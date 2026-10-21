# SetWise — modular Flask prototype (no JavaScript)

Refactored from the original working server-rendered SetWise prototype, preserving the same HTML, CSS, URL structure and functionality. Local-only SQLite and rule-based recommendations; **not yet connected to AWS Bedrock**.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Open http://127.0.0.1:5000.

Run tests (no external test framework needed):

```bash
python -m unittest discover -s tests -v
```

## Organisation

- `app/__init__.py`: application factory (`create_app`)
- `app/routes/main.py`: form and page HTTP routes
- `app/services/inventory_service.py`: sample initial data
- `app/services/analysis_service.py`: dashboard aggregations
- `app/services/planning_service.py`: deterministic recommendation generator
- `app/services/actions.py`: wall/climb/target/reset/plan operations
- `app/database/repository.py`: SQLite persistence adapter
- `app/templates/index.html`, `app/static/style.css`: unchanged browser UI
- `run.py`: entry point
- `tests/`: isolated SQLite tests

## AWS migration

Keep the routes and business logic where possible; swap the SQLite repository for a DynamoDB adapter, then move longer-running planning into an ECS worker using SQS. Add Bedrock behind a separate recommendation service and deploy behind production authentication and CSRF protection. Do not put `.db`, `.env`, or local secrets into Git.

**Limitations:** This refactor preserves the original simple shared-state SQLite design; it is not concurrency-safe for simultaneous writers, and the original HTML forms have no CSRF protection. Address these before public deployment. The initial data is illustrative demo data.

## Docker (local first)

Install Docker Desktop, then run from this project's directory:

```bash
docker compose up --build -d
docker compose ps
```

Open **http://localhost:5050**. The database is kept in the named Docker volume `setwise_data`, so it survives container recreation. To inspect logs and stop the container:

```bash
docker compose logs -f setwise
docker compose down
```

For a clean reset of **local demo data only**, `docker compose down -v` also deletes that volume.

Run tests using a disposable container that doesn't connect to the persistent volume:

```bash
docker compose run --rm --no-deps -e SETWISE_DB=/tmp/setwise-test.db setwise python -m unittest discover -s tests -v
```

The container binds to localhost on port 5050, uses Gunicorn, and remains a **local demo**: SQLite stores a single shared JSON document, so this is not safe for concurrent production writes or multiple ECS replicas. Before public AWS deployment, implement shared datastore, secure user/gym access and CSRF protection.
