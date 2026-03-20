from src.db.base import Base

# Импортируем все модели сюда, чтобы метаданные Base загрузились для Alembic
from src.modules.products.models import Product

# Иначе alembic --autogenerate не сможет найти таблицы
