"""Black-box HTTP smoke test against a running deployment with real S3 and worker."""

import argparse
import http.cookiejar
import json
import secrets
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument(
        "--allow-write",
        action="store_true",
        help="Creates a dedicated smoke-test user and removes its video afterward",
    )
    args = parser.parse_args()
    if not args.allow_write:
        raise SystemExit("Pass --allow-write to run this isolated test workflow")
    base = args.url.rstrip("/")
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    csrf = ""

    def request(path, method="GET", data=None, raw=None, expected=200, headers=None):
        body = raw if raw is not None else json.dumps(data).encode() if data is not None else None
        h = {"X-CSRF-Token": csrf}
        if data is not None:
            h["Content-Type"] = "application/json"
        if headers:
            h.update(headers)
        req = urllib.request.Request(base + path, data=body, method=method, headers=h)
        try:
            response = opener.open(req, timeout=90)
        except urllib.error.HTTPError as exc:
            response = exc
        content = response.read()
        assert response.status == expected, (path, response.status, content[:500])
        return (
            json.loads(content)
            if response.headers.get("Content-Type", "").startswith("application/json") and content
            else content
        )

    csrf = request("/api/auth/csrf")["csrf_token"]
    unique = secrets.token_hex(6)
    request(
        "/api/auth/register",
        "POST",
        {
            "email": f"smoke-{unique}@example.com",
            "password": secrets.token_urlsafe(24),
            "display_name": "Smoke test",
        },
        expected=201,
    )
    video = request("/api/videos", "POST", {"title": "Smoke test " + unique}, expected=201)
    vid = video["id"]
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "video.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                "testsrc2=s=320x180:r=15:d=2",
                "-c:v",
                "libx264",
                "-threads",
                "1",
                "-pix_fmt",
                "yuv420p",
                str(path),
            ],
            check=True,
        )
        request(f"/api/videos/{vid}/file", "PUT", raw=path.read_bytes(), expected=202)
    for _ in range(60):
        state = request(f"/api/videos/{vid}")
        if state["status"] == "ready":
            break
        assert state["status"] != "failed", state
        time.sleep(2)
    else:
        raise AssertionError("Worker did not finish within 120 seconds")
    media = request(f"/api/videos/{vid}/stream", headers={"Range": "bytes=0-100"}, expected=206)
    assert b"ftyp" in media
    assert request(f"/api/videos/{vid}/thumbnail")[:2] == b"\xff\xd8"
    assert request(f"/api/videos/{vid}/reaction", "PUT", {"value": 1})["likes"] == 1
    request(f"/api/videos/{vid}/comments", "POST", {"text": "Smoke test comment"}, expected=201)
    assert len(request(f"/api/videos/{vid}/comments")) == 1
    request(
        f"/api/videos/{vid}", "PATCH", {"title": "Smoke test " + unique, "visibility": "private"}
    )
    anonymous = urllib.request.build_opener()
    try:
        anonymous.open(base + f"/api/videos/{vid}/stream")
        raise AssertionError("Private stream accessible anonymously")
    except urllib.error.HTTPError as exc:
        assert exc.code == 404
    request(f"/api/videos/{vid}", "DELETE", expected=204)
    print(
        "PASS: registration -> upload -> worker -> Range playback -> thumbnail -> like -> comment -> private isolation -> cleanup"
    )


if __name__ == "__main__":
    main()
