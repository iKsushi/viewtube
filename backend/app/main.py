import hmac
import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api import auth, community, videos
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.schemas import CATEGORIES
from app.services.storage import s3

app = FastAPI(
    title="ViewTube API",
    version="1.0.0",
    description="Видео, каналы и приватный доступ. Для изменяющих запросов получите /api/auth/csrf и передайте X-CSRF-Token.",
)
log = logging.getLogger("viewtube")


@app.middleware("http")
async def security(request: Request, call_next):
    settings = get_settings()
    request_id = str(uuid.uuid4())
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        cookie = request.cookies.get("vt_csrf", "")
        header = request.headers.get("x-csrf-token", "")
        origin = request.headers.get("origin")
        if (
            (origin and origin != settings.app_origin)
            or not cookie
            or not hmac.compare_digest(cookie, header)
        ):
            return JSONResponse(
                {"detail": "Обновите страницу и повторите действие", "request_id": request_id},
                status_code=403,
            )
    try:
        response = await call_next(request)
    except Exception:
        log.exception("request_failed request_id=%s path=%s", request_id, request.url.path)
        response = JSONResponse(
            {"detail": "Не удалось выполнить запрос. Попробуйте позже.", "request_id": request_id},
            status_code=500,
        )
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "DENY"
    if request.url.path.startswith("/api"):
        response.headers.setdefault("Cache-Control", "private, no-store")
    return response


@app.get("/api/health", tags=["Operations"])
def health():
    return {"status": "ok"}


@app.get("/api/ready", tags=["Operations"])
def ready():
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1 FROM alembic_version"))
        s3().head_bucket(Bucket=get_settings().s3_bucket)
        return {"status": "ready"}
    except (SQLAlchemyError, Exception):
        return JSONResponse({"status": "unavailable"}, status_code=503)


@app.get("/api/config", tags=["Configuration"])
def config():
    return {"categories": CATEGORIES, "max_upload_bytes": get_settings().max_upload_bytes}


app.include_router(auth.router, prefix="/api")
app.include_router(videos.router, prefix="/api")
app.include_router(community.router, prefix="/api")
