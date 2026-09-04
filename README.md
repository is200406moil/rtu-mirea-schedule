# RTU MIREA Schedule API

API для получения расписания учебных групп РТУ МИРЭА. Сервис читает публичный источник расписания, разбирает iCalendar, сохраняет нормализованные данные в MongoDB и отдаёт их через FastAPI.

> Репозиторий — форк [0niel/rtu-mirea-schedule](https://github.com/0niel/rtu-mirea-schedule), основанный на открытом проекте [RTUITLab/Schedule-RTU-API](https://github.com/RTUITLab/Schedule-RTU-API), и сохраняет исходную MIT-лицензию. Мой вклад в эту версию: переход со старого Excel-парсера на публичный `schedule-of` API и iCalendar, повторные HTTP-запросы с задержкой, безопасный литеральный поиск, атомарная публикация расписания и защищённое фоновое обновление с общим состоянием в MongoDB. [Исходный коммит с переходом на iCalendar](https://github.com/is200406moil/rtu-mirea-schedule/commit/428d84d83d5a4ac91de1c3079f8f45ee9c503bf9). Остальные API-сценарии развивались авторами исходных проектов.

## Возможности

- расписание группы по дням недели;
- список доступных групп;
- поиск занятий преподавателя;
- поиск занятий по аудитории;
- текущая учебная неделя;
- статистика запросов по группам;
- атомарное обновление кэша расписания с защищённым служебным endpoint.

## Поток данных

```mermaid
flowchart LR
    Source[Публичный schedule-of API]
    Parser[iCalendar parser]
    Mongo[(MongoDB)]
    API[FastAPI]
    Client[Клиент]

    Source --> Parser
    Parser --> Mongo
    Mongo --> API
    API --> Client
```

Технические детали и ограничения: [docs/architecture.md](docs/architecture.md).

## Стек

- Python 3.12, FastAPI, Pydantic;
- MongoDB, асинхронный API PyMongo;
- Requests с переносом блокирующих вызовов в отдельный поток;
- Docker Compose;
- Pytest, Ruff.

## Запуск

```bash
docker compose up --build
```

После запуска доступны:

- Swagger UI: <http://localhost:5000/docs>;
- OpenAPI: <http://localhost:5000/api/openapi.json>;
- healthcheck: <http://localhost:5000/health>.

MongoDB стартует вместе с приложением. Для локальной демонстрации используется служебный ключ `development-only`; при любом внешнем развёртывании задайте `SECRET_REFRESH_KEY` через окружение.

Новое расписание становится доступно только после успешной загрузки всех групп. Если источник недоступен или одна из групп не разобрана, сервис оставляет предыдущий набор данных активным. Блокировка и статус обновления хранятся в MongoDB, поэтому параллельный запуск из другого процесса также будет отклонён.

Первичное заполнение базы:

```bash
curl -X POST http://localhost:5000/api/refresh \
  -H "X-Refresh-Key: development-only"
```

Статус обновления:

```bash
curl http://localhost:5000/api/refresh/status \
  -H "X-Refresh-Key: development-only"
```

## Основные endpoints

| Метод | Путь | Назначение |
| --- | --- | --- |
| `GET` | `/api/schedule/groups` | список групп |
| `GET` | `/api/schedule/{group}/full_schedule` | расписание группы |
| `GET` | `/api/schedule/teacher/{name}` | поиск по преподавателю |
| `GET` | `/api/schedule/room/{room}` | поиск по аудитории |
| `GET` | `/api/schedule/current_week` | номер учебной недели |
| `POST` | `/api/refresh` | запуск обновления данных |
| `GET` | `/api/refresh/status` | состояние обновления |

Полный контракт с моделями ответов доступен в Swagger UI.

## Проверки

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m ruff check .
python -m ruff format --check app tests
python -m pytest --cov=app --cov-report=term-missing --cov-fail-under=70
python -m pip_audit --requirement requirements-dev.lock
```

Тесты проверяют разбор iCalendar, расчёт учебной недели, поиск, служебный endpoint, атомарную замену коллекции и распределённую блокировку. Интеграционный тест MongoDB запускается при наличии `TEST_MONGODB_URL`; в CI база поднимается автоматически.

## Ограничения

- формат парсера зависит от полей внешнего `schedule-of` API;
- обновление всех групп выполняется последовательно и может занимать время;
- блокировка обновления имеет TTL (по умолчанию один час), чтобы сервис восстановился после аварийной остановки процесса;
- проект не гарантирует актуальность данных при недоступности источника.
