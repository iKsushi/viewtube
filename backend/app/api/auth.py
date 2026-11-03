import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import (
    DUMMY_HASH,
    client_key,
    current_user,
    password_hasher,
    rate_limit,
    start_session,
    token_hash,
    verify_password,
)
from app.models import Channel, LoginSession, User
from app.schemas import Login, Register
from app.services.presenters import user_dict

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/csrf")
def csrf(request: Request, response: Response):
    token = request.cookies.get("vt_csrf") or secrets.token_urlsafe(32)
    response.set_cookie(
        "vt_csrf",
        token,
        secure=get_settings().cookie_secure,
        samesite="strict",
        httponly=True,
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return {"csrf_token": token}


@router.post("/register", status_code=201)
def register(data: Register, request: Request, response: Response, db: Session = Depends(get_db)):
    rate_limit(db, "register:" + client_key(request), 10, 3600)
    user = User(
        email=str(data.email).lower(),
        display_name=data.display_name,
        password_hash=password_hasher.hash(data.password),
    )
    db.add(user)
    try:
        db.flush()
        db.add(Channel(user_id=user.id, name=user.display_name, handle="user-" + user.id[:12]))
        start_session(db, user, response)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Не удалось зарегистрировать этот адрес") from None
    return user_dict(db, user)


@router.post("/login")
def login(data: Login, request: Request, response: Response, db: Session = Depends(get_db)):
    rate_limit(db, "login-ip:" + client_key(request), 30, 900)
    rate_limit(db, "login-user:" + token_hash(str(data.email).lower()), 15, 900)
    user = db.scalar(select(User).where(User.email == str(data.email).lower()))
    valid = verify_password(data.password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid or user.disabled:
        raise HTTPException(401, "Неверный email или пароль")
    old = request.cookies.get("vt_session")
    if old:
        db.execute(delete(LoginSession).where(LoginSession.token_hash == token_hash(old)))
    start_session(db, user, response)
    db.commit()
    return user_dict(db, user)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get("vt_session", "")
    db.execute(delete(LoginSession).where(LoginSession.token_hash == token_hash(token)))
    db.commit()
    response.delete_cookie("vt_session", path="/")


@router.get("/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return user_dict(db, user)
