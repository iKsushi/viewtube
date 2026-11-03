"""Real deployment boundary checks. Creates test accounts/videos; run on test data only."""

import argparse
import http.cookiejar
import json
import secrets
import struct
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--allow-write", action="store_true", required=True)
    args = parser.parse_args()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    csrf = ""

    def request(path, method="GET", data=None, file=None, expected=200):
        headers = {"X-CSRF-Token": csrf}
        body = json.dumps(data).encode() if data is not None else None
        if data is not None:
            headers["Content-Type"] = "application/json"
        if file:
            headers.update(
                {
                    "Content-Type": "application/octet-stream",
                    "Content-Length": str(file.stat().st_size),
                }
            )
            body = file.open("rb")
        try:
            req = urllib.request.Request(
                args.url.rstrip("/") + path, data=body, headers=headers, method=method
            )
            try:
                response = opener.open(req, timeout=600)
            except urllib.error.HTTPError as exc:
                response = exc
            content = response.read()
            assert response.status == expected, (path, response.status, content[:200])
            return (
                json.loads(content)
                if content and response.headers.get_content_type() == "application/json"
                else content
            )
        finally:
            if file:
                body.close()

    csrf = request("/api/auth/csrf")["csrf_token"]
    request(
        "/api/auth/register",
        "POST",
        {
            "email": f"limits-{secrets.token_hex(6)}@example.com",
            "password": secrets.token_urlsafe(24),
            "display_name": "Boundary test",
        },
        expected=201,
    )
    with tempfile.TemporaryDirectory() as temp:
        for name, duration, size, target in [
            ("size-512MiB", 2, 536870912, "ready"),
            ("duration-7200", 7200, None, "ready"),
            ("duration-7201", 7201, None, "failed"),
        ]:
            path = Path(temp) / f"{name}.mp4"
            subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=c=blue:s=32x32:r=1:d={duration}",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "ultrafast",
                    "-pix_fmt",
                    "yuv420p",
                    "-movflags",
                    "+faststart",
                    str(path),
                ],
                check=True,
            )
            if size:
                # Valid MP4 free box pads to the exact real upload boundary without fake headers.
                padding = size - path.stat().st_size
                assert padding >= 8
                with path.open("ab") as stream:
                    stream.write(struct.pack(">I4s", padding, b"free"))
                    stream.truncate(size)
            vid = request("/api/videos", "POST", {"title": "Boundary " + name}, expected=201)["id"]
            start = time.monotonic()
            request(f"/api/videos/{vid}/file", "PUT", file=path, expected=202)
            while time.monotonic() - start < 4200:
                state = request(f"/api/videos/{vid}")
                if state["status"] in ("ready", "failed"):
                    break
                time.sleep(3)
            assert state["status"] == target, state
            if target == "ready":
                assert abs(state["duration"] - duration) <= 1, state
                assert request(f"/api/videos/{vid}/thumbnail")[:2] == b"\xff\xd8"
            else:
                request(f"/api/videos/{vid}/stream", expected=404)
            request(f"/api/videos/{vid}", "DELETE", expected=204)
            print(
                json.dumps(
                    {
                        "case": name,
                        "bytes": path.stat().st_size,
                        "duration": duration,
                        "expected": target,
                        "result": "PASS",
                        "seconds": round(time.monotonic() - start, 1),
                    }
                ),
                flush=True,
            )


if __name__ == "__main__":
    main()
