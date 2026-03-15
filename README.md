# URL Shortener FastAPI

небольшой сервис для сокращения ссылок
отправляешь длинный URL и получаешь короткий код, по нему идёт редирект
данные хранятся в PostgreSQL, для ускорения редиректов используется Redis-кэш

основное:

POST /links/shorten - создать короткую ссылку (можно custom_alias, можно expires_at)
GET /links/{short_code} - редирект на оригинальный URL (и увеличивает счётчик переходов)
GET /links/{short_code}/stats - статистика (оригинал, дата создания, клики, последнее использование)
GET /links/search?original_url=.. - найти короткие ссылки по оригинальному URL
PUT /links/{short_code} - обновить original_url (только владелец)
DELETE /links/{short_code} - удалить ссылку (только владелец)

дополнительно:

автоудаление неиспользуемых ссылок спустя INACTIVE_DAYS

история удалённых/истёкших ссылок: GET /links/expired

авторизация:

есть POST /auth/register и POST /auth/login
GET и POST доступны всем
PUT и DELETE — только для зарегистрированных (и только если ссылка твоя)

## Как запустить локально (Docker)
1) в корне проекта должен быть `.env`
2) запуск:

```bash
docker compose up --build

Swagger:

http://localhost:8000/docs

если нужно остановить:

docker compose down

пример .env
POSTGRES_DB=shortener
POSTGRES_USER=shortener
POSTGRES_PASSWORD=shortener

DATABASE_URL=postgresql+asyncpg://shortener:shortener@db:5432/shortener
REDIS_URL=redis://redis:6379/0

JWT_SECRET=super_secret_key_123
JWT_EXPIRE_MINUTES=60

INACTIVE_DAYS=7