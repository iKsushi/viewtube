import hashlib
import hmac
import re
import tempfile
from datetime import timedelta
from pathlib import Path
from typing import Literal

from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, exists, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import client_key, current_user, optional_user, rate_limit
from app.models import (
    AuditEvent,
    Channel,
    Comment,
    ProcessingJob,
    Reaction,
    Report,
    Subscription,
    User,
    Video,
    VideoAsset,
    VideoGrant,
    ViewEvent,
    WatchHistory,
    new_id,
    utcnow,
)
from app.schemas import (
    CATEGORIES,
    CommentInput,
    GrantInput,
    ReactionInput,
    ReportInput,
    VideoInput,
    WatchInput,
)
from app.services.access import readable_filter, require_video
from app.services.presenters import videos_dict
from app.services.storage import remove, s3, upload

router = APIRouter(prefix="/videos", tags=["Videos"])


@router.get("")
def list_videos(
    q: str = Query("", max_length=150),
    category: str | None = None,
    scope: Literal["public", "subscriptions", "liked", "history", "mine", "shared"] = "public",
    sort: Literal["new", "popular"] = "new",
    channel_id: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(18, ge=1, le=48),
    user: User | None = Depends(optional_user),
    db: Session = Depends(get_db),
):
    if scope != "public" and not user:
        raise HTTPException(401, "Войдите в аккаунт")
    stmt = select(Video)
    if scope == "mine":
        stmt = stmt.where(Video.channel.has(user_id=user.id))
    else:
        stmt = stmt.where(readable_filter(user))
        if scope == "public":
            stmt = stmt.where(Video.visibility == "public")
        elif scope == "subscriptions":
            stmt = stmt.where(
                exists(
                    select(Subscription.id).where(
                        Subscription.user_id == user.id, Subscription.channel_id == Video.channel_id
                    )
                )
            )
        elif scope == "liked":
            stmt = stmt.where(
                exists(
                    select(Reaction.id).where(
                        Reaction.user_id == user.id,
                        Reaction.video_id == Video.id,
                        Reaction.value == 1,
                    )
                )
            )
        elif scope == "history":
            stmt = stmt.join(WatchHistory).where(WatchHistory.user_id == user.id)
        elif scope == "shared":
            stmt = stmt.where(
                Video.visibility == "private",
                exists(
                    select(VideoGrant.id).where(
                        VideoGrant.video_id == Video.id, VideoGrant.user_id == user.id
                    )
                ),
            )
    if q:
        stmt = stmt.where(
            Video.title.ilike(
                "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%",
                escape="\\",
            )
        )
    if category and category in CATEGORIES:
        stmt = stmt.where(Video.category == category)
    if channel_id:
        stmt = stmt.where(Video.channel_id == channel_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    order = (
        WatchHistory.watched_at.desc()
        if scope == "history"
        else (Video.views.desc() if sort == "popular" else Video.created_at.desc())
    )
    videos = list(
        db.scalars(stmt.order_by(order, Video.id).offset((page - 1) * limit).limit(limit))
    )
    return {"items": videos_dict(db, videos, user), "total": total, "page": page, "limit": limit}


@router.post("", status_code=201)
def create_video(
    data: VideoInput, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    rate_limit(db, "create-video:" + user.id, 30, 3600)
    channel = db.scalar(select(Channel).where(Channel.user_id == user.id))
    video = Video(channel_id=channel.id, **data.model_dump())
    db.add(video)
    db.commit()
    return videos_dict(db, [video], user)[0]


@router.get("/{video_id}")
def get_video(
    video_id: str, user: User | None = Depends(optional_user), db: Session = Depends(get_db)
):
    return videos_dict(db, [require_video(db, video_id, user)], user)[0]


@router.patch("/{video_id}")
def edit_video(
    video_id: str,
    data: VideoInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    video = require_video(db, video_id, user, owner=True)
    for key, value in data.model_dump().items():
        setattr(video, key, value)
    video.updated_at = utcnow()
    db.commit()
    return videos_dict(db, [video], user)[0]


@router.put("/{video_id}/file", status_code=202)
async def upload_video(
    video_id: str,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    rate_limit(db, "upload:" + user.id, 20, 3600)
    require_video(db, video_id, user, owner=True)
    video = db.scalar(select(Video).where(Video.id == video_id).with_for_update(of=Video))
    stale = video.status == "uploading" and video.updated_at < utcnow() - timedelta(hours=2)
    if video.status not in ("draft", "failed") and not stale:
        raise HTTPException(409, "Файл уже загружается или обрабатывается")
    try:
        declared_size = int(request.headers.get("content-length", "0"))
    except ValueError:
        raise HTTPException(400, "Некорректный размер файла") from None
    if declared_size > settings.max_upload_bytes:
        raise HTTPException(413, "Файл превышает лимит 512 МБ")
    video.status, video.error, video.updated_at = "uploading", None, utcnow()
    db.commit()
    key = f"videos/{video.id}/source-{new_id()}"
    stored = False
    try:
        with tempfile.TemporaryDirectory(prefix="viewtube-upload-") as temp:
            path = Path(temp) / "source"
            size = 0
            with path.open("wb") as output:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > settings.max_upload_bytes:
                        raise HTTPException(413, "Файл превышает лимит 512 МБ")
                    output.write(chunk)
            if size < 32:
                raise HTTPException(422, "Файл пустой или повреждён")
            await run_in_threadpool(upload, path, key, "application/octet-stream")
            stored = True
        old_asset = db.scalar(
            select(VideoAsset).where(VideoAsset.video_id == video.id, VideoAsset.kind == "source")
        )
        if old_asset:
            await run_in_threadpool(remove, old_asset.key)
            db.delete(old_asset)
            db.flush()
        db.add(
            VideoAsset(
                video_id=video.id,
                kind="source",
                key=key,
                size=size,
                content_type="application/octet-stream",
            )
        )
        job = db.scalar(select(ProcessingJob).where(ProcessingJob.video_id == video.id))
        if job:
            job.state, job.attempts, job.error, job.lease_until = "pending", 0, None, None
        else:
            db.add(ProcessingJob(video_id=video.id))
        video.status, video.updated_at = "queued", utcnow()
        db.commit()
        return {"id": video.id, "status": video.status}
    except BaseException:
        db.rollback()
        db.execute(
            update(Video)
            .where(Video.id == video_id)
            .values(status="failed", error="Загрузка прервана. Повторите её.")
        )
        db.commit()
        if stored:
            await run_in_threadpool(remove, key)
        raise


@router.delete("/{video_id}", status_code=204)
def delete_video(video_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    video = require_video(db, video_id, user, owner=True)
    video = db.scalar(select(Video).where(Video.id == video_id).with_for_update(of=Video))
    if video.status in ("uploading", "processing", "queued"):
        raise HTTPException(409, "Дождитесь завершения обработки")
    # Hide first so partial S3 failure cannot leave a playable broken public entry.
    video.hidden = True
    db.commit()
    for asset in db.scalars(select(VideoAsset).where(VideoAsset.video_id == video.id)):
        remove(asset.key)
    db.add(AuditEvent(actor_id=user.id, action="video.delete", target_id=video.id))
    db.delete(video)
    db.commit()


def media_response(video_id, kind, request, user, db):
    require_video(db, video_id, user, media=True)
    asset = db.scalar(
        select(VideoAsset).where(VideoAsset.video_id == video_id, VideoAsset.kind == kind)
    )
    if not asset:
        raise HTTPException(404, "Файл недоступен")
    args = {"Bucket": get_settings().s3_bucket, "Key": asset.key}
    headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
    }
    status, length = 200, asset.size
    value = request.headers.get("range")
    if value:
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", value)
        if not match or not any(match.groups()):
            raise HTTPException(
                416, "Некорректный диапазон", headers={"Content-Range": f"bytes */{asset.size}"}
            )
        first, last = match.groups()
        if first:
            start = int(first)
            end = min(int(last), asset.size - 1) if last else asset.size - 1
        else:
            start, end = max(0, asset.size - int(last)), asset.size - 1
        if start > end or start >= asset.size:
            raise HTTPException(
                416, "Диапазон вне файла", headers={"Content-Range": f"bytes */{asset.size}"}
            )
        args["Range"] = f"bytes={start}-{end}"
        headers["Content-Range"] = f"bytes {start}-{end}/{asset.size}"
        status, length = 206, end - start + 1
    headers["Content-Length"] = str(length)
    if request.method == "HEAD":
        return Response(status_code=status, headers=headers, media_type=asset.content_type)
    try:
        result = s3().get_object(**args)
    except ClientError:
        raise HTTPException(503, "Хранилище временно недоступно") from None

    def chunks():
        try:
            yield from result["Body"].iter_chunks(chunk_size=256 * 1024)
        finally:
            result["Body"].close()

    return StreamingResponse(
        chunks(), status_code=status, headers=headers, media_type=asset.content_type
    )


@router.api_route("/{video_id}/stream", methods=["GET", "HEAD"])
def stream(
    video_id: str,
    request: Request,
    user: User | None = Depends(optional_user),
    db: Session = Depends(get_db),
):
    return media_response(video_id, "playback", request, user, db)


@router.api_route("/{video_id}/thumbnail", methods=["GET", "HEAD"])
def thumbnail(
    video_id: str,
    request: Request,
    user: User | None = Depends(optional_user),
    db: Session = Depends(get_db),
):
    return media_response(video_id, "thumbnail", request, user, db)


@router.put("/{video_id}/reaction")
def reaction(
    video_id: str,
    data: ReactionInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    video = require_video(db, video_id, user, media=True)
    if data.value == 0:
        db.execute(
            delete(Reaction).where(Reaction.user_id == user.id, Reaction.video_id == video_id)
        )
    else:
        stmt = insert(Reaction).values(user_id=user.id, video_id=video_id, value=data.value)
        db.execute(
            stmt.on_conflict_do_update(
                index_elements=["user_id", "video_id"], set_={"value": data.value}
            )
        )
    db.commit()
    return videos_dict(db, [video], user)[0]


@router.get("/{video_id}/comments")
def comments(
    video_id: str,
    page: int = Query(1, ge=1),
    user: User | None = Depends(optional_user),
    db: Session = Depends(get_db),
):
    require_video(db, video_id, user, media=True)
    rows = db.scalars(
        select(Comment)
        .where(Comment.video_id == video_id)
        .order_by(Comment.created_at.desc(), Comment.id)
        .offset((page - 1) * 30)
        .limit(30)
    )
    return [
        {
            "id": c.id,
            "text": c.text,
            "created_at": c.created_at,
            "author": c.user.display_name,
            "can_delete": bool(
                user and (user.id == c.user_id or user.role in ("admin", "moderator"))
            ),
        }
        for c in rows
    ]


@router.post("/{video_id}/comments", status_code=201)
def add_comment(
    video_id: str,
    data: CommentInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    rate_limit(db, "comment:" + user.id, 20)
    require_video(db, video_id, user, media=True)
    comment = Comment(video_id=video_id, user_id=user.id, text=data.text)
    db.add(comment)
    db.commit()
    return {"id": comment.id}


@router.delete("/{video_id}/comments/{comment_id}", status_code=204)
def delete_comment(
    video_id: str,
    comment_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    require_video(db, video_id, user, media=True)
    comment = db.get(Comment, comment_id)
    if not comment or comment.video_id != video_id:
        raise HTTPException(404, "Комментарий не найден")
    if user.id != comment.user_id and user.role not in ("admin", "moderator"):
        raise HTTPException(403, "Недостаточно прав")
    db.delete(comment)
    db.commit()


@router.post("/{video_id}/view", status_code=204)
def record_view(
    video_id: str,
    data: WatchInput,
    request: Request,
    user: User | None = Depends(optional_user),
    db: Session = Depends(get_db),
):
    video = require_video(db, video_id, user, media=True)
    identity = user.id if user else client_key(request)
    hashed = hmac.new(
        get_settings().secret_key.encode(), identity.encode(), hashlib.sha256
    ).hexdigest()
    stmt = insert(ViewEvent).values(
        video_id=video_id, viewer_hash=hashed, day=utcnow().date().isoformat()
    )
    inserted = db.scalar(
        stmt.on_conflict_do_nothing(index_elements=["video_id", "viewer_hash", "day"]).returning(
            ViewEvent.id
        )
    )
    if inserted:
        db.execute(update(Video).where(Video.id == video_id).values(views=Video.views + 1))
    if user:
        position = min(data.position, video.duration)
        stmt = insert(WatchHistory).values(video_id=video_id, user_id=user.id, position=position)
        db.execute(
            stmt.on_conflict_do_update(
                index_elements=["user_id", "video_id"],
                set_={"position": position, "watched_at": utcnow()},
            )
        )
    db.commit()


@router.get("/{video_id}/grants")
def grants(video_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_video(db, video_id, user, owner=True)
    return [
        {"id": g.id, "email": email}
        for g, email in db.execute(
            select(VideoGrant, User.email).join(User).where(VideoGrant.video_id == video_id)
        )
    ]


@router.post("/{video_id}/grants", status_code=201)
def grant(
    video_id: str,
    data: GrantInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    rate_limit(db, "grant:" + user.id, 30)
    require_video(db, video_id, user, owner=True)
    recipient = db.scalar(
        select(User).where(User.email == str(data.email).lower(), User.disabled.is_(False))
    )
    if not recipient:
        raise HTTPException(404, "Пользователь с таким email не зарегистрирован")
    if recipient.id == user.id:
        raise HTTPException(422, "У владельца уже есть доступ")
    db.execute(
        insert(VideoGrant)
        .values(video_id=video_id, user_id=recipient.id)
        .on_conflict_do_nothing(index_elements=["video_id", "user_id"])
    )
    db.add(
        AuditEvent(
            actor_id=user.id,
            action="video.grant",
            target_id=video_id,
            detail={"recipient_id": recipient.id},
        )
    )
    db.commit()
    return {"ok": True}


@router.delete("/{video_id}/grants/{grant_id}", status_code=204)
def revoke(
    video_id: str, grant_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    require_video(db, video_id, user, owner=True)
    db.execute(delete(VideoGrant).where(VideoGrant.id == grant_id, VideoGrant.video_id == video_id))
    db.add(AuditEvent(actor_id=user.id, action="video.revoke", target_id=video_id))
    db.commit()


@router.post("/{video_id}/reports", status_code=201)
def report(
    video_id: str,
    data: ReportInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    rate_limit(db, "report:" + user.id, 10, 3600)
    require_video(db, video_id, user, media=True)
    stmt = insert(Report).values(user_id=user.id, video_id=video_id, reason=data.reason)
    result = db.scalar(
        stmt.on_conflict_do_nothing(index_elements=["user_id", "video_id"]).returning(Report.id)
    )
    db.commit()
    if not result:
        raise HTTPException(409, "Вы уже отправили жалобу на это видео")
    return {"id": result}
