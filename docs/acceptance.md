# Протокол проверки — 3 ноября 2026

## Среда и результаты

- Host: macOS ARM64. Python 3.12, Node 24, настоящий PostgreSQL 17.6, FFmpeg.
- Deployment: новая локальная Lima/VZ VM, Ubuntu 24.04 minimal ARM64, 3 CPU,
  4 ГБ RAM, диск 24 ГБ. Docker отсутствовал перед первым запуском скрипта.
- `bash scripts/deploy.sh --url http://localhost:18088 --demo`: успешно после
  исправления некорректной YAML-записи tmpfs. Все основные сервисы запущены,
  readiness подтверждает БД и настоящий SeaweedFS 4.52.
- `bash scripts/test.sh` внутри Ubuntu: **25 passed**, 1 предупреждение
  Starlette о будущей замене httpx в TestClient. Ошибок тестов нет.
- TypeScript + Vite production build: успешно на host и внутри Docker.
- Ruff: успешно. Bash scripts: проверка синтаксиса.
- HTTP smoke на Docker-версии: регистрация → загрузка → FFmpeg worker → Range
  playback → thumbnail → лайк → комментарий → приватность → удаление видео: PASS.
- Backup + restore синтетической установки: PASS. Проверены контрольные суммы,
  восстановление БД и S3, отзыв сессий; после восстановления smoke снова PASS.
  Изначально найденный дефект seekable() потокового tar исправлен; добавлен
  тест roundtrip двух объектов с проверкой содержимого и MIME.

## Соответствие заданию

| Требование | Реализация / доказательство |
| --- | --- |
| Лента, превью, поиск | React Feed, API `/api/videos`, поиск и pagination tests |
| Просмотр, лайки, комментарии | Watch, авторизованный stream с Range/HEAD, product/security tests |
| Канал и подписки | Channel, community API, идемпотентные subscriptions |
| Плейлисты | Создание/добавление/удаление, фильтрация скрытых и приватных записей |
| Загрузка с прогрессом | XHR progress, отмена/повтор, метаданные; браузерная загрузка успешна |
| Вход и регистрация | Auth, Argon2id, сессии; tests CSRF, rate limit, logout, expiry |
| Роли | user/moderator/admin; tests запрета эскалации и отзыва сессий |
| Приватное видео | Owner/grants; tests запрета list/detail/stream/thumb/comments для чужого и staff |
| Модерация | Жалобы, hide/restore, audit; tests deny/allow и состояние ленты |
| FastAPI + PostgreSQL | Реальная БД в тестах и контейнерах, миграция Alembic |
| Объектное хранилище | SeaweedFS, 36 демо-объектов; smoke и backup/restore с настоящим S3 |
| Фоновая обработка | Отдельный worker, durable jobs, lease/retry; concurrency и FFmpeg tests |
| Swagger | `/docs`, `/openapi.json`, описание CSRF |
| Одна команда Ubuntu | Docker bootstrap, сборка, миграции, S3, seed, healthcheck |
| Демо | 7 пользователей, 12 видео, комментарии, подписки, плейлист, жалоба |
| Git, диалог, обвязка | Полный `.git`, последовательные коммиты, исходный JSONL, снимки правил/skills |

## Браузерная проверка

Встроенный Chromium: desktop 1440×900 и узкий экран 359px. Проверены лента,
переход к видео, вход, отправка комментария, воспроизведение, загрузка синтетического
MP4 и переход в студию со статусом «Опубликовано», открытие загруженного видео,
диалог сохранения в плейлист и переход к созданию. На desktop проверяется
сворачивание sidebar; mobile — перенос элементов и отсутствие горизонтального
переполнения. Резервные данные и приватные API проверены автотестами.

## Не проверено / не заявляется

Публичный домен, ACME в интернете, внешняя VM x86_64, физические iOS/Android
устройства, Safari/Firefox, высокая нагрузка и 2-часовое видео максимального
размера. Проверка безопасности — целевые тесты и анализ кода, не независимый
pentest. На момент исходной проверки browser E2E suite не был включён; HTTP smoke воспроизводим,
а браузерные проверки записаны в нативном журнале. Интеграционные тесты используют
реальную PostgreSQL и FFmpeg, но moto вместо S3; настоящий SeaweedFS дополнительно
проверен сквозным smoke и восстановлением.

## Повторная проверка после добавления процедуры приёмки

3 ноября 2026: TypeScript/Vite production build PASS в Ubuntu ARM64;
backend 25 passed (4.14 s), HTTP smoke с настоящим S3/worker PASS.
Тест упаковщика: два разрешённых JSONL сохраняются побайтно, чужой ID и
дубликат отклоняются. Ruff и синтаксис shell/JavaScript PASS.
При переносе tar из macOS выявлены AppleDouble `._*`: Alembic читал их
как миграции. Служебные файлы удалены из тестовой копии; Docker ignore
дополнен исключением. Повторный прогон после удаления прошёл.

Новый Playwright E2E: Firefox PASS и WebKit PASS (реальное воспроизведение,
лайк, комментарий, reload, ширина 359px). Chromium в Linux ARM64-образе
не поддерживает H.264: canPlayType возвращает пустую строку, VP9 — probably;
оба режима Chromium завершались NotSupportedError. Теперь отсутствие кодека
явно помечается SKIP до создания данных. Это НЕ PASS Chrome; нужен прогон
на браузерной сборке с H.264. WebKit также не заменяет физический Safari.

