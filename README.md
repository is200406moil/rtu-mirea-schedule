# RTU MIREA Schedule API

API для получения расписания учебных групп РТУ МИРЭА. Сервис читает публичный источник расписания, разбирает iCalendar, сохраняет нормализованные данные в MongoDB и отдаёт их через FastAPI.

> Репозиторий основан на открытом проекте [Mirea Ninja / Schedule-RTU-API](https://github.com/RTUITLab/Schedule-RTU-API) и сохраняет его MIT-лицензию. Мой вклад в эту версию: переход со старого Excel-парсера на публичный `schedule-of` API и iCalendar, повторные HTTP-запросы с задержкой, фоновое обновление и endpoint его статуса. [Исходный коммит с этой доработкой](https://github.com/is200406moil/rtu-mirea-schedule/commit/428d84d83d5a4ac91de1c3079f8f45ee9c503bf9). Остальные API-сценарии развивались авторами исходного проекта.

## Возможности

- расписание группы по дням недели;
- список доступных групп;
- поиск занятий преподавателя;
- поиск занятий по аудитории;
- текущая учебная неделя;
- статистика запросов по группам;
- ручное обновление кэша расписания с защищённым служебным endpoint.

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
ruff check .
pytest
```

Тесты проверяют разбор iCalendar, расчёт учебной недели и защиту служебного endpoint.

## Ограничения

- формат парсера зависит от полей внешнего `schedule-of` API;
- состояние фонового обновления хранится в памяти одного процесса;
- обновление всех групп выполняется последовательно и может занимать время;
- проект не гарантирует актуальность данных при недоступности источника.
