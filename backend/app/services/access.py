from fastapi import HTTPException
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import User, Video, VideoGrant


def owns(video: Video, user: User | None) -> bool:
    return bool(user and video.channel.user_id == user.id)


def readable_filter(user: User | None):
    public = Video.visibility == "public"
    if user:
        public = public | exists(
            select(VideoGrant.id).where(
                VideoGrant.video_id == Video.id, VideoGrant.user_id == user.id
            )
        )
        public = public | Video.channel.has(user_id=user.id)
        if get_settings().staff_private_access and user.role in ("moderator", "admin"):
            public = True
    return (Video.status == "ready") & (Video.hidden.is_(False)) & public


def require_video(db: Session, video_id: str, user: User | None, *, owner=False, media=False):
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(404, "Видео недоступно")
    is_owner = owns(video, user)
    if owner:
        if not is_owner:
            raise HTTPException(404, "Видео недоступно")
        return video
    if is_owner and not media:
        return video
    if video.hidden or video.status != "ready":
        raise HTTPException(404, "Видео недоступно")
    if video.visibility == "private" and not is_owner:
        is_staff = (
            user and user.role in ("moderator", "admin") and get_settings().staff_private_access
        )
        grant = user and db.scalar(
            select(VideoGrant.id).where(
                VideoGrant.video_id == video.id, VideoGrant.user_id == user.id
            )
        )
        if not grant and not is_staff:
            raise HTTPException(404, "Видео недоступно")
    return video
