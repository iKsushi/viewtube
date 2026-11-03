import os
import subprocess
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from moto import mock_aws
from sqlalchemy import text

from alembic import command

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://viewtube@127.0.0.1:55432/viewtube_test"
)
if not os.environ["DATABASE_URL"].split("?")[0].endswith("_test"):
    raise RuntimeError("Tests require an isolated database whose name ends in _test")
os.environ["SECRET_KEY"] = "test-secret-key-only-for-automated-tests-123456"
os.environ["S3_ENDPOINT"] = "https://s3.amazonaws.com"
os.environ["S3_ACCESS_KEY"] = "testing"
os.environ["S3_SECRET_KEY"] = "testing"
os.environ["S3_BUCKET"] = "viewtube-test"
os.environ["APP_ORIGIN"] = "http://testserver"
os.environ["COOKIE_SECURE"] = "false"

from app.core.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services.storage import ensure_bucket, s3  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def database_schema():
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(config, "head")


@pytest.fixture(autouse=True)
def isolate(database_schema):
    with engine.begin() as conn:
        tables = ",".join('"' + table.name + '"' for table in Base.metadata.sorted_tables)
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    s3.cache_clear()
    with mock_aws():
        ensure_bucket()
        yield
    s3.cache_clear()


@pytest.fixture
def client():
    with TestClient(app) as c:
        c.headers["X-CSRF-Token"] = c.get("/api/auth/csrf").json()["csrf_token"]
        yield c


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture(scope="session")
def sample_video(tmp_path_factory):
    path = tmp_path_factory.mktemp("media") / "sample.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=0x314a72:s=320x180:r=15:d=2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=220:sample_rate=44100:duration=2",
            "-c:v",
            "libx264",
            "-threads",
            "1",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(path),
        ],
        check=True,
    )
    return path


def register(client, email="owner@example.com", name="Автор"):
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "A-good-password-2026", "display_name": name},
    )
    assert response.status_code == 201, response.text
    return response.json()


def login(client, email):
    response = client.post(
        "/api/auth/login", json={"email": email, "password": "A-good-password-2026"}
    )
    assert response.status_code == 200, response.text
    return response.json()


def create_video(client, visibility="public", title="Первое видео"):
    result = client.post("/api/videos", json={"title": title, "visibility": visibility})
    assert result.status_code == 201, result.text
    return result.json()["id"]


def ready_video(db, client, visibility="public", title="Первое видео"):
    from app.core.config import get_settings
    from app.models import Video, VideoAsset

    video_id = create_video(client, visibility, title)
    video = db.get(Video, video_id)
    video.status, video.duration = "ready", 10
    for kind, mime, data in (
        ("playback", "video/mp4", b"0123456789"),
        ("thumbnail", "image/jpeg", b"image"),
    ):
        key = f"videos/{video_id}/{kind}"
        s3().put_object(Bucket=get_settings().s3_bucket, Key=key, Body=data, ContentType=mime)
        db.add(VideoAsset(video_id=video_id, kind=kind, key=key, size=len(data), content_type=mime))
    db.commit()
    return video_id
