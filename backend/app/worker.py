import json
import logging
import signal
import subprocess
import tempfile
import time
from datetime import timedelta
from pathlib import Path

from sqlalchemy import delete, or_, select

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models import LoginSession, ProcessingJob, RateBucket, Video, VideoAsset, new_id, utcnow
from app.services.storage import remove, s3, upload

log = logging.getLogger("viewtube.worker")
FORMATS = "mov,matroska,webm,avi,ogg,mpegts"


def command(args, timeout):
    try:
        return subprocess.run(args, check=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise ValueError("Превышено время обработки видео") from None
    except subprocess.CalledProcessError:
        raise ValueError("Не удалось прочитать видео. Используйте MP4, MOV или WebM.") from None


def transcode(source: Path, destination: Path, thumbnail: Path):
    settings = get_settings()
    data = json.loads(
        command(
            [
                "ffprobe",
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-format_whitelist",
                FORMATS,
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(source),
            ],
            30,
        ).stdout
    )
    stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    duration = float(data.get("format", {}).get("duration", 0))
    if not stream or not (0 < duration <= settings.max_duration_seconds):
        raise ValueError("Нужно видео длительностью от 1 секунды до 2 часов")
    if max(stream.get("width", 0), stream.get("height", 0)) > 8192:
        raise ValueError("Разрешение видео превышает 8K")
    command(
        [
            "ffmpeg",
            "-y",
            "-nostdin",
            "-v",
            "error",
            "-threads",
            "2",
            "-protocol_whitelist",
            "file,pipe",
            "-format_whitelist",
            FORMATS,
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-map_metadata",
            "-1",
            "-sn",
            "-dn",
            "-vf",
            "scale=w='min(1280,iw)':h='min(720,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1",
            "-r",
            "30",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-maxrate",
            "2M",
            "-bufsize",
            "4M",
            "-threads",
            "2",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            str(destination),
        ],
        settings.worker_timeout_seconds,
    )
    command(
        [
            "ffmpeg",
            "-y",
            "-nostdin",
            "-v",
            "error",
            "-ss",
            str(min(1, duration / 3)),
            "-i",
            str(destination),
            "-frames:v",
            "1",
            "-vf",
            "scale=640:-2",
            str(thumbnail),
        ],
        60,
    )
    return duration


def claim_job():
    settings = get_settings()
    with SessionLocal() as db:
        job = db.scalar(
            select(ProcessingJob)
            .where(
                or_(
                    ProcessingJob.state == "pending",
                    (ProcessingJob.state == "running") & (ProcessingJob.lease_until < utcnow()),
                )
            )
            .order_by(ProcessingJob.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not job:
            return None
        video = db.get(Video, job.video_id)
        if job.attempts >= settings.worker_max_attempts:
            job.state, video.status = "failed", "failed"
            video.error = "Обработка не завершилась. Загрузите файл повторно."
            db.commit()
            return None
        token = new_id()
        job.state, job.lease_token = "running", token
        job.lease_until = utcnow() + timedelta(seconds=settings.worker_timeout_seconds + 180)
        job.attempts += 1
        video.status, video.updated_at = "processing", utcnow()
        source = db.scalar(
            select(VideoAsset).where(VideoAsset.video_id == video.id, VideoAsset.kind == "source")
        )
        db.commit()
        return job.id, video.id, source.key if source else None, token


def process_one():
    claim = claim_job()
    if not claim:
        return False
    job_id, video_id, source_key, token = claim
    uploaded = []
    try:
        if not source_key:
            raise ValueError("Исходный файл отсутствует. Повторите загрузку.")
        with tempfile.TemporaryDirectory(prefix="viewtube-worker-") as temp:
            source, playback, thumbnail = (
                Path(temp) / n for n in ("source", "video.mp4", "thumbnail.jpg")
            )
            s3().download_file(get_settings().s3_bucket, source_key, str(source))
            duration = transcode(source, playback, thumbnail)
            assets = []
            for kind, path, mime in (
                ("playback", playback, "video/mp4"),
                ("thumbnail", thumbnail, "image/jpeg"),
            ):
                key = f"videos/{video_id}/{token}/{path.name}"
                upload(path, key, mime)
                uploaded.append(key)
                assets.append(
                    VideoAsset(
                        video_id=video_id,
                        kind=kind,
                        key=key,
                        size=path.stat().st_size,
                        content_type=mime,
                    )
                )
            with SessionLocal() as db:
                job = db.scalar(
                    select(ProcessingJob).where(ProcessingJob.id == job_id).with_for_update()
                )
                if not job or job.lease_token != token:
                    raise ValueError("Задание уже передано другому обработчику")
                video = db.get(Video, video_id)
                old_keys = list(
                    db.scalars(
                        select(VideoAsset.key).where(
                            VideoAsset.video_id == video_id, VideoAsset.kind != "source"
                        )
                    )
                )
                db.execute(
                    delete(VideoAsset).where(
                        VideoAsset.video_id == video_id, VideoAsset.kind != "source"
                    )
                )
                db.add_all(assets)
                video.status, video.duration, video.error, video.updated_at = (
                    "ready",
                    duration,
                    None,
                    utcnow(),
                )
                job.state, job.error, job.lease_until = "done", None, None
                db.commit()
            uploaded.clear()  # Database now owns these objects.
            for key in old_keys:
                try:
                    remove(key)
                except Exception:
                    log.warning("stale_asset_cleanup_failed video=%s", video_id)
        log.info("video_ready video=%s", video_id)
    except Exception as exc:
        public_error = (
            str(exc)
            if isinstance(exc, ValueError)
            else "Хранилище недоступно. Обработка будет повторена."
        )
        log.warning("processing_failed video=%s type=%s", video_id, type(exc).__name__)
        for key in uploaded:
            try:
                remove(key)
            except Exception:
                pass
        with SessionLocal() as db:
            job = db.scalar(
                select(ProcessingJob).where(ProcessingJob.id == job_id).with_for_update()
            )
            if job and job.lease_token == token:
                permanent = (
                    isinstance(exc, ValueError)
                    or job.attempts >= get_settings().worker_max_attempts
                )
                job.state, job.error = ("failed" if permanent else "pending"), public_error[:250]
                video = db.get(Video, video_id)
                video.status, video.error = (
                    ("failed" if permanent else "queued"),
                    public_error[:250],
                )
                db.commit()
    return True


def main():
    logging.basicConfig(level=logging.INFO)
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    cleanup_at = 0
    while not stopping:
        try:
            if time.monotonic() > cleanup_at:
                with SessionLocal() as db:
                    db.execute(delete(LoginSession).where(LoginSession.expires_at < utcnow()))
                    # Windows use seconds=60/900/3600; retain conservatively for 2 days.
                    db.execute(
                        delete(RateBucket).where(RateBucket.window < int(time.time()) // 3600 - 48)
                    )
                    db.commit()
                cleanup_at = time.monotonic() + 3600
            if not process_one():
                time.sleep(2)
        except Exception:
            log.exception("worker_iteration_failed")
            time.sleep(5)


if __name__ == "__main__":
    main()
