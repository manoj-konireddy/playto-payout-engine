# Playto Payout Engine Challenge

Minimal payout engine for Playto Pay using Django + DRF + Celery and a React + Tailwind dashboard.

## Stack

- Backend: Django 6, Django REST Framework
- Worker: Celery
- DB: PostgreSQL only
- Frontend: React 18 + Tailwind (served as static module by Django)

## Core capabilities implemented

- Merchant ledger with integer paise amounts only (`BigIntegerField`)
- Payout request API with merchant-scoped idempotency key
- Atomic funds hold during payout creation
- Background payout processor with probabilistic outcomes (70/20/10)
- Retry with exponential backoff for stuck processing payouts
- Strict payout state machine with illegal transition checks
- Dashboard for balances, ledger history, payout request, and live status polling

## Project structure

- `backend/config`: Django project config + Celery wiring
- `backend/payouts`: models, API, services, worker task, tests, seed command
- `frontend/index.html`: dashboard host page
- `frontend/app.js`: React + Tailwind dashboard app

## Local setup

```bash
python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install django djangorestframework celery redis psycopg[binary]
```

## Environment variables

PostgreSQL (required):

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`

Celery:

- `CELERY_BROKER_URL` (default: `redis://localhost:6379/0`)
- `CELERY_RESULT_BACKEND` (default: `redis://localhost:6379/0`)
- `CELERY_TASK_ALWAYS_EAGER=1` (optional for local synchronous execution)

## Run backend

```bash
$env:POSTGRES_DB="playto"
$env:POSTGRES_USER="playto"
$env:POSTGRES_PASSWORD="playto"
$env:POSTGRES_HOST="127.0.0.1"
$env:POSTGRES_PORT="5433"
.venv\Scripts\python backend\manage.py migrate
.venv\Scripts\python backend\manage.py seed_data
.venv\Scripts\python backend\manage.py runserver
```

Open `http://127.0.0.1:8000/`

## Run worker (Windows)

```bash
cd backend
$env:POSTGRES_DB="playto"
$env:POSTGRES_USER="playto"
$env:POSTGRES_PASSWORD="playto"
$env:POSTGRES_HOST="127.0.0.1"
$env:POSTGRES_PORT="5433"
$env:CELERY_BROKER_URL="redis://127.0.0.1:6379/0"
$env:CELERY_RESULT_BACKEND="redis://127.0.0.1:6379/0"
..\.venv\Scripts\celery -A config worker -l info --pool=solo
```

`--pool=solo` is required on Windows.

## Run beat scheduler (Windows)

```bash
cd backend
$env:POSTGRES_DB="playto"
$env:POSTGRES_USER="playto"
$env:POSTGRES_PASSWORD="playto"
$env:POSTGRES_HOST="127.0.0.1"
$env:POSTGRES_PORT="5433"
$env:CELERY_BROKER_URL="redis://127.0.0.1:6379/0"
$env:CELERY_RESULT_BACKEND="redis://127.0.0.1:6379/0"
..\.venv\Scripts\celery -A config beat -l info
```

Beat runs the periodic job every 5 seconds to process pending/stuck payouts.

## Trigger payout processing

You can call the task manually from shell:

```bash
.venv\Scripts\python backend\manage.py shell -c "from payouts.tasks import process_payouts; process_payouts.delay()"
```

## About "adding money"

Customer payment collection/add-money flow is intentionally not implemented because the challenge explicitly says you do not need to build it.

Instead, merchant credits are simulated through seeded `LedgerEntry` credit rows via:

```bash
.venv\Scripts\python backend\manage.py seed_data
```

## API

### Get dashboard

`GET /api/v1/merchant/dashboard`

Headers:

- `X-Merchant-Id: <merchant_id>`

### Create payout

`POST /api/v1/payouts`

Headers:

- `X-Merchant-Id: <merchant_id>`
- `Idempotency-Key: <uuid>`

Body:

```json
{
  "amount_paise": 6000,
  "bank_account_id": 1
}
```

### List payouts

`GET /api/v1/payouts`

Headers:

- `X-Merchant-Id: <merchant_id>`

## Tests

```bash
$env:POSTGRES_DB="playto"
$env:POSTGRES_USER="playto"
$env:POSTGRES_PASSWORD="playto"
$env:POSTGRES_HOST="127.0.0.1"
$env:POSTGRES_PORT="5433"
.venv\Scripts\python backend\manage.py test payouts
```

Includes:

- Idempotency replay test
- Concurrency overdraft test (runs on PostgreSQL)
