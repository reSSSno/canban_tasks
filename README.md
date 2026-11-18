# Командная доска задач

Канбан для небольшой команды с обновлениями в реальном времени.

## Возможности
- Регистрация и вход, роли: владелец, участник, гость (только чтение).
- Проекты, колонки, задачи, назначение исполнителей, комментарии.
- Перетаскивание карточек между колонками, синхронизация через WebSocket.
- Еженедельные отчёты, формируемые фоновой задачей.

## Запуск
Требуются Docker и Docker Compose.

```bash
docker compose up --build
```

Откройте http://localhost:5173. Документация API: http://localhost:8000/docs.

В Docker интерфейс собирается командой `npm run build` и обслуживается Nginx. Vite dev-сервер в контейнере не запускается.

Подробности устройства приложения: [Архитектура](docs/ARCHITECTURE.md).

Первый зарегистрированный пользователь может создать проект и становится его владельцем. Владелец добавляет участников по их email. Гостям доступен только просмотр.

## Стек
React, TypeScript, Vite, FastAPI, SQLAlchemy, PostgreSQL, APScheduler, WebSocket, Docker Compose.

## Проверка
```bash
docker compose exec backend pytest -q
```



## Стиль кода

Frontend: `cd frontend && npm install && npm run format` (Prettier).

Backend: `ruff format backend/app backend/tests` и `ruff check backend/app backend/tests` (после установки Ruff).

Проверка сборки и тестов запускается в GitHub Actions при отправке изменений.
