from src.db.base import Base

# Импортируем все модели сюда, чтобы метаданные Base загрузились для Alembic
from src.modules.products.models import Product, ProcessedEvent
from src.modules.categories.models import Category
from src.modules.skus.models import SKU
from src.modules.auth.models import Seller, WarehouseOperator, RefreshToken
from src.modules.invoices.models import Invoice, InvoiceItem
from src.modules.inventory.models import ReserveOperation

# Иначе alembic --autogenerate не сможет найти таблицы
