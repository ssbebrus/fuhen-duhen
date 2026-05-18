from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException, status
import datetime

from .models import Invoice, InvoiceItem, InvoiceStatus
from .schemas import InvoiceCreate, InvoiceAcceptRequest
from src.modules.skus.models import SKU
from src.modules.products.models import ProductStatus

class InvoiceService:
    @staticmethod
    async def get_all(db: AsyncSession, limit: int = 20, offset: int = 0, seller_id: Optional[UUID] = None, status_filter: Optional[InvoiceStatus] = None) -> dict:
        count_query = select(func.count()).select_from(Invoice)
        
        conditions = []
        if seller_id:
            conditions.append(Invoice.seller_id == seller_id)
        if status_filter:
            conditions.append(Invoice.status == status_filter)
            
        if conditions:
            count_query = count_query.where(*conditions)
            
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        query = (
            select(Invoice)
            .options(selectinload(Invoice.items))
            .order_by(Invoice.created_at.desc())
        )
        
        if conditions:
            query = query.where(*conditions)
            
        query = query.limit(limit).offset(offset)
            
        result = await db.execute(query)
        invoices = list(result.scalars().all())
        
        # Populate sku_name for items
        for invoice in invoices:
            for item in invoice.items:
                sku = await db.execute(select(SKU).where(SKU.id == item.sku_id))
                sku = sku.scalar_one_or_none()
                item.sku_name = sku.name if sku else "Unknown SKU"
        
        return {
            "items": invoices,
            "total_count": total,
            "limit": limit,
            "offset": offset
        }

    @staticmethod
    async def create(db: AsyncSession, invoice_in: InvoiceCreate, seller_id: UUID) -> Invoice:
        if not invoice_in.items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_REQUEST", "message": "At least one item is required"}
            )

        sku_ids = [item.sku_id for item in invoice_in.items]
        
        query = select(SKU).where(SKU.id.in_(sku_ids)).options(selectinload(SKU.product))
        result = await db.execute(query)
        skus = {sku.id: sku for sku in result.scalars().all()}
        
        for item in invoice_in.items:
            sku = skus.get(item.sku_id)
            if not sku:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"code": "NOT_FOUND", "message": "SKU not found"}
                )
            
            if sku.product.seller_id != seller_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"code": "NOT_OWNER", "message": "One or more SKUs do not belong to the authenticated seller"}
                )
            
            if sku.product.status != ProductStatus.MODERATED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"code": "INVALID_REQUEST", "message": "Invoice can only be created for MODERATED products"}
                )
                
            if item.quantity <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"code": "INVALID_REQUEST", "message": "quantity must be > 0"}
                )

        new_invoice = Invoice(
            seller_id=seller_id,
            status=InvoiceStatus.CREATED
        )
        db.add(new_invoice)
        await db.flush() # To get new_invoice.id

        for item in invoice_in.items:
            invoice_item = InvoiceItem(
                invoice_id=new_invoice.id,
                sku_id=item.sku_id,
                quantity=item.quantity
            )
            db.add(invoice_item)

        await db.commit()
        
        # Re-query to avoid MissingGreenlet / lazy loading issues
        query = select(Invoice).where(Invoice.id == new_invoice.id).options(selectinload(Invoice.items))
        result = await db.execute(query)
        new_invoice = result.scalar_one()
        
        # Inject sku_name for the response
        for item in new_invoice.items:
            sku = skus.get(item.sku_id)
            item.sku_name = sku.name if sku else "Unknown SKU"
            
        return new_invoice

    @staticmethod
    async def accept(db: AsyncSession, invoice_id: UUID, accept_in: Optional[InvoiceAcceptRequest], operator_id: UUID) -> Invoice:
        query = select(Invoice).where(Invoice.id == invoice_id).options(selectinload(Invoice.items))
        result = await db.execute(query)
        invoice = result.scalar_one_or_none()
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Invoice not found"}
            )
        
        if invoice.status != InvoiceStatus.CREATED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "CONFLICT", "message": "Invoice is already processed"}
            )

        invoice_items_map = {item.id: item for item in invoice.items}
        accepted_quantities = {}

        if not accept_in or accept_in.accepted_items is None:
            for item in invoice.items:
                accepted_quantities[item.id] = item.quantity
        else:
            for acc_item in accept_in.accepted_items:
                item = invoice_items_map.get(acc_item.invoice_item_id)
                if not item:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={"code": "INVALID_REQUEST", "message": f"Invoice item {acc_item.invoice_item_id} not found in this invoice"}
                    )
                
                if acc_item.accepted_quantity < 0 or acc_item.accepted_quantity > item.quantity:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={"code": "INVALID_REQUEST", "message": f"accepted_quantity must be between 0 and {item.quantity}"}
                    )
                accepted_quantities[acc_item.invoice_item_id] = acc_item.accepted_quantity
            
            for item in invoice.items:
                if item.id not in accepted_quantities:
                    accepted_quantities[item.id] = 0

        all_accepted_qty = []
        all_quantity = []

        sku_ids = [item.sku_id for item in invoice.items]
        sku_query = select(SKU).where(SKU.id.in_(sku_ids))
        sku_result = await db.execute(sku_query)
        skus = {sku.id: sku for sku in sku_result.scalars().all()}

        for item in invoice.items:
            qty = accepted_quantities[item.id]
            item.accepted_quantity = qty
            db.add(item)
            
            all_accepted_qty.append(qty)
            all_quantity.append(item.quantity)

            sku = skus.get(item.sku_id)
            if sku:
                sku.active_quantity = (sku.active_quantity or 0) + qty
                sku.stock_quantity = (sku.stock_quantity or 0) + qty
                db.add(sku)

        if all(a == q for a, q in zip(all_accepted_qty, all_quantity)):
            invoice.status = InvoiceStatus.ACCEPTED
        elif all(a == 0 for a in all_accepted_qty):
            invoice.status = InvoiceStatus.CANCELLED
        else:
            invoice.status = InvoiceStatus.PARTIALLY_ACCEPTED

        invoice.accepted_at = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        invoice.accepted_by = operator_id
        db.add(invoice)
        
        await db.commit()
        
        # Re-query to avoid MissingGreenlet / lazy loading issues
        query = select(Invoice).where(Invoice.id == invoice.id).options(selectinload(Invoice.items))
        result = await db.execute(query)
        invoice = result.scalar_one()

        for item in invoice.items:
            sku = skus.get(item.sku_id)
            item.sku_name = sku.name if sku else "Unknown SKU"
            
        return invoice
