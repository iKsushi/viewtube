"""Idempotent demo seed with locally generated, copyright-free video animations."""

import os
import subprocess
import tempfile
from datetime import timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import password_hasher
from app.models import (
    Channel,
    Comment,
    Playlist,
    PlaylistItem,
    ProcessingJob,
    Reaction,
    Report,
    Subscription,
    User,
    Video,
    VideoAsset,
    VideoGrant,
    utcnow,
)
from app.services.storage import ensure_bucket, upload
from app.worker import process_one

CREATORS = [
    ("studio", "Студия формы", "#836b65", "Дизайн, визуальная культура и внимание к деталям."),
    ("lab", "Код и кофе", "#607e87", "Простые объяснения сложных технологий."),
    ("sound", "Тихая сторона", "#758d77", "Звук, ритм и пространство для новых мыслей."),
    ("science", "За горизонтом", "#8c79a7", "Наука, космос и любопытство без границ."),
]
VIDEOS = [
    (
        "Меньше, но лучше: искусство простых форм",
        0,
        "Образование",
        "LESS IS",
        "MORE.",
        "d8c8b3",
        "8d8172",
        "282721",
    ),
    (
        "Код как искусство: красота в движении",
        1,
        "Технологии",
        "CREATIVE",
        "CODING",
        "172630",
        "18666b",
        "ffffff",
    ),
    (
        "Пространство для мыслей · визуальная пауза",
        2,
        "Музыка",
        "DEEP",
        "FOCUS",
        "233c45",
        "6c8a7d",
        "f6edcf",
    ),
    (
        "Вселенная начинается с любопытства",
        3,
        "Наука",
        "BEYOND",
        "THE KNOWN",
        "22233f",
        "6a5295",
        "f5e5ff",
    ),
    (
        "Цвет меняет всё: наблюдаем за градиентами",
        0,
        "Образование",
        "COLOR",
        "STORIES",
        "ed8e71",
        "a9b3c9",
        "ffffff",
    ),
    (
        "Ритм алгоритма: как появляется движение",
        1,
        "Технологии",
        "THINK.",
        "BUILD.",
        "c1d8b4",
        "739574",
        "213d31",
    ),
    (
        "Медленный вечер: время остановиться",
        2,
        "Музыка",
        "SLOW",
        "EVENING",
        "bd8b6a",
        "624e57",
        "fff0da",
    ),
    (
        "Свет и тень: маленький визуальный эксперимент",
        3,
        "Наука",
        "MADE",
        "OF LIGHT",
        "182e3c",
        "567f99",
        "e0eeff",
    ),
    (
        "С чистого листа: создаём что-то своё",
        0,
        "Кино",
        "A FRESH",
        "START",
        "e2dcbf",
        "aa9582",
        "51463c",
    ),
    (
        "Внутри цифрового мира: порядок и случайность",
        1,
        "Игры",
        "DIGITAL",
        "PLAYGROUND",
        "34345e",
        "c06e9b",
        "ffe9fc",
    ),
    (
        "Маршрут без спешки: навстречу новому",
        2,
        "Путешествия",
        "TAKE IT",
        "SLOW",
        "9cb6ac",
        "425e61",
        "f3f5e8",
    ),
    (
        "Новые перспективы: увидеть привычное иначе",
        3,
        "Наука",
        "STAY",
        "CURIOUS",
        "b69876",
        "6d8894",
        "ffffff",
    ),
]


def sid(value):
    return str(uuid5(NAMESPACE_URL, "viewtube-demo/" + value))


def font_path():
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ]
    return next(p for p in candidates if Path(p).exists())


