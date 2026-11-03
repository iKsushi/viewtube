"""Initialize private storage and the first administrator, without resetting passwords."""

import os
import time

from sqlalchemy import select, text

from app.core.db import SessionLocal
from app.core.security import password_hasher
from app.models import Channel, User
from app.services.storage import ensure_bucket


def main():
    for attempt in range(60):
        try:
            ensure_bucket()
            break
        except Exception:
            if attempt == 59:
                raise
            time.sleep(2)
    email = os.environ["ADMIN_EMAIL"].lower()
    password = os.environ["ADMIN_PASSWORD"]
    if len(password) < 12:
        raise RuntimeError("Administrator password must have at least 12 characters")
    with SessionLocal() as db:
        db.execute(text("SELECT pg_advisory_xact_lock(20261104)"))
        user = db.scalar(select(User).where(User.email == email))
        if not user:
            user = User(
                email=email,
                password_hash=password_hasher.hash(password),
                display_name="Администратор",
                role="admin",
            )
            db.add(user)
            db.flush()
            db.add(Channel(user_id=user.id, name=user.display_name, handle="admin-" + user.id[:10]))
            db.commit()
    print("Private storage and administrator ready; existing credentials unchanged.")


if __name__ == "__main__":
    main()
