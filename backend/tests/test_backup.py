import io
from types import SimpleNamespace

from app import backup
from app.core.config import get_settings
from app.services.storage import s3


def test_streaming_backup_restore_roundtrip(monkeypatch):
    bucket = get_settings().s3_bucket
    expected = {
        "videos/a/video.mp4": (b"video" * 5000, "video/mp4"),
        "videos/b/thumbnail.jpg": (b"image", "image/jpeg"),
    }
    for key, (data, mime) in expected.items():
        s3().put_object(Bucket=bucket, Key=key, Body=data, ContentType=mime)
    output = io.BytesIO()
    monkeypatch.setattr("sys.argv", ["backup", "export"])
    monkeypatch.setattr("sys.stdout", SimpleNamespace(buffer=output))
    backup.main()
    for key in expected:
        s3().delete_object(Bucket=bucket, Key=key)
    monkeypatch.setattr("sys.argv", ["backup", "import"])
    monkeypatch.setattr("sys.stdin", SimpleNamespace(buffer=io.BytesIO(output.getvalue())))
    backup.main()
    for key, (data, mime) in expected.items():
        result = s3().get_object(Bucket=bucket, Key=key)
        assert result["Body"].read() == data
        assert result["ContentType"] == mime
