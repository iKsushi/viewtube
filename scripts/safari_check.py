"""Native Safari WebDriver journey; start safaridriver -p 4444 first."""

import argparse
import json
import secrets
import time
import urllib.error
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--media", type=Path, required=True)
    parser.add_argument("--driver", default="http://localhost:4444")
    args = parser.parse_args()

    def call(path, data=None, method=None):
        request = urllib.request.Request(
            args.driver + path,
            data=json.dumps(data).encode() if data is not None else None,
            headers={"Content-Type": "application/json"},
            method=method or ("POST" if data is not None else "GET"),
        )
        try:
            response = urllib.request.urlopen(request, timeout=180)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(exc.read().decode()) from exc
        value = json.load(response)["value"]
        return value

    session = call(
        "/session", {"capabilities": {"alwaysMatch": {"browserName": "safari"}}}
    )["sessionId"]
    base = "/session/" + session

    def js(script, *values):
        return call(base + "/execute/sync", {"script": script, "args": list(values)})

    def wait(script, timeout=120):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            if js(script):
                return
            time.sleep(0.3)
        raise AssertionError(script)

    def fill(selector, value):
        js(
            'const e=document.querySelector(arguments[0]); Object.getOwnPropertyDescriptor(e.tagName==="TEXTAREA"?HTMLTextAreaElement.prototype:HTMLInputElement.prototype,"value").set.call(e,arguments[1]); e.dispatchEvent(new Event("input",{bubbles:true}));',
            selector,
            value,
        )

    def click(selector):
        js("document.querySelector(arguments[0]).click()", selector)

    try:
        call(base + "/url", {"url": args.url + "/register"})
        wait('return !!document.querySelector("input[autocomplete=name]")')
        fill("input[autocomplete=name]", "Safari Test")
        fill("input[type=email]", "safari-" + secrets.token_hex(6) + "@example.com")
        fill("input[autocomplete=new-password]", secrets.token_urlsafe(24))
        click("button[type=submit],form button.primary")
        wait('return location.pathname !== "/register"')
        call(base + "/url", {"url": args.url + "/upload"})
        wait('return !!document.querySelector("input[type=file]")')
        element = call(
            base + "/element", {"using": "css selector", "value": "input[type=file]"}
        )
        eid = element["element-6066-11e4-a52e-4f735466cecf"]
        call(base + "/element/" + eid + "/value", {"text": str(args.media.resolve())})
        title = "Safari " + secrets.token_hex(6)
        fill('input[maxlength="150"]', title)
        click("form button.primary")
        wait('return document.body.innerText.includes("Готовим ваше видео")')
        click('a[href="/studio"]')
        wait('return !!document.querySelector("a[aria-label^=Смотреть]")')
        click("a[aria-label^=Смотреть]")
        wait('return !!document.querySelector("video")')
        assert js(
            'return document.querySelector("video").canPlayType(\'video/mp4; codecs="avc1.42E01E"\')'
        )
        js('const v=document.querySelector("video");v.muted=true;v.play();')
        wait('return document.querySelector("video").currentTime>0')
        click('button[aria-label="Нравится"]')
        wait(
            'return document.querySelector(\'button[aria-label="Нравится"]\').getAttribute("aria-pressed")==="true"'
        )
        fill("#comment", title)
        click(".comment-form button")
        wait('return !!document.querySelector(".comment")')
        call(base + "/refresh", {})
        wait('return !!document.querySelector(".comment")')
        assert js(
            'return document.querySelector(".comments").innerText.includes(arguments[0])',
            title,
        )
        assert js(
            'return document.querySelector(\'button[aria-label="Нравится"]\').getAttribute("aria-pressed")==="true"'
        )
        print("PASS native Safari: registration/upload/playback/like/comment/reload")
    finally:
        call(base, method="DELETE")


if __name__ == "__main__":
    main()
