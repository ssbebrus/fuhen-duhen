import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import joinedload
from fastapi import HTTPException, status, BackgroundTasks

from .models import ReserveOperation
from .schemas import ReserveRequest, InventoryOrderRequest, ReservedItemInfo
from src.modules.skus.models import SKU
from src.modules.products.models import Product, ProductStatus
from src.modules.common.events import send_b2c_sku_out_of_stock_event

class InventoryService:
    @staticmethod
    async def reserve(
        db: AsyncSession, 
        request: ReserveRequest,
        background_tasks: BackgroundTasks
    ) -> Dict[str, Any]:
        # 1. Проверяем идемпотентность по idempotency_key
        existing_op = await db.get(ReserveOperation, request.idempotency_key)
        if existing_op:
            # Если операция уже успешно выполнена, возвращаем сохраненный результат
            return existing_op.result

        # 2. Сортируем sku_id для исключения взаимоблокировок (deadlocks)
        sorted_items = sorted(request.items, key=lambda x: x.sku_id)
        sorted_sku_ids = [item.sku_id for item in sorted_items]

        # 3. Начинаем транзакцию с SELECT FOR UPDATE
        # Нам также нужно загрузить связанные товары (products), чтобы проверить их статус и deleted флаг
        stmt = (
            select(SKU)
            .where(SKU.id.in_(sorted_sku_ids))
            .options(joinedload(SKU.product, innerjoin=True))
            .with_for_update(of=SKU)
        )
        result = await db.execute(stmt)
        skus_list = result.scalars().all()
        skus_map = {sku.id: sku for sku in skus_list}

        failed_items = []
        items_to_process = []

        # 4. Проверяем остатки и статус каждого SKU/товара
        for item in request.items:
            sku = skus_map.get(item.sku_id)
            
            # Если SKU не найден или товар удален / не модерирован
            if not sku or sku.product.deleted or sku.product.status != ProductStatus.MODERATED:
                failed_items.append({
                    "sku_id": str(item.sku_id),
                    "requested": item.quantity,
                    "available": 0,
                    "reason": "OUT_OF_STOCK"
                })
            else:
                # Если недостаточно остатка к продаже
                if sku.active_quantity < item.quantity:
                    reason = "OUT_OF_STOCK" if sku.active_quantity == 0 else "INSUFFICIENT_STOCK"
                    failed_items.append({
                        "sku_id": str(item.sku_id),
                        "requested": item.quantity,
                        "available": sku.active_quantity,
                        "reason": reason
                    })
                else:
                    items_to_process.append((sku, item.quantity))

        # 5. Если есть хотя бы одна ошибка - делаем ROLLBACK и возвращаем 409
        if failed_items:
            # В SQLAlchemy 2.0 rollback происходит автоматически при выходе из блока транзакции или при ошибке,
            # но мы можем явно вернуть ответ, так как API-контроллер выбросит HTTPException.
            error_detail = {
                "code": "INSUFFICIENT_STOCK",
                "message": "Недостаточно товара на складе для некоторых позиций",
                "details": {
                    "reserved": False,
                    "failed_items": failed_items
                },
                # Для прямого соответствия каноническому flow (где B2C ожидает эти поля на верхнем уровне)
                "reserved": False,
                "failed_items": failed_items
            }
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_detail
            )

        # 6. Если все проверки прошли, выполняем списание active и начисление reserved
        reserved_items = []
        skus_to_check_out_of_stock = []

        for sku, quantity in items_to_process:
            sku.active_quantity -= quantity
            sku.reserved_quantity += quantity
            
            # Подготавливаем данные для ответа
            reserved_items.append(
                ReservedItemInfo(
                    sku_id=sku.id,
                    reserved_quantity=quantity,
                    remaining_stock=sku.active_quantity
                )
            )

            # Если после резервирования остаток стал 0, запоминаем для отправки события B2C
            if sku.active_quantity == 0:
                skus_to_check_out_of_stock.append((sku.product_id, sku.id))

        # Собираем успешный ответ
        response_data = {
            "order_id": str(request.order_id),
            "status": "RESERVED",
            "reserved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "reserved": True,
            "items": [
                {
                    "sku_id": str(item.sku_id),
                    "reserved_quantity": item.reserved_quantity,
                    "remaining_stock": item.remaining_stock
                }
                for item in reserved_items
            ]
        }

        # Записываем операцию резервирования в БД
        new_op = ReserveOperation(
            idempotency_key=request.idempotency_key,
            order_id=request.order_id,
            status="RESERVED",
            result=response_data
        )
        db.add(new_op)

        # Фиксируем изменения
        await db.commit()

        # 7. После коммита отправляем события в B2C о том, что SKU закончился
        for product_id, sku_id in skus_to_check_out_of_stock:
            background_tasks.add_task(send_b2c_sku_out_of_stock_event, product_id, sku_id)

        return response_data

    @staticmethod
    async def unreserve(
        db: AsyncSession, 
        request: InventoryOrderRequest
    ) -> Dict[str, Any]:
        # 1. Проверяем, не была ли эта транзакция уже отменена (идемпотентность по order_id)
        stmt_op = select(ReserveOperation).where(ReserveOperation.order_id == request.order_id)
        res_ops = await db.execute(stmt_op)
        existing_ops = res_ops.scalars().all()

        # Если уже есть отмененная операция по этому заказу, просто возвращаем успешный ответ
        for op in existing_ops:
            if op.status == "UNRESERVED":
                return op.result

        # Находим оригинальную операцию резервирования (RESERVED)
        reserved_op = next((op for op in existing_ops if op.status == "RESERVED"), None)

        # 2. Восстанавливаем остатки только из найденной операции резервирования (компенсация)
        items_to_restore = []
        if reserved_op and "items" in reserved_op.result:
            for item in reserved_op.result["items"]:
                sku_id_str = item.get("sku_id")
                qty = item.get("reserved_quantity", 0)
                if sku_id_str and qty > 0:
                    items_to_restore.append((uuid.UUID(sku_id_str), qty))

        # Сортируем SKU для предотвращения взаимоблокировок (deadlocks)
        sorted_items = sorted(items_to_restore, key=lambda x: x[0])
        sorted_sku_ids = [sku_id for sku_id, _ in sorted_items]

        # 3. Блокируем строки SKU в БД и восстанавливаем остатки
        if sorted_sku_ids:
            stmt_skus = select(SKU).where(SKU.id.in_(sorted_sku_ids)).with_for_update()
            res_skus = await db.execute(stmt_skus)
            skus_list = res_skus.scalars().all()
            skus_map = {sku.id: sku for sku in skus_list}

            # 4. Восстанавливаем остатки
            for sku_id, qty in sorted_items:
                sku = skus_map.get(sku_id)
                if sku:
                    # Увеличиваем active_quantity, уменьшаем reserved_quantity
                    sku.active_quantity += qty
                    sku.reserved_quantity = max(0, sku.reserved_quantity - qty)

        response_data = {
            "order_id": str(request.order_id),
            "status": "UNRESERVED",
            "processed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "ok": True
        }

        # 5. Обновляем статус существующих операций или создаем плейсхолдер
        if existing_ops:
            for op in existing_ops:
                op.status = "UNRESERVED"
                op.result = response_data
        else:
            # Если самой операции резервирования не существовало, все равно сохраняем
            # плейсхолдер с отмененным статусом для будущей идемпотентности
            placeholder_key = uuid.uuid5(uuid.NAMESPACE_OID, f"unreserve_{request.order_id}")
            placeholder_op = ReserveOperation(
                idempotency_key=placeholder_key,
                order_id=request.order_id,
                status="UNRESERVED",
                result=response_data
            )
            db.add(placeholder_op)

        await db.commit()
        return response_data

    @staticmethod
    async def fulfill(
        db: AsyncSession, 
        request: InventoryOrderRequest
    ) -> Dict[str, Any]:
        # 1. Проверяем, не была ли эта транзакция уже выполнена (идемпотентность по order_id)
        stmt_op = select(ReserveOperation).where(ReserveOperation.order_id == request.order_id)
        res_ops = await db.execute(stmt_op)
        existing_ops = res_ops.scalars().all()

        # Если уже есть завершенная операция по этому заказу, просто возвращаем успешный ответ
        for op in existing_ops:
            if op.status == "FULFILLED":
                return op.result

        # 2. Сортируем SKU для предотвращения взаимоблокировок
        sorted_items = sorted(request.items, key=lambda x: x.sku_id)
        sorted_sku_ids = [item.sku_id for item in sorted_items]

        # 3. Блокируем строки SKU в БД
        stmt_skus = select(SKU).where(SKU.id.in_(sorted_sku_ids)).with_for_update()
        res_skus = await db.execute(stmt_skus)
        skus_list = res_skus.scalars().all()
        skus_map = {sku.id: sku for sku in skus_list}

        # 4. Списываем резервы и физические остатки
        for item in request.items:
            sku = skus_map.get(item.sku_id)
            if sku:
                # Уменьшаем stock_quantity и reserved_quantity
                sku.stock_quantity = max(0, sku.stock_quantity - item.quantity)
                sku.reserved_quantity = max(0, sku.reserved_quantity - item.quantity)

        response_data = {
            "order_id": str(request.order_id),
            "status": "FULFILLED",
            "processed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "ok": True
        }

        # 5. Обновляем статус существующих операций или создаем плейсхолдер
        if existing_ops:
            for op in existing_ops:
                op.status = "FULFILLED"
                op.result = response_data
        else:
            placeholder_key = uuid.uuid5(uuid.NAMESPACE_OID, f"fulfill_{request.order_id}")
            placeholder_op = ReserveOperation(
                idempotency_key=placeholder_key,
                order_id=request.order_id,
                status="FULFILLED",
                result=response_data
            )
            db.add(placeholder_op)

        await db.commit()
        return response_data
