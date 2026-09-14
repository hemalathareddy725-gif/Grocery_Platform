# Aforro Backend Assignment (Round 2)

Django + DRF backend covering order processing, inventory, product search/autocomplete,
Redis caching, Celery async jobs, and Docker.

## Stack
Django 5, DRF, PostgreSQL, Redis (cache + Celery broker), Celery, Docker Compose.

## Project layout
```
config/            settings, urls, celery app
apps/products/      Category, Product models + search serializer + cache-invalidation signals
apps/stores/         Store, Inventory models + inventory listing API
apps/orders/         Order, OrderItem models + order create/list APIs + confirmation task
apps/search/         product search + autocomplete APIs
tests/               test suite
```

## Setup — Docker (recommended)
```bash
cp .env.example .env
docker-compose up --build
```
This starts: `web` (Django on :8000), `db` (Postgres), `redis`, `celery_worker`, `celery_beat`.
Migrations run automatically on `web` startup.

Seed data (run once containers are up):
```bash
docker-compose exec web python manage.py seed_data
```
Create an admin user (optional):
```bash
docker-compose exec web python manage.py createsuperuser
```

## Setup — Local (without Docker)
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit POSTGRES_HOST=localhost, REDIS_URL=redis://localhost:6379/0
python manage.py migrate
python manage.py seed_data
python manage.py runserver
# in separate terminals:
celery -A config worker -l info
celery -A config beat -l info
```

## Running tests
```bash
python manage.py test tests
```
(7 tests covering order creation/rejection, stock deduction, order listing, inventory
listing, and search/autocomplete.) Tests automatically fall back to an in-memory cache
and eager Celery execution, so no Redis/broker is required to run them.

## Sample API requests

**Create an order**
```bash
curl -X POST localhost:8000/orders/ -H "Content-Type: application/json" -d '{
  "store_id": 1,
  "items": [{"product_id": 10, "quantity_requested": 2}, {"product_id": 11, "quantity_requested": 1}]
}'
```
Returns `201` with `status: CONFIRMED` if all items have enough stock, or `200` with
`status: REJECTED` (no stock deducted) otherwise. The stock check + deduction runs inside
`transaction.atomic()` with `select_for_update()` on the relevant inventory rows, so
concurrent orders against the same store/product can't oversell.

**List a store's orders**
```bash
curl localhost:8000/stores/1/orders/
```
Newest first, with an annotated `item_count` (via `Count`) so no N+1 queries per order.

**List a store's inventory**
```bash
curl localhost:8000/stores/1/inventory/
```
`select_related` on product + category, sorted alphabetically by product title.

**Product search**
```bash
curl "localhost:8000/api/search/products/?q=phone&category=Electronics&sort=price&store_id=1&in_stock=1&page=1"
```
Supports `q` (title/description/category keyword match), `category`, `min_price`,
`max_price`, `store_id`, `in_stock`, `sort` (`price` | `newest` | `relevance`), plus
DRF's standard pagination params.

**Autocomplete**
```bash
curl "localhost:8000/api/search/suggest/?q=pho"
```
Requires `q` >= 3 chars, returns up to 10 titles with prefix matches ranked before
substring matches. Rate-limited to 20 req/min per user/IP.

## Caching / async notes

- **Caching (Redis)**: `ProductSearchView` and `ProductSuggestView` cache their JSON
  responses in Redis, keyed by a hash of the query params plus a **cache version**
  number. Any write to `Product`, `Category`, or `Inventory` bumps that version via
  Django signals (`apps/products/signals.py`, `apps/stores/signals.py`), which
  instantly invalidates *every* cached search/suggest response without needing to
  enumerate or delete individual keys — cheap and correct under concurrent writes.
- **Rate limiting**: `/api/search/suggest/` is also throttled via DRF's
  `UserRateThrottle`/`AnonRateThrottle` (`20/min`), which is backed by the same Redis
  cache — so both caching and rate limiting are demonstrated using Redis.
- **Celery**: order creation triggers `send_order_confirmation.delay(order.id)` when an
  order is `CONFIRMED`. The worker looks up the order and logs a confirmation (kept
  free of real email/SMS integration so it runs without extra config). Redis is used
  as both the broker and result backend. `celery_beat` is included in `docker-compose.yml`
  for scheduled jobs (e.g. a daily inventory summary) though none is scheduled by default.

## Scalability considerations
- Inventory writes use `F()` expressions + `select_for_update()` inside
  `transaction.atomic()` to avoid lost updates under concurrent order placement.
- `Inventory` has a unique constraint on `(store, product)` enforcing "at most one
  inventory row per product per store" at the DB level.
- Search/listing endpoints use `select_related`/`annotate` to avoid N+1 queries, and
  DB indexes on `Product.title`, `Product.price`, `Product.created_at`, and
  `Order(store, -created_at)` support the common filter/sort paths.
- Search results are cached in Redis with a short TTL (5 min) as a safety net on top
  of version-based invalidation, and pagination bounds response size regardless of
  catalog size.
- For further scale: move `icontains` search to Postgres full-text search / an
  external search engine (e.g. OpenSearch) once catalog size grows past what
  multi-field `LIKE` queries handle well; add read replicas for listing/search
  endpoints; shard Celery queues by task type if async volume grows.
