from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Channel, Comment, Reaction, Subscription, User, Video, WatchHistory


def user_dict(db: Session, user: User):
    channel = db.scalar(select(Channel).where(Channel.user_id == user.id))
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "channel_id": channel.id,
        "handle": channel.handle,
    }


def channel_dict(db: Session, channel: Channel, user: User | None = None):
    count = db.scalar(
        select(func.count()).select_from(Subscription).where(Subscription.channel_id == channel.id)
    )
    subscribed = bool(
        user
        and db.scalar(
            select(Subscription.id).where(
                Subscription.channel_id == channel.id, Subscription.user_id == user.id
            )
        )
    )
    return {
        "id": channel.id,
        "name": channel.name,
        "handle": channel.handle,
        "description": channel.description,
        "color": channel.color,
        "subscribers": count,
        "subscribed": subscribed,
        "is_owner": bool(user and channel.user_id == user.id),
    }


def videos_dict(db: Session, videos: list[Video], user: User | None = None):
    ids = [v.id for v in videos]
    if not ids:
        return []
    likes = dict(
        db.execute(
            select(Reaction.video_id, func.count())
            .where(Reaction.video_id.in_(ids), Reaction.value == 1)
            .group_by(Reaction.video_id)
        ).all()
    )
    comments = dict(
        db.execute(
            select(Comment.video_id, func.count())
            .where(Comment.video_id.in_(ids))
            .group_by(Comment.video_id)
        ).all()
    )
    reactions, positions = {}, {}
    if user:
        reactions = dict(
            db.execute(
                select(Reaction.video_id, Reaction.value).where(
                    Reaction.video_id.in_(ids), Reaction.user_id == user.id
                )
            ).all()
        )
        positions = dict(
            db.execute(
                select(WatchHistory.video_id, WatchHistory.position).where(
                    WatchHistory.video_id.in_(ids), WatchHistory.user_id == user.id
                )
            ).all()
        )
    return [
        {
            "id": v.id,
            "title": v.title,
            "description": v.description,
            "category": v.category,
            "visibility": v.visibility,
            "status": v.status,
            "hidden": v.hidden,
            "duration": v.duration,
            "views": v.views,
            "created_at": v.created_at,
            "likes": likes.get(v.id, 0),
            "comment_count": comments.get(v.id, 0),
            "reaction": reactions.get(v.id, 0),
            "position": positions.get(v.id, 0),
            "error": v.error,
            "is_owner": bool(user and v.channel.user_id == user.id),
            "thumbnail": f"/api/videos/{v.id}/thumbnail"
            if v.status == "ready" and not v.hidden
            else None,
            "channel": {
                "id": v.channel.id,
                "name": v.channel.name,
                "handle": v.channel.handle,
                "color": v.channel.color,
            },
        }
        for v in videos
    ]
