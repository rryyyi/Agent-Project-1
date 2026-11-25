"""Real browser checks. Install .[browser] and run playwright install chromium first."""

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", help="Optional installed Chrome/Edge executable")
    parser.add_argument("--screenshot", type=Path, help="Save desktop workbench screenshot")
    args = parser.parse_args()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory(prefix="jewelmentor-browser-") as temp:
        env = os.environ.copy()
        env.update(JEWELMENTOR_DB=str(Path(temp) / "browser.db"), JEWELMENTOR_PROVIDER="demo")
        with (Path(temp) / "server.log").open("w", encoding="utf-8") as log:
            server = subprocess.Popen(
                [sys.executable, "-m", "jewelmentor.cli", "serve", "--port", str(port)],
                env=env,
                stdout=log,
                stderr=log,
            )
            try:
                for attempt in range(50):
                    try:
                        urllib.request.urlopen(url + "/health", timeout=1).close()
                        break
                    except OSError:
                        if server.poll() is not None or attempt == 49:
                            raise RuntimeError("Smoke-test server did not start") from None
                        time.sleep(0.2)
                with sync_playwright() as p:
                    browser = p.chromium.launch(
                        headless=True,
                        **({"executable_path": args.executable} if args.executable else {}),
                    )
                    page = browser.new_page(
                        viewport={"width": 1500, "height": 1200}, device_scale_factor=1
                    )
                    errors = []
                    page.on("pageerror", lambda exc: errors.append(str(exc)))
                    page.goto(url)
                    expect(page.locator("#send")).to_be_enabled()
                    page.locator("[data-prompt]").first.click()
                    page.click("#send")
                    expect(page.locator(".message.assistant")).to_have_count(1)
                    expect(page.locator("#send")).to_be_enabled()
                    expect(page.locator("#turn-state")).to_have_text("已完成")
                    expect(page.locator("#active-expert")).to_have_text("陈砺")
                    assert "离线演示" in page.locator(".message.assistant").inner_text()
                    assert "kb-objection" in page.locator("#evidence").inner_text()
                    page.locator("#evidence details").first.click()
                    if args.screenshot:
                        args.screenshot.parent.mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(args.screenshot), full_page=True)
                    page.select_option("#expert", "lin")
                    page.fill("#input", "我的顾客预算一万元，应该先问什么？")
                    page.click("#send")
                    expect(page.locator(".message.assistant")).to_have_count(2)
                    expect(page.locator("#send")).to_be_enabled()
                    expect(page.locator("#active-expert")).to_have_text("林知微")
                    page.reload()
                    expect(page.locator("#send")).to_be_enabled()
                    expect(page.locator(".message")).to_have_count(4)
                    page.set_viewport_size({"width": 390, "height": 844})
                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= window.innerWidth"
                    )
                    page.once("dialog", lambda dialog: dialog.accept())
                    page.click("#reset")
                    expect(page.locator("#send")).to_be_enabled()
                    expect(page.locator(".message")).to_have_count(0)
                    expect(page.locator("#turn-state")).to_have_text("等待输入")
                    assert not errors, errors
                    browser.close()
                    print(
                        json.dumps(
                            {
                                "chat": True,
                                "expert_switch": True,
                                "reload": True,
                                "mobile_layout": True,
                                "delete_and_reset": True,
                                "page_errors": errors,
                            }
                        )
                    )
            finally:
                server.terminate()
                server.wait(timeout=10)


if __name__ == "__main__":
    main()