def generate_demo(path, first, second, color1, color2, ink, index):
    font = font_path()
    # All filter inputs are constants defined above, never user-uploaded strings.
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (960, 540))
    draw = ImageDraw.Draw(image)
    c1, c2 = tuple(bytes.fromhex(color1)), tuple(bytes.fromhex(color2))
    for y in range(540):
        ratio = y / 539
        color = tuple(int(a * (1 - ratio) + b * ratio) for a, b in zip(c1, c2))
        draw.line((0, y, 960, y), fill=color)
    text_color = "#" + ink
    overlay = Image.new("RGBA", image.size)
    pen = ImageDraw.Draw(overlay)
    rgb = tuple(bytes.fromhex(ink))
    for x in range(0, 960, 80):
        pen.line((x, 0, x, 540), fill=(*rgb, 15))
    for y in range(0, 540, 80):
        pen.line((0, y, 960, y), fill=(*rgb, 15))
    if index % 3 == 0:
        pen.ellipse((610, 100, 1020, 510), fill=(*rgb, 24), outline=(*rgb, 50), width=2)
        pen.ellipse((660, 150, 970, 460), outline=(*rgb, 70), width=2)
    elif index % 3 == 1:
        for offset in range(0, 150, 25):
            pen.rounded_rectangle(
                (630 + offset, 80 + offset, 850 + offset, 330 + offset),
                radius=20,
                outline=(*rgb, 55),
                width=2,
            )
    else:
        for offset in range(0, 230, 30):
            pen.arc((570 + offset, 100, 920 + offset, 450), 90, 270, fill=(*rgb, 60), width=3)
    image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(image)
    draw.text(
        (58, 43), "VIEWTUBE  /  ORIGINALS", font=ImageFont.truetype(font, 16), fill=text_color
    )
    draw.text((54, 160), first, font=ImageFont.truetype(font, 74), fill=text_color)
    draw.text((54, 250), second, font=ImageFont.truetype(font, 66), fill=text_color)
    draw.text(
        (58, 465),
        f"A VISUAL EXPERIMENT  /  {index + 1:02d}",
        font=ImageFont.truetype(font, 14),
        fill=text_color,
    )
    cover = path.with_suffix(".jpg")
    image.save(cover, quality=95)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-nostdin",
            "-v",
            "error",
            "-loop",
            "1",
            "-i",
            str(cover),
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={130 + index * 16}:sample_rate=44100:duration=12",
            "-vf",
            "zoompan=z='1+0.0003*on':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=180:s=960x540:fps=15",
            "-af",
            "volume=0.035,afade=t=in:d=2,afade=t=out:st=10:d=2",
            "-t",
            "12",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-threads",
            "2",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(path),
        ],
        check=True,
        timeout=180,
    )


