import hashlib
import hmac
import secrets
import time
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.models import LoginSession, RateBucket, User, utcnow

password_hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
DUMMY_HASH = password_hasher.hash(secrets.token_urlsafe(32))


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def verify_password(password: str, encoded: str) -> bool:
    try:
        return password_hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    token = request.cookies.get("vt_session")
    if not token:
        return None
    return db.scalar(
        select(User)
        .join(LoginSession)
        .where(
            LoginSession.token_hash == token_hash(token),
            LoginSession.expires_at > utcnow(),
            User.disabled.is_(False),
        )
    )


def current_user(user: User | None = Depends(optional_user)) -> User:
    if not user:
        raise HTTPException(401, "Войдите в аккаунт")
    return user


def staff_user(user: User = Depends(current_user)) -> User:
    if user.role not in ("moderator", "admin"):
        raise HTTPException(403, "Недостаточно прав")
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Требуется роль администратора")
    return user


def start_session(db: Session, user: User, response: Response):
    token = secrets.token_urlsafe(48)
    settings = get_settings()
    db.add(
        LoginSession(
            user_id=user.id,
            token_hash=token_hash(token),
            expires_at=utcnow() + timedelta(days=settings.session_days),
        )
    )
    response.set_cookie(
        "vt_session",
        token,
        max_age=settings.session_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def client_key(request: Request) -> str:
    # Reverse proxy sanitizes forwarded headers; never trust user-supplied X-Forwarded-For here.
    value = request.client.host if request.client else "unknown"
    return hmac.new(get_settings().secret_key.encode(), value.encode(), hashlib.sha256).hexdigest()


def rate_limit(db: Session, key: str, limit: int, seconds: int = 60):
    window = int(time.time()) // seconds
    stmt = insert(RateBucket).values(key=key, window=window, count=1)
    stmt = stmt.on_conflict_do_update(
        index_elements=[RateBucket.key],
        set_={
            "window": window,
            "count": __import__("sqlalchemy").case(
                (RateBucket.window == window, RateBucket.count + 1), else_=1
            ),
        },
    ).returning(RateBucket.count)
    count = db.scalar(stmt)
    # Separate commit makes failed login attempts count too. Call before other writes.
    db.commit()
    if count > limit:
        raise HTTPException(
            429, "Слишком много запросов. Попробуйте позже.", headers={"Retry-After": str(seconds)}
        )