## Расширенные проверки 3 ноября 2026

- Настоящий установленный Google Chrome на macOS: полный E2E PASS, повторно
  после исправлений — 1 passed (6.5 s), реальный H.264 и сохранение действий.
- Настоящий Safari через штатный safaridriver: регистрация, загрузка,
  воспроизведение, лайк, комментарий и reload PASS после включения пользователем
  Allow remote automation. Это отдельная проверка от Playwright WebKit.
- Реальный MP4 536870912 байт через Caddy/S3/worker: PASS (28.1 s).
- Ровно 7200 секунд: ready, длительность результата и превью PASS (6.1 s).
- 7201 секунда: failed и stream 404 PASS (3.1 s). Ролики 32×32/1 fps;
  это граничная проверка, не нагрузочный тест двухчасового 4K.
- Найдены и исправлены: 513MB у Caddy меньше 512 МиБ приложения; лимит
  прокси теперь задан байтами. SeaweedFS при multipart превысил 768 МиБ
  (OOM подтверждён ядром): установлен GOMEMLIMIT=512MiB, S3 concurrency=2.
- После изменений backend: 25 passed (3.30 s).

### Чистая Ubuntu x86_64

Отдельная QEMU 11.1.3 VM под Lima 2.2.1 на macOS ARM64, 2 vCPU, 4 ГиБ,
диск 24 ГиБ. Ubuntu minimal 24.04 amd64 release-20261103, SHA-256
`bc9237bfdfa42b5f9a4404b6c6cab595d3e57599c6498f6664ad00e6192f9595`.
Источник: https://cloud-images.ubuntu.com/minimal/releases/noble/release-20261103/
Docker перед запуском отсутствовал. Проверен commit 91d496c.

- `bash scripts/ubuntu-x86-check.sh`: этап deploy --demo PASS; все 12
  демо-роликов созданы, API/web healthy.
- Backend: 25 passed, 1 warning, 81.97 s.
- Реальный HTTP smoke с S3/worker/private isolation: PASS.
- Тест упаковщика в новой VM: PASS.
- На 3 ноября вся acceptance-команда НЕ PASS: browser stage остановился на скачивании
  Microsoft Playwright image (сначала DNS, затем зависший повторный download).
  Browser E2E внутри этой x86_64 VM не запускался. VM выключена после
  сохранения локальных логов в .runtime/x86.

Это полноценная x86_64 гостевая ОС, но CPU эмулируется на ARM; результаты
не являются замером производительности физического x86_64 сервера.
Настоящие Chrome 156.0.8078.80 и Safari 27.2 проверены отдельно на macOS ARM64.

## Продолжение x86_64 проверки — 11 ноября 2026

Возобновлена та же Ubuntu VM; приложение из 91d496c, исходники host 8ede1e8.
Образ `mcr.microsoft.com/playwright:v1.56.1-noble` скачан после двух ограниченных
по времени попыток. Digest:
`sha256:f1e7e01021efd65dd1a2c56064be399f3e4de00fd021ac561325f2bfbb2b837a`.
Сборка `viewtube-e2e:local` и запуск `bash scripts/e2e.sh` состоялись:

- Firefox: **PASS**, полный сценарий, 2.2 минуты.
- Chromium: **SKIP**, сборка без H.264; не считается успешной проверкой.
- WebKit: **FAIL**, после reload не найден лайк за стандартные 5 секунд.
  Сохранённый снимок страницы уже содержит активный лайк и комментарий.
  Ожидание сохранённого лайка увеличено до 30 секунд в `e2e/journey.spec.js`.
- Повтор только WebKit с этой правкой: общий timeout 180 секунд на выборе файла.
- Последний повтор с `--timeout=600000`: **FAIL**, за 5 секунд не появилось
  сообщение «Готовим ваше видео к просмотру» после загрузки. API подтвердил
  создание видео (201) и приём файла (202). Снимок после ошибки уже содержит
  нужный заголовок и ссылку в студию. Это не доказывает причину задержки;
  предположение о влиянии эмуляции не заменяет успешный прогон.

Для повторения WebKit после `scripts/e2e.sh` и пересборки образа:

```bash
docker build -t viewtube-e2e:local e2e
docker run --rm --network host --ipc=host \
  -e E2E_BASE_URL=http://localhost:8080 \
  -v "$PWD/.runtime/e2e-media:/media:ro" \
  -v "$PWD/.runtime/e2e-results-webkit:/tests/test-results" \
  viewtube-e2e:local npx playwright test --project webkit --timeout=600000
```

Порт соответствует этой VM; для другой установки использовать APP_ORIGIN.
Последние повторы использовали bind mount изменённого journey.spec.js поверх
того же образа. Локальные логи и traces сохранены в
`.runtime/x86/browser-evidence-20261111.tar.gz` (не входят в Git/архив сдачи).
VM выключена после сохранения диагностики.
Тест упаковщика PASS, `git diff --check` PASS. Полная acceptance-команда всё
ещё НЕ PASS: сетевой блокер снят, WebKit на x86_64 требует дальнейшей проверки.
Предыдущие успешные Chrome/Safari на macOS и WebKit на ARM64 сохраняются как
отдельные результаты, а не подмена x86_64 проверки.
