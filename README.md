# secret_exchange — Docker

Запуск проекта в Docker (локальная среда, development):

1) Собрать и запустить контейнеры:

```bash
docker compose up --build
```

2) Приложение будет доступно по адресу http://localhost:8000

Сервисы:
- `web` — Django + Gunicorn
- `db` — PostgreSQL
- `redis` — Redis (для Celery)
- `worker` — Celery worker

Примечания:
- В `config/settings.py` добавлены чтение переменных окружения для базы данных и Celery.
- Для production рекомендую использовать безопасные секреты и HTTPS.
