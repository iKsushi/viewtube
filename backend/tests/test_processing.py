from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from sqlalchemy import select

from app.models import ProcessingJob, Video, utcnow
from app.worker import claim_job, process_one
from tests.conftest import create_video, register


def test_real_upload_transcode_playback_journey(client, db, sample_video):
    register(client)
    video_id = create_video(client)
    response = client.put(f"/api/videos/{video_id}/file", content=sample_video.read_bytes())
    assert response.status_code == 202, response.text
    assert client.get(f"/api/videos/{video_id}").json()["status"] == "queued"
    assert process_one()
    response = client.get(f"/api/videos/{video_id}")
    assert response.json()["status"] == "ready", response.text
    assert response.json()["duration"] >= 1.9
    media = client.get(f"/api/videos/{video_id}/stream", headers={"Range": "bytes=0-100"})
    assert media.status_code == 206 and b"ftyp" in media.content
    image = client.get(f"/api/videos/{video_id}/thumbnail")
    assert image.status_code == 200 and image.content[:2] == b"\xff\xd8"
    assert client.put(f"/api/videos/{video_id}/reaction", json={"value": 1}).json()["likes"] == 1
    assert (
        client.post(
            f"/api/videos/{video_id}/comments", json={"text": "Сценарий работает"}
        ).status_code
        == 201
    )
    assert (
        client.put(f"/api/videos/{video_id}/file", content=sample_video.read_bytes()).status_code
        == 409
    )


def test_invalid_media_rejected_in_background_and_can_retry(client, db, sample_video):
    register(client)
    video_id = create_video(client)
    assert (
        client.put(f"/api/videos/{video_id}/file", content=b"not a video " * 20).status_code == 202
    )
    process_one()
    assert client.get(f"/api/videos/{video_id}").json()["status"] == "failed"
    assert client.get(f"/api/videos/{video_id}/stream").status_code == 404
    assert (
        client.put(f"/api/videos/{video_id}/file", content=sample_video.read_bytes()).status_code
        == 202
    )
    process_one()
    assert client.get(f"/api/videos/{video_id}").json()["status"] == "ready"


def test_upload_enforces_size_even_when_client_forges_content_type(client, db):
    register(client)
    video_id = create_video(client)
    response = client.put(
        f"/api/videos/{video_id}/file",
        content=b"fake",
        headers={"Content-Length": str(536870913), "Content-Type": "video/mp4"},
    )
    assert response.status_code == 413
    assert client.get(f"/api/videos/{video_id}").json()["status"] == "draft"
    assert client.put(f"/api/videos/{video_id}/file", content=b"").status_code == 422


def test_queue_claim_is_exclusive_and_expired_lease_recovers(client, db, sample_video):
    register(client)
    video_id = create_video(client)
    client.put(f"/api/videos/{video_id}/file", content=sample_video.read_bytes())
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda _: claim_job(), range(2)))
    assert sum(c is not None for c in claims) == 1
    job = db.scalar(select(ProcessingJob).where(ProcessingJob.video_id == video_id))
    old_token = job.lease_token
    job.lease_until = utcnow() - timedelta(seconds=1)
    db.commit()
    reclaimed = claim_job()
    assert reclaimed and reclaimed[3] != old_token


def test_queue_stops_after_retry_budget(client, db, sample_video):
    register(client)
    video_id = create_video(client)
    client.put(f"/api/videos/{video_id}/file", content=sample_video.read_bytes())
    job = db.scalar(select(ProcessingJob).where(ProcessingJob.video_id == video_id))
    job.attempts = 3
    db.commit()
    assert claim_job() is None
    db.expire_all()
    assert db.get(Video, video_id).status == "failed"


def test_playlist_media_cannot_fetch_network_or_local_files(client):
    register(client)
    video_id = create_video(client)
    payload = (
        b"#EXTM3U\n#EXT-X-TARGETDURATION:1\n#EXTINF:1,\nhttp://127.0.0.1:1/secret\n#EXT-X-ENDLIST\n"
    )
    assert client.put(f"/api/videos/{video_id}/file", content=payload).status_code == 202
    process_one()
    assert client.get(f"/api/videos/{video_id}").json()["status"] == "failed"
