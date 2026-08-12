# Smart Placement Companion (SPC)

## Quick start (local)

1. Create virtual env and install dependencies:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Apply migrations and create a superuser:
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```
3. Run server:
   ```bash
   python manage.py runserver
   ```

## Database options
- Default: SQLite (local development)
- Postgres: set `DB_ENGINE=django.db.backends.postgresql` and run via Docker Compose

## PostgreSQL + Docker
```bash
docker compose up --build
```

## Roles
- Use Django admin to create groups: `coordinator`, `recruiter`, `student`.
- Assign users to groups and map students by email.

## Real-time metrics
- Live metrics update via WebSockets on `ws://<host>/ws/metrics/`.
- Fallback to polling every 15 seconds.
