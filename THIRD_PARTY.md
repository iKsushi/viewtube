# Компоненты и материалы

- React / React DOM (MIT), React Router (MIT), Vite (MIT), TypeScript (Apache-2.0), Lucide (ISC).
- FastAPI (MIT), SQLAlchemy/Alembic (MIT), psycopg (LGPL-3.0), boto3 (Apache-2.0), Argon2-cffi (MIT), Pillow (HPND).
- PostgreSQL (PostgreSQL License), SeaweedFS (Apache-2.0), Caddy (Apache-2.0).
- FFmpeg с libx264 используется как внешний executable внутри образа Debian; эта сборка включает GPL-компоненты. Лицензии пакетов Debian находятся в `/usr/share/doc` контейнера. Готовые контейнеры в ZIP не распространяются, собираются из Dockerfile.
- Manrope: оригинальный шрифт из google/fonts, лицензия SIL Open Font License в `frontend/public/fonts/OFL.txt`.

Точные версии JS/Python фиксируются lock-файлами. Демо-медиа создаются Pillow и
FFmpeg при seed; внешних видеозаписей и фотографий в комплекте нет. Иконки — Lucide.
ViewTube — учебное название, продукт не связан с YouTube/Google.
