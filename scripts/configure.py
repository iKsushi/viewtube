#!/usr/bin/env python3
"""Generate local deployment config. No credentials enter Git or shell arguments."""

import argparse
import json
import os
import secrets
from pathlib import Path
from urllib.parse import urlsplit

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://localhost:8080")
args = parser.parse_args()
url = urlsplit(args.url)
if (
    url.scheme not in ("http", "https")
    or not url.hostname
    or url.username
    or url.password
    or url.path not in ("", "/")
    or url.query
    or url.fragment
    or any(
        c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:-/"
        for c in args.url
    )
):
    raise SystemExit("Use a plain http(s) URL with no path, credentials or query.")
origin = args.url.rstrip("/")
root = Path(__file__).resolve().parents[1]
runtime = root / ".runtime"
runtime.mkdir(mode=0o700, exist_ok=True)
runtime.chmod(0o700)
env_file = root / ".env"
if env_file.exists():
    env = dict(
        line.split("=", 1)
        for line in env_file.read_text().splitlines()
        if line and not line.startswith("#")
    )
    if env.get("APP_ORIGIN") != origin:
        raise SystemExit(
            "Existing .env has another APP_ORIGIN. Edit it deliberately; credentials were preserved."
        )
else:
    secure = url.scheme == "https"
    if secure and url.port not in (None, 443):
        raise SystemExit("HTTPS deployment expects standard port 443.")
    env = {
        "POSTGRES_PASSWORD": secrets.token_hex(24),
        "SECRET_KEY": secrets.token_hex(48),
        "S3_ACCESS_KEY": secrets.token_hex(12),
        "S3_SECRET_KEY": secrets.token_hex(32),
        "APP_ORIGIN": origin,
        "COOKIE_SECURE": str(secure).lower(),
        "SITE_ADDRESS": url.hostname if secure else ":80",
        "BIND_ADDRESS": "127.0.0.1"
        if url.hostname in ("localhost", "127.0.0.1")
        else "0.0.0.0",
        "HTTP_PORT": "80" if secure else str(url.port or 80),
        "HTTPS_PORT": "443" if secure else "8443",
        "ADMIN_EMAIL": os.environ.get("ADMIN_EMAIL", "admin@viewtube.example.com"),
        "ADMIN_PASSWORD": secrets.token_urlsafe(24),
        "DEMO_PASSWORD": secrets.token_urlsafe(24),
    }
    for value in env.values():
        if "\n" in value or "\r" in value or "$" in value or "#" in value:
            raise SystemExit("Unsupported environment value")
    env_file.write_text("\n".join(f"{k}={v}" for k, v in env.items()) + "\n")
    env_file.chmod(0o600)
    access = runtime / "access.txt"
    access.write_text(
        f"URL: {origin}\nAdministrator: {env['ADMIN_EMAIL']}\nPassword: {env['ADMIN_PASSWORD']}\n\nDemo viewer: viewer@demo.viewtube.example.com\nDemo author: studio@demo.viewtube.example.com\nDemo moderator: moderator@demo.viewtube.example.com\nDemo admin: admin@demo.viewtube.example.com\nDemo password: {env['DEMO_PASSWORD']}\nDemo accounts exist only after --demo. Keep this file private.\n"
    )
    access.chmod(0o600)
config = {
    "identities": [
        {
            "name": "viewtube",
            "credentials": [
                {"accessKey": env["S3_ACCESS_KEY"], "secretKey": env["S3_SECRET_KEY"]}
            ],
            "actions": ["Admin", "Read", "Write", "List", "Tagging"],
        }
    ]
}
s3_file = runtime / "s3.json"
s3_file.write_text(json.dumps(config))
# Container UID can read the bind mount; host parent directory is owner-only.
s3_file.chmod(0o644)
print("Configuration ready. Private credentials: .runtime/access.txt")
