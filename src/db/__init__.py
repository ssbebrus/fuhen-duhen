from src.db.base import Base

# Импортируем все модели сюда, чтобы метаданные Base загрузились для Alembic
from src.modules.products.models import Product
from src.modules.categories.models import Category
from src.modules.skus.models import SKU

# Иначе alembic --autogenerate не сможет найти таблицы
