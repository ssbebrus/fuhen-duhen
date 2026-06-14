import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Optional
from fastapi import HTTPException
from uuid import UUID


from .models import Category
from .schemas import CategoryCreate, CategoryUpdate

class CategoryService:
    @staticmethod
    async def get_all(
        db: AsyncSession,
        parent_id: Optional[UUID] = None,
        only_root: bool = False
    ) -> List[Category]:
        """Получить список всех категорий с возможностью фильтрации"""
        query = select(Category)
        if only_root:
            query = query.where(Category.level == 0)
        elif parent_id:
            parent = await CategoryService.get_by_id(db, parent_id)
            if parent:
                query = query.where(
                    Category.level == parent.level + 1,
                    Category.path.like(f"{parent.path}.%")
                )
            else:
                return []
        
        result = await db.execute(query.order_by(Category.level, Category.name))
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(db: AsyncSession, category_id: UUID) -> Optional[Category]:
        """Получить категорию по ID"""
        result = await db.execute(select(Category).where(Category.id == category_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_tree(db: AsyncSession) -> List[dict]:
        """Получить полное дерево активных категорий"""
        result = await db.execute(
            select(Category)
            .where(Category.is_active == True)
            .order_by(Category.level, Category.name)
        )
        categories = result.scalars().all()
        
        nodes = {}
        roots = []
        
        for cat in categories:
            nodes[cat.id] = {
                "id": cat.id,
                "name": cat.name,
                "children": []
            }
            
        for cat in categories:
            node = nodes[cat.id]
            parent_id = None
            if cat.level > 0 and cat.path:
                parts = cat.path.split('.')
                if len(parts) > 1:
                    try:
                        parent_id = UUID(parts[-2])
                    except ValueError:
                        pass
            
            if parent_id and parent_id in nodes:
                nodes[parent_id]["children"].append(node)
            else:
                if cat.level == 0 or not parent_id or parent_id not in nodes:
                    roots.append(node)
        return roots

    @staticmethod
    async def get_by_id_with_children(db: AsyncSession, category_id: UUID) -> Optional[dict]:
        """Получить категорию и список её прямых подкатегорий"""
        category = await CategoryService.get_by_id(db, category_id)
        if not category:
            return None
            
        result = await db.execute(
            select(Category)
            .where(
                Category.level == category.level + 1,
                Category.path.like(f"{category.path}.%")
            )
            .order_by(Category.name)
        )
        children = list(result.scalars().all())
        
        return {
            "id": category.id,
            "name": category.name,
            "level": category.level,
            "path": category.path,
            "is_active": category.is_active,
            "created_at": category.created_at,
            "updated_at": category.updated_at,
            "children": children
        }

    @staticmethod
    async def get_breadcrumbs(db: AsyncSession, category_id: UUID) -> Optional[List[Category]]:
        """Получить хлебные крошки от корня до категории"""
        category = await CategoryService.get_by_id(db, category_id)
        if not category:
            return None
        if not category.path:
            return [category]
            
        parts = category.path.split('.')
        uuids = []
        for p in parts:
            try:
                uuids.append(UUID(p))
            except ValueError:
                pass
                
        if not uuids:
            return [category]
            
        result = await db.execute(select(Category).where(Category.id.in_(uuids)))
        fetched = {cat.id: cat for cat in result.scalars().all()}
        
        breadcrumbs = []
        for u in uuids:
            if u in fetched:
                breadcrumbs.append(fetched[u])
        return breadcrumbs

    @staticmethod
    async def create(db: AsyncSession, category_in: CategoryCreate) -> Category:
        """Создать новую категорию с расчетом path и level"""
        new_id = uuid.uuid4()
        level = 0
        path = str(new_id)
        
        if category_in.parent_id:
            parent = await CategoryService.get_by_id(db, category_in.parent_id)
            if parent:
                level = parent.level + 1
                path = f"{parent.path}.{new_id}"
        
        data = category_in.model_dump(exclude={"parent_id"})
        new_category = Category(id=new_id, level=level, path=path, **data)
        
        db.add(new_category)
        await db.commit()
        await db.refresh(new_category)
        return new_category

    @staticmethod
    async def update(db: AsyncSession, category_id: UUID, category_in: CategoryUpdate) -> Optional[Category]:
        """Обновить категорию с пересчетом путей потомков при смене родителя"""
        category = await CategoryService.get_by_id(db, category_id)
        if not category:
            return None
            
        update_data = category_in.model_dump(exclude_unset=True)
        if not update_data:
            return category
            
        if "parent_id" in update_data:
            new_parent_id = update_data.pop("parent_id")
            old_path = category.path
            old_level = category.level
            
            if new_parent_id is None:
                new_level = 0
                new_path = str(category_id)
            else:
                if new_parent_id == category_id:
                    raise HTTPException(status_code=400, detail={"code": "INVALID_REQUEST", "message": "Category cannot be its own parent"})
                parent = await CategoryService.get_by_id(db, new_parent_id)
                if not parent:
                    raise HTTPException(status_code=400, detail={"code": "INVALID_REQUEST", "message": "Parent category not found"})
                if parent.path.startswith(f"{old_path}.") or parent.id == category_id:
                    raise HTTPException(status_code=400, detail={"code": "INVALID_REQUEST", "message": "Cycle detected in categories hierarchy"})
                new_level = parent.level + 1
                new_path = f"{parent.path}.{category_id}"
            
            # Fetch descendants and update their path and level
            res_desc = await db.execute(
                select(Category).where(Category.path.like(f"{old_path}.%"))
            )
            descendants = res_desc.scalars().all()
            for desc in descendants:
                desc.path = desc.path.replace(old_path, new_path, 1)
                desc.level = desc.level + (new_level - old_level)
                
            category.level = new_level
            category.path = new_path
            
        for key, val in update_data.items():
            setattr(category, key, val)
            
        await db.commit()
        await db.refresh(category)
        return category