def main():
    password = os.environ.get("DEMO_PASSWORD", "")
    if len(password) < 12:
        raise SystemExit(
            "Set DEMO_PASSWORD (at least 12 characters); demo users never have a built-in password."
        )
    ensure_bucket()
    with SessionLocal() as db:
        # Serialize repeat/concurrent seed invocations on the demo namespace.
        db.execute(__import__("sqlalchemy").text("SELECT pg_advisory_xact_lock(20261103)"))
        for slug, name, color, description in CREATORS + [
            ("viewer", "Александр", "#7f8caa", "Сохраняю то, что интересно."),
            ("moderator", "Модератор", "#887caa", "Команда ViewTube"),
            ("admin", "Администратор", "#a96b6e", "Команда ViewTube"),
        ]:
            if db.get(User, sid(slug)):
                continue
            role = slug if slug in ("admin", "moderator") else "user"
            db.add(
                User(
                    id=sid(slug),
                    email=f"{slug}@demo.viewtube.example.com",
                    display_name=name,
                    password_hash=password_hasher.hash(password),
                    role=role,
                )
            )
            db.flush()
            db.add(
                Channel(
                    id=sid("channel/" + slug),
                    user_id=sid(slug),
                    handle=slug,
                    name=name,
                    color=color,
                    description=description,
                )
            )
        db.commit()
    with tempfile.TemporaryDirectory(prefix="viewtube-demo-") as temp:
        for index, (title, creator, category, first, second, color1, color2, ink) in enumerate(
            VIDEOS
        ):
            video_id = sid(f"video/{index}")
            with SessionLocal() as db:
                existing = db.get(Video, video_id)
                if existing and existing.status == "ready":
                    continue
                if not existing:
                    existing = Video(
                        id=video_id,
                        channel_id=sid("channel/" + CREATORS[creator][0]),
                        title=title,
                        description="Демонстрационное видео ViewTube. Анимация и звук созданы локально скриптом наполнения базы. Это короткий визуальный эксперимент для проверки плеера, поиска, комментариев и подписок.",
                        category=category,
                        status="draft",
                        views=(index * 317 + 942),
                        created_at=utcnow() - timedelta(days=index // 2),
                    )
                    db.add(existing)
                    db.commit()
                asset = db.scalar(
                    select(VideoAsset).where(
                        VideoAsset.video_id == video_id, VideoAsset.kind == "source"
                    )
                )
                if not asset:
                    path = Path(temp) / f"{index}.mp4"
                    generate_demo(path, first, second, color1, color2, ink, index)
                    key = f"videos/{video_id}/source.mp4"
                    upload(path, key, "video/mp4")
                    db.add(
                        VideoAsset(
                            video_id=video_id,
                            kind="source",
                            key=key,
                            size=path.stat().st_size,
                            content_type="video/mp4",
                        )
                    )
                    db.flush()
                job = db.scalar(select(ProcessingJob).where(ProcessingJob.video_id == video_id))
                if not job:
                    db.add(ProcessingJob(video_id=video_id))
                else:
                    job.state, job.attempts = "pending", 0
                existing.status = "queued"
                db.commit()
            print(f"Preparing demo video {index + 1}/{len(VIDEOS)}", flush=True)
            while process_one():
                pass
    with SessionLocal() as db:
        for index in range(len(VIDEOS)):
            video_id = sid(f"video/{index}")
            video = db.get(Video, video_id)
            if video.status != "ready":
                raise SystemExit(f"Demo video {index} failed: {video.error}")
            if not db.get(Comment, sid(f"comment/{index}")):
                db.add(
                    Comment(
                        id=sid(f"comment/{index}"),
                        video_id=video_id,
                        user_id=sid("viewer"),
                        text=[
                            "Красиво! Нравится сочетание цветов.",
                            "Сохранил в подборку для вдохновения.",
                            "Хорошая идея для визуального эксперимента.",
                        ][index % 3],
                    )
                )
                db.add(
                    Reaction(
                        id=sid(f"reaction/{index}"),
                        video_id=video_id,
                        user_id=sid("viewer"),
                        value=1,
                    )
                )
        for slug, *_ in CREATORS:
            if not db.get(Subscription, sid("sub/" + slug)):
                db.add(
                    Subscription(
                        id=sid("sub/" + slug),
                        user_id=sid("viewer"),
                        channel_id=sid("channel/" + slug),
                    )
                )
        if not db.get(Playlist, sid("playlist")):
            db.add(
                Playlist(
                    id=sid("playlist"),
                    channel_id=sid("channel/studio"),
                    title="Визуальное вдохновение",
                )
            )
            db.flush()
            for position, index in enumerate((0, 4, 8)):
                db.add(
                    PlaylistItem(
                        playlist_id=sid("playlist"),
                        video_id=sid(f"video/{index}"),
                        position=position,
                    )
                )
        # One real private video for owner/grantee/stranger tests in the UI.
        private = db.get(Video, sid("video/11"))
        private.visibility = "private"
        if not db.get(VideoGrant, sid("private-grant")):
            db.add(VideoGrant(id=sid("private-grant"), video_id=private.id, user_id=sid("viewer")))
        if not db.get(Report, sid("report")):
            db.add(
                Report(
                    id=sid("report"),
                    user_id=sid("viewer"),
                    video_id=sid("video/8"),
                    reason="Демонстрационная жалоба для проверки интерфейса модерации. Нарушение не утверждается.",
                )
            )
        db.commit()
    print(
        "Demo seed complete: 7 users, 12 playable videos (one private), comments, subscriptions and playlist."
    )


if __name__ == "__main__":
    main()
