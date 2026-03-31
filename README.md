# Fuhen-Duhen B2B Marketplace Backend

Бэкенд для B2B маркетплейса, обеспечивающий управление категориями, товарами (Products) и их вариациями (SKUs), а также хранение изображений в S3-совместимом хранилище.

## Функционал
- **Управление каталогом**: Создание и редактирование категорий, товаров и артикулов (SKU).
- **Хранение медиа**: Интеграция с MinIO для загрузки и хранения изображений товаров.
- **Гибкая конфигурация**: Использование Pydantic Settings для управления окружением.
- **Автодокументация**: Swagger/ReDoc из коробки.

## Технологический стек
- **Язык**: Python 3.12+
- **Фреймворк**: FastAPI
- **База данных**: PostgreSQL (Asyncpg)
- **ORM**: SQLAlchemy 2.0
- **Миграции**: Alembic
- **Хранилище объектов**: MinIO (S3-совместимое)
- **Контейнеризация**: Docker & Docker Compose

## Быстрый запуск

### 1. Подготовка окружения
Создайте файл `.env` на основе примера:
```bash
cp env.sample .env
```
Отредактируйте `.env`, если требуется изменить стандартные порты или учетные данные.

### 2. Запуск через Docker Compose
Запустите все сервисы (база данных, minio, приложение):
```bash
docker-compose up --build
```
Приложение будет доступно по адресу: http://localhost:8000

### 3. Применение миграций
После запуска контейнеров необходимо применить миграции базы данных:
```bash
docker-compose exec backend alembic upgrade head
```

## Настройки приложения
Все основные настройки находятся в файле [src/config.py](src/config.py). 
Приложение использует `pydantic-settings` для автоматической загрузки переменных из `.env`.

## Полезные ссылки
- **Swagger UI (Dosc)**: [http://localhost:8000/docs](http://localhost:8000/docs) - полная спецификация API.
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health) - проверка статуса сервиса.
- **MinIO Console**: [http://localhost:9001](http://localhost:9001) - веб-интерфейс управления хранилищем изображений (логин/пароль из `.env`).
- **MinIO API**: [http://localhost:9000](http://localhost:9000) - адрес для программного доступа к S3.

## Разработка
Для локальной разработки без Docker (требуется установленный PostgreSQL и MinIO):
1. Создайте venv: `python -m venv .venv`
2. Активируйте: `.venv\Scripts\activate` (Windows) или `source .venv/bin/activate` (Linux/macOS)
3. Установите зависимости: `pip install -r requirements.txt`
4. Запустите: `uvicorn src.main:app --reload`