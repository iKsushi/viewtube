import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def utcnow():
    return datetime.now(UTC)


def new_id():
    return str(uuid.uuid4())


class Identity:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(Identity, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(60))
    role: Mapped[str] = mapped_column(String(12), default="user")
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (CheckConstraint("role IN ('user','moderator','admin')"),)


class Channel(Identity, Base):
    __tablename__ = "channels"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    handle: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(60))
    description: Mapped[str] = mapped_column(Text, default="")
    color: Mapped[str] = mapped_column(String(7), default="#d92d35")
    user: Mapped[User] = relationship(lazy="joined")


class LoginSession(Identity, Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Video(Identity, Base):
    __tablename__ = "videos"
    channel_id: Mapped[str] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(30), default="Другое")
    visibility: Mapped[str] = mapped_column(String(10), default="public")
    status: Mapped[str] = mapped_column(String(12), default="draft")
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    duration: Mapped[float] = mapped_column(Float, default=0)
    views: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(String(250))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    channel: Mapped[Channel] = relationship(lazy="joined")
    __table_args__ = (
        CheckConstraint("visibility IN ('public','private')"),
        CheckConstraint("status IN ('draft','uploading','queued','processing','ready','failed')"),
        Index("ix_videos_feed", "hidden", "visibility", "status", "created_at"),
    )


class VideoAsset(Identity, Base):
    __tablename__ = "video_assets"
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(12))
    key: Mapped[str] = mapped_column(String(200), unique=True)
    size: Mapped[int] = mapped_column(Integer)
    content_type: Mapped[str] = mapped_column(String(60))
    __table_args__ = (UniqueConstraint("video_id", "kind"),)


class VideoGrant(Identity, Base):
    __tablename__ = "video_grants"
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    __table_args__ = (UniqueConstraint("video_id", "user_id"),)


class Reaction(Identity, Base):
    __tablename__ = "reactions"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    value: Mapped[int] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint("user_id", "video_id"), CheckConstraint("value IN (-1,1)"))


class Comment(Identity, Base):
    __tablename__ = "comments"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    user: Mapped[User] = relationship(lazy="joined")


class Subscription(Identity, Base):
    __tablename__ = "subscriptions"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    channel_id: Mapped[str] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), index=True
    )
    __table_args__ = (UniqueConstraint("user_id", "channel_id"),)


class Playlist(Identity, Base):
    __tablename__ = "playlists"
    channel_id: Mapped[str] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(100))
    visibility: Mapped[str] = mapped_column(String(10), default="public")
    channel: Mapped[Channel] = relationship(lazy="joined")
    __table_args__ = (CheckConstraint("visibility IN ('public','private')"),)


class PlaylistItem(Identity, Base):
    __tablename__ = "playlist_items"
    playlist_id: Mapped[str] = mapped_column(ForeignKey("playlists.id", ondelete="CASCADE"))
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint("playlist_id", "video_id"),)


class Report(Identity, Base):
    __tablename__ = "reports"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    reason: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(10), default="open", index=True)
    resolution: Mapped[str | None] = mapped_column(String(500))
    resolved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    __table_args__ = (UniqueConstraint("user_id", "video_id"),)


class ProcessingJob(Identity, Base):
    __tablename__ = "processing_jobs"
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), unique=True)
    state: Mapped[str] = mapped_column(String(12), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[str | None] = mapped_column(String(36))
    error: Mapped[str | None] = mapped_column(String(250))


class ViewEvent(Identity, Base):
    __tablename__ = "view_events"
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    viewer_hash: Mapped[str] = mapped_column(String(64))
    day: Mapped[str] = mapped_column(String(10))
    __table_args__ = (UniqueConstraint("video_id", "viewer_hash", "day"),)


class WatchHistory(Identity, Base):
    __tablename__ = "watch_history"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"))
    position: Mapped[float] = mapped_column(Float, default=0)
    watched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("user_id", "video_id"),)


class AuditEvent(Identity, Base):
    __tablename__ = "audit_events"
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(60))
    target_id: Mapped[str] = mapped_column(String(36))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)


class RateBucket(Base):
    __tablename__ = "rate_buckets"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    window: Mapped[int] = mapped_column(Integer)
    count: Mapped[int] = mapped_column(Integer, default=1)
