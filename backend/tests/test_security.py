from datetime import timedelta

from sqlalchemy import select

from app.models import LoginSession, User, utcnow
from tests.conftest import create_video, login, ready_video, register


def test_registration_hashes_password_and_revokes_logout(client, db):
    user = register(client)
    stored = db.get(User, user["id"])
    assert stored.password_hash.startswith("$argon2id$")
    assert "A-good-password" not in stored.password_hash
    assert client.get("/api/auth/me").status_code == 200
    token = client.cookies["vt_session"]
    session = db.scalar(select(LoginSession))
    assert session.token_hash != token and len(session.token_hash) == 64
    assert client.post("/api/auth/logout").status_code == 204
    client.cookies.set("vt_session", token)
    assert client.get("/api/auth/me").status_code == 401


def test_csrf_and_cross_origin_rejected(client):
    register(client)
    payload = {"title": "forged"}
    assert client.post("/api/videos", json=payload, headers={"X-CSRF-Token": ""}).status_code == 403
    assert (
        client.post(
            "/api/videos", json=payload, headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )


def test_signup_cannot_choose_role(client):
    result = client.post(
        "/api/auth/register",
        json={
            "email": "evil@example.com",
            "password": "long-enough-password",
            "display_name": "Атакующий",
            "role": "admin",
        },
    )
    assert result.status_code == 422


def test_expired_session_rejected(client, db):
    register(client)
    session = db.scalar(select(LoginSession))
    session.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    assert client.get("/api/auth/me").status_code == 401


def test_private_access_covers_every_surface_and_revocation(client, db):
    register(client)
    video_id = ready_video(db, client, "private", "Секретный проект")
    register(client, "friend@example.com", "Друг")
    register(client, "stranger@example.com", "Чужой")
    for endpoint in ("", "/stream", "/thumbnail", "/comments"):
        assert client.get(f"/api/videos/{video_id}{endpoint}").status_code == 404
    assert (
        client.head(f"/api/videos/{video_id}/stream", headers={"Range": "bytes=0-1"}).status_code
        == 404
    )
    assert client.get("/api/videos?q=Секретный").json()["total"] == 0
    assert client.put(f"/api/videos/{video_id}/reaction", json={"value": 1}).status_code == 404
    assert client.patch(f"/api/videos/{video_id}", json={"title": "hijack"}).status_code == 404
    login(client, "owner@example.com")
    assert (
        client.post(
            f"/api/videos/{video_id}/grants", json={"email": "friend@example.com"}
        ).status_code
        == 201
    )
    grant_id = client.get(f"/api/videos/{video_id}/grants").json()[0]["id"]
    login(client, "friend@example.com")
    assert client.get(f"/api/videos/{video_id}/stream").content == b"0123456789"
    assert client.get("/api/videos?scope=shared").json()["total"] == 1
    assert client.get("/api/videos").json()["total"] == 0
    login(client, "owner@example.com")
    assert client.delete(f"/api/videos/{video_id}/grants/{grant_id}").status_code == 204
    login(client, "friend@example.com")
    assert (
        client.get(f"/api/videos/{video_id}/stream", headers={"Range": "bytes=0-1"}).status_code
        == 404
    )
    assert client.get(f"/api/videos/{video_id}/thumbnail").status_code == 404


def test_staff_cannot_bypass_private_access(client, db):
    register(client)
    video_id = ready_video(db, client, "private")
    staff = register(client, "staff@example.com", "Модератор")
    db.get(User, staff["id"]).role = "moderator"
    db.commit()
    assert client.get(f"/api/videos/{video_id}").status_code == 404
    assert client.get(f"/api/videos/{video_id}/stream").status_code == 404


def test_anonymous_mutations_and_owner_boundaries(client, db):
    register(client)
    video_id = create_video(client)
    register(client, "another@example.com", "Другой")
    assert client.delete(f"/api/videos/{video_id}").status_code == 404
    assert client.put(f"/api/videos/{video_id}/file", content=b"x" * 50).status_code == 404
    assert client.get(f"/api/videos/{video_id}/grants").status_code == 404
    client.post("/api/auth/logout")
    assert client.post("/api/videos", json={"title": "anon"}).status_code == 401


def test_duplicate_email_case_insensitive(client):
    register(client, "Owner@Example.com")
    result = client.post(
        "/api/auth/register",
        json={
            "email": "owner@example.com",
            "password": "another-long-password",
            "display_name": "Второй",
        },
    )
    assert result.status_code == 409


def test_login_rate_limit_counts_failed_attempts(client):
    for _ in range(15):
        assert (
            client.post(
                "/api/auth/login", json={"email": "missing@example.com", "password": "wrong"}
            ).status_code
            == 401
        )
    response = client.post(
        "/api/auth/login", json={"email": "missing@example.com", "password": "wrong"}
    )
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "900"


def test_admin_role_change_rejects_self_and_invalidates_target_session(client, db):
    admin = register(client, "admin@example.com", "Админ")
    db.get(User, admin["id"]).role = "admin"
    db.commit()
    target = register(client, "target@example.com", "Участник")
    target_token = client.cookies["vt_session"]
    assert client.get("/api/admin/users").status_code == 403
    login(client, "admin@example.com")
    assert (
        client.patch(f"/api/admin/users/{admin['id']}/role", json={"role": "user"}).status_code
        == 422
    )
    assert (
        client.patch(
            f"/api/admin/users/{target['id']}/role", json={"role": "moderator"}
        ).status_code
        == 200
    )
    client.cookies.clear()
    client.cookies.set("vt_session", target_token)
    assert client.get("/api/auth/me").status_code == 401
