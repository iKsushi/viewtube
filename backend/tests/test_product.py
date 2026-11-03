from sqlalchemy import select

from app.models import AuditEvent, User
from tests.conftest import login, ready_video, register


def test_range_requests_and_head(client, db):
    register(client)
    video_id = ready_video(db, client)
    url = f"/api/videos/{video_id}/stream"
    for header, expected, content_range in (
        ("bytes=2-5", b"2345", "bytes 2-5/10"),
        ("bytes=-3", b"789", "bytes 7-9/10"),
        ("bytes=8-", b"89", "bytes 8-9/10"),
    ):
        response = client.get(url, headers={"Range": header})
        assert response.status_code == 206
        assert response.content == expected
        assert response.headers["Content-Range"] == content_range
        assert response.headers["Cache-Control"] == "private, no-store"
    for invalid in ("bytes=10-20", "bytes=3-1", "bytes=-0", "bytes=1-2,4-6", "bytes=-", "wrong"):
        assert client.get(url, headers={"Range": invalid}).status_code == 416
    head = client.head(url)
    assert (
        head.status_code == 200 and head.content == b"" and head.headers["Content-Length"] == "10"
    )


def test_reactions_idempotent_views_deduplicated_comments(client, db):
    register(client)
    video_id = ready_video(db, client)
    base = f"/api/videos/{video_id}"
    for _ in range(2):
        assert client.put(base + "/reaction", json={"value": 1}).json()["likes"] == 1
        assert client.post(base + "/view", json={"position": 2}).status_code == 204
    assert client.get(base).json()["views"] == 1
    assert client.get("/api/videos?scope=history").json()["items"][0]["position"] == 2
    assert client.get("/api/videos?scope=liked").json()["total"] == 1
    assert client.put(base + "/reaction", json={"value": -1}).json()["likes"] == 0
    assert client.put(base + "/reaction", json={"value": 0}).json()["reaction"] == 0
    c = client.post(base + "/comments", json={"text": "<script>alert(1)</script>"})
    assert c.status_code == 201
    assert client.get(base + "/comments").json()[0]["text"] == "<script>alert(1)</script>"
    register(client, "stranger@example.com", "Другой")
    assert client.delete(base + "/comments/" + c.json()["id"]).status_code == 403


def test_subscription_idempotent_and_feed(client, db):
    author = register(client)
    ready_video(db, client)
    assert client.put(f"/api/channels/{author['channel_id']}/subscription").status_code == 422
    register(client, "viewer@example.com", "Зритель")
    for _ in range(2):
        assert (
            client.put(f"/api/channels/{author['channel_id']}/subscription").json()["subscribers"]
            == 1
        )
    assert client.get("/api/videos?scope=subscriptions").json()["total"] == 1
    client.delete(f"/api/channels/{author['channel_id']}/subscription")
    assert client.get("/api/videos?scope=subscriptions").json()["total"] == 0


def test_public_playlist_filters_private_metadata(client, db):
    author = register(client)
    public = ready_video(db, client)
    secret = ready_video(db, client, "private", "Never leak title")
    playlist = client.post("/api/playlists", json={"title": "Collection"}).json()
    for video_id in (public, secret, public):
        assert client.put(f"/api/playlists/{playlist['id']}/videos/{video_id}").status_code == 200
    assert len(client.get(f"/api/playlists/{playlist['id']}").json()["videos"]) == 2
    client.post("/api/auth/logout")
    result = client.get(f"/api/playlists/{playlist['id']}").json()
    assert len(result["videos"]) == 1 and result["videos"][0]["id"] == public
    assert "Never leak title" not in str(
        client.get(f"/api/channels/{author['channel_id']}/playlists").json()
    )


def test_private_playlist_and_cross_owner_writes(client, db):
    register(client)
    video_id = ready_video(db, client)
    playlist_id = client.post(
        "/api/playlists", json={"title": "Private list", "visibility": "private"}
    ).json()["id"]
    register(client, "other@example.com", "Другой")
    assert client.get(f"/api/playlists/{playlist_id}").status_code == 404
    assert client.put(f"/api/playlists/{playlist_id}/videos/{video_id}").status_code == 404
    assert client.delete(f"/api/playlists/{playlist_id}").status_code == 404


def test_moderation_hides_all_surfaces_and_audits(client, db):
    register(client)
    video_id = ready_video(db, client)
    viewer = register(client, "viewer@example.com", "Зритель")
    base = f"/api/videos/{video_id}"
    report = client.post(base + "/reports", json={"reason": "Нарушение правил сообщества"})
    assert report.status_code == 201
    assert client.post(base + "/reports", json={"reason": "Повторная жалоба"}).status_code == 409
    assert client.get("/api/moderation/reports").status_code == 403
    db.get(User, viewer["id"]).role = "moderator"
    db.commit()
    result = client.post(
        f"/api/moderation/reports/{report.json()['id']}/resolve",
        json={"action": "hide", "reason": "Подтверждено нарушение"},
    )
    assert result.status_code == 200
    assert client.get("/api/videos").json()["total"] == 0
    for endpoint in ("", "/stream", "/thumbnail", "/comments"):
        assert client.get(base + endpoint).status_code == 404
    assert db.scalar(select(AuditEvent).where(AuditEvent.action == "moderation.hide"))
    assert (
        client.post(
            f"/api/moderation/reports/{report.json()['id']}/resolve",
            json={"action": "dismiss", "reason": "Повторное решение"},
        ).status_code
        == 409
    )
    assert client.post(f"/api/moderation/videos/{video_id}/restore").status_code == 200
    assert client.get(base + "/stream").status_code == 200
    login(client, "owner@example.com")
    assert client.get(base).status_code == 200


def test_title_search_literal_wildcard_and_pagination(client, db):
    register(client)
    ready_video(db, client, title="100% успех")
    ready_video(db, client, title="Другой сюжет")
    result = client.get("/api/videos", params={"q": "%"}).json()
    assert result["total"] == 1
    assert client.get("/api/videos?limit=1&page=2").json()["total"] == 2
    assert client.get("/api/videos?limit=1000").status_code == 422
    assert client.get("/api/videos?page=0").status_code == 422


def test_delete_cascades_comments_reactions_and_assets(client, db):
    register(client)
    video_id = ready_video(db, client)
    client.put(f"/api/videos/{video_id}/reaction", json={"value": 1})
    client.post(f"/api/videos/{video_id}/comments", json={"text": "Комментарий"})
    assert client.delete(f"/api/videos/{video_id}").status_code == 204
    assert client.get(f"/api/videos/{video_id}/stream").status_code == 404
    from app.models import Comment, Reaction, VideoAsset

    for model in (Comment, Reaction, VideoAsset):
        assert db.scalar(select(model).where(model.video_id == video_id)) is None
