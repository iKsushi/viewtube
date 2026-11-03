from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import admin_user, current_user, optional_user, staff_user
from app.models import (
    AuditEvent,
    Channel,
    LoginSession,
    Playlist,
    PlaylistItem,
    Report,
    Subscription,
    User,
    Video,
)
from app.schemas import ChannelInput, ModerationInput, PlaylistInput, RoleInput
from app.services.access import readable_filter, require_video
from app.services.presenters import channel_dict, videos_dict

router = APIRouter(tags=["Community"])


@router.get("/channels/{channel_id}")
def channel(
    channel_id: str, user: User | None = Depends(optional_user), db: Session = Depends(get_db)
):
    row = db.get(Channel, channel_id)
    if not row:
        raise HTTPException(404, "Канал не найден")
    return channel_dict(db, row, user)


@router.patch("/channels/{channel_id}")
def edit_channel(
    channel_id: str,
    data: ChannelInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    row = db.get(Channel, channel_id)
    if not row or row.user_id != user.id:
        raise HTTPException(404, "Канал не найден")
    row.name, row.description = data.name, data.description
    db.commit()
    return channel_dict(db, row, user)


@router.put("/channels/{channel_id}/subscription")
def subscribe(channel_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.get(Channel, channel_id)
    if not row:
        raise HTTPException(404, "Канал не найден")
    if row.user_id == user.id:
        raise HTTPException(422, "Нельзя подписаться на свой канал")
    db.execute(
        insert(Subscription)
        .values(user_id=user.id, channel_id=channel_id)
        .on_conflict_do_nothing(index_elements=["user_id", "channel_id"])
    )
    db.commit()
    return channel_dict(db, row, user)


@router.delete("/channels/{channel_id}/subscription")
def unsubscribe(channel_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.get(Channel, channel_id)
    if not row:
        raise HTTPException(404, "Канал не найден")
    db.execute(
        delete(Subscription).where(
            Subscription.user_id == user.id, Subscription.channel_id == channel_id
        )
    )
    db.commit()
    return channel_dict(db, row, user)


@router.get("/subscriptions")
def subscriptions(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Channel)
        .join(Subscription)
        .where(Subscription.user_id == user.id)
        .order_by(Channel.name)
        .limit(200)
    )
    return [channel_dict(db, c, user) for c in rows]


def playlist_access(db, playlist_id, user, owner=False):
    p = db.get(Playlist, playlist_id)
    if not p or (
        (owner or p.visibility == "private") and (not user or p.channel.user_id != user.id)
    ):
        raise HTTPException(404, "Плейлист недоступен")
    return p


def playlist_dict(db, p, user):
    # A public playlist never exposes names or counts of inaccessible private videos.
    videos = list(
        db.scalars(
            select(Video)
            .join(PlaylistItem)
            .where(PlaylistItem.playlist_id == p.id, readable_filter(user))
            .order_by(PlaylistItem.position, PlaylistItem.id)
        )
    )
    return {
        "id": p.id,
        "title": p.title,
        "visibility": p.visibility,
        "channel_id": p.channel_id,
        "is_owner": bool(user and p.channel.user_id == user.id),
        "videos": videos_dict(db, videos, user),
    }


@router.get("/channels/{channel_id}/playlists")
def playlists(
    channel_id: str, user: User | None = Depends(optional_user), db: Session = Depends(get_db)
):
    query = select(Playlist).where(Playlist.channel_id == channel_id)
    channel = db.get(Channel, channel_id)
    if not channel:
        raise HTTPException(404, "Канал не найден")
    if not user or channel.user_id != user.id:
        query = query.where(Playlist.visibility == "public")
    return [
        playlist_dict(db, p, user)
        for p in db.scalars(query.order_by(Playlist.created_at.desc()).limit(100))
    ]


@router.get("/playlists/{playlist_id}")
def get_playlist(
    playlist_id: str, user: User | None = Depends(optional_user), db: Session = Depends(get_db)
):
    return playlist_dict(db, playlist_access(db, playlist_id, user), user)


@router.post("/playlists", status_code=201)
def create_playlist(
    data: PlaylistInput, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    channel = db.scalar(select(Channel).where(Channel.user_id == user.id))
    count = db.scalar(
        select(func.count()).select_from(Playlist).where(Playlist.channel_id == channel.id)
    )
    if count >= 100:
        raise HTTPException(422, "Лимит: 100 плейлистов")
    p = Playlist(channel_id=channel.id, **data.model_dump())
    db.add(p)
    db.commit()
    return playlist_dict(db, p, user)


@router.patch("/playlists/{playlist_id}")
def edit_playlist(
    playlist_id: str,
    data: PlaylistInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    p = playlist_access(db, playlist_id, user, owner=True)
    p.title, p.visibility = data.title, data.visibility
    db.commit()
    return playlist_dict(db, p, user)


@router.delete("/playlists/{playlist_id}", status_code=204)
def delete_playlist(
    playlist_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    db.delete(playlist_access(db, playlist_id, user, owner=True))
    db.commit()


@router.put("/playlists/{playlist_id}/videos/{video_id}")
def add_to_playlist(
    playlist_id: str,
    video_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    p = playlist_access(db, playlist_id, user, owner=True)
    require_video(db, video_id, user, media=True)
    # Serialize position assignment per playlist; unique membership makes this idempotent.
    db.scalar(select(Playlist).where(Playlist.id == p.id).with_for_update(of=Playlist))
    position = (
        db.scalar(
            select(func.coalesce(func.max(PlaylistItem.position), 0)).where(
                PlaylistItem.playlist_id == p.id
            )
        )
        + 1
    )
    if position > 1000:
        raise HTTPException(422, "Лимит: 1000 видео в плейлисте")
    db.execute(
        insert(PlaylistItem)
        .values(playlist_id=p.id, video_id=video_id, position=position)
        .on_conflict_do_nothing(index_elements=["playlist_id", "video_id"])
    )
    db.commit()
    return playlist_dict(db, p, user)


@router.delete("/playlists/{playlist_id}/videos/{video_id}", status_code=204)
def remove_from_playlist(
    playlist_id: str,
    video_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    playlist_access(db, playlist_id, user, owner=True)
    db.execute(
        delete(PlaylistItem).where(
            PlaylistItem.playlist_id == playlist_id, PlaylistItem.video_id == video_id
        )
    )
    db.commit()


@router.get("/moderation/reports")
def reports(
    status: str = "open",
    page: int = Query(1, ge=1),
    user: User = Depends(staff_user),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(Report, Video)
        .join(Video)
        .where(Report.status == status)
        .order_by(Report.created_at)
        .offset((page - 1) * 30)
        .limit(30)
    )
    return [
        {
            "id": r.id,
            "video_id": v.id,
            "title": v.title,
            "reason": r.reason,
            "status": r.status,
            "hidden": v.hidden,
            "created_at": r.created_at,
            "visibility": v.visibility,
            "resolution": r.resolution,
        }
        for r, v in rows
    ]


@router.post("/moderation/reports/{report_id}/resolve")
def resolve_report(
    report_id: str,
    data: ModerationInput,
    user: User = Depends(staff_user),
    db: Session = Depends(get_db),
):
    r = db.scalar(select(Report).where(Report.id == report_id).with_for_update())
    if not r:
        raise HTTPException(404, "Жалоба не найдена")
    if r.status != "open":
        raise HTTPException(409, "Жалоба уже рассмотрена")
    video = db.get(Video, r.video_id)
    if data.action == "hide":
        video.hidden = True
    r.status, r.resolution, r.resolved_by = "resolved", data.reason, user.id
    db.add(
        AuditEvent(
            actor_id=user.id,
            action="moderation." + data.action,
            target_id=video.id,
            detail={"report_id": r.id, "reason": data.reason},
        )
    )
    db.commit()
    return {"ok": True}


@router.post("/moderation/videos/{video_id}/restore")
def restore_video(video_id: str, user: User = Depends(staff_user), db: Session = Depends(get_db)):
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(404, "Видео не найдено")
    video.hidden = False
    db.add(AuditEvent(actor_id=user.id, action="moderation.restore", target_id=video.id))
    db.commit()
    return {"ok": True}


@router.get("/admin/users")
def users(
    q: str = Query("", max_length=100),
    page: int = Query(1, ge=1),
    user: User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    stmt = (
        select(User)
        .where(User.email.contains(q, autoescape=True))
        .order_by(User.created_at.desc())
        .offset((page - 1) * 30)
        .limit(30)
    )
    return [
        {
            "id": u.id,
            "email": u.email,
            "display_name": u.display_name,
            "role": u.role,
            "disabled": u.disabled,
        }
        for u in db.scalars(stmt)
    ]


@router.patch("/admin/users/{user_id}/role")
def change_role(
    user_id: str, data: RoleInput, user: User = Depends(admin_user), db: Session = Depends(get_db)
):
    if user_id == user.id:
        raise HTTPException(422, "Нельзя менять собственную роль")
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "Пользователь не найден")
    target.role = data.role
    db.execute(delete(LoginSession).where(LoginSession.user_id == target.id))
    db.add(
        AuditEvent(
            actor_id=user.id, action="user.role", target_id=target.id, detail={"role": data.role}
        )
    )
    db.commit()
    return {"ok": True}


@router.get("/admin/audit")
def audit(
    page: int = Query(1, ge=1), user: User = Depends(admin_user), db: Session = Depends(get_db)
):
    return [
        {
            "id": e.id,
            "action": e.action,
            "target_id": e.target_id,
            "actor_id": e.actor_id,
            "detail": e.detail,
            "created_at": e.created_at,
        }
        for e in db.scalars(
            select(AuditEvent)
            .order_by(AuditEvent.created_at.desc())
            .offset((page - 1) * 50)
            .limit(50)
        )
    ]
