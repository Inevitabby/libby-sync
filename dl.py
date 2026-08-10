#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["patchright"]
# ///
"""Download ACSM files (ebooks) and MP3 parts (audiobooks) from Libby.

Setup:  uvx patchright install chromium && ./dl.py login
Usage:  ./dl.py [--dry-run]
"""
import argparse
import re
import sys
from pathlib import Path
from typing import NamedTuple
from urllib.parse import unquote, urlsplit

from patchright.sync_api import Error, sync_playwright

BASE = "https://libbyapp.com"
PROFILE = Path.home() / ".config/libbydl/profile"
OUT = Path(__file__).resolve().parent / "acsm"
AUDIO = OUT.parent / "audio_parts"

TILES_JS = """
() => [...document.querySelectorAll('.title-tile')].map(t => ({
  cls: t.className,
  href: t.querySelector('a[href^="/shelf/loans/"][href*="/return"]')?.getAttribute('href'),
  title: t.querySelector('.title-tile-title')?.textContent ?? '',
}))
"""


class Loan(NamedTuple):
    id: str
    card: str | None
    kind: str | None
    title: str


def list_loans(page) -> list[Loan]:
    try:
        with page.expect_response(
            lambda r: "sentry.libbyapp.com/chip/sync" in r.url and r.ok, timeout=30_000
        ):
            page.goto(f"{BASE}/shelf/loans", wait_until="domcontentloaded")
    except Error:
        sys.exit(f"Not logged in. Run: {sys.argv[0]} login")

    try:
        page.wait_for_selector(".title-tile", timeout=15_000)
    except Error:
        return []
    page.wait_for_timeout(500)

    loans = []
    for t in page.evaluate(TILES_JS):
        tid = re.search(r"data-title_(\S+)", t["cls"])
        kind = re.search(r"data-title-tile-format_(\S+)", t["cls"])
        if not tid:
            continue
        # return link is /shelf/loans/<card>-<title>/return
        card = t["href"].split("/")[3].rsplit("-", 1)[0] if t["href"] else None
        loans.append(Loan(tid[1], card, kind[1] if kind else None, " ".join(t["title"].split())))
    return loans


def fulfill(page, loan: Loan) -> Path:
    page.goto(f"{BASE}/shelf/loans/{loan.card}-{loan.id}/fulfill", wait_until="domcontentloaded")

    options = page.locator("button.circ-option-fulfill-loan")
    epub = options.filter(
        has=page.locator("h2.circ-option-fulfill-loan-sup-type", has_text=re.compile(r"^\s*EPUB\s*$"))
    ).filter(has=page.locator(".circ-option-fulfill-loan-drm-badge"))

    options.first.wait_for()
    if not epub.is_visible(): # (on some books it's behind "Other Options...")
        more = page.locator(".circ-fulfill-loan-secondary-expando button")
        if not more.count():
            raise Error("no EPUB download available")
        more.click()

    with page.expect_download() as dl:
        epub.click()
    dest = OUT / dl.value.suggested_filename
    dl.value.save_as(dest)
    return dest


def part_name(url: str) -> str:
    return unquote(urlsplit(url).path.rsplit("/", 1)[-1])


def page_js(frame, js, arg=None):
    return frame.evaluate(js, arg, isolated_context=False)


def player_frame(page):
    for _ in range(40):
        for f in page.frames:
            try:
                if page_js(f, "window.BIF?.objects?.compass && window.BIF.objects.spool?.components?.length"):
                    return f
            except Error:
                pass
        page.wait_for_timeout(500)
    raise Error("audiobook player not found in: " + ", ".join(f.url for f in page.frames))


def listen(page, loan: Loan) -> Path:
    """Open the player, let it request each MP3 part itself, and save what it requested."""
    urls = {}

    def note(req):
        if ".mp3" in req.url:
            urls[part_name(req.url)] = req.url

    page.on("request", note)
    page.goto(f"{BASE}/shelf/loans", wait_until="domcontentloaded")
    page.locator(f".title-tile.data-title_{loan.id}").get_by_text("Open Audiobook").click()
    player = player_frame(page)
    resume = page_js(player, "BIF.objects.spool.focus?.floc ?? 0")
    parts = [unquote(p) for p in page_js(player, "BIF.objects.spool.components.map(c => c.meta.path)")]
    player.locator("button[aria-label='Play']").click()

    tmp = AUDIO / f".{loan.id}.part"
    tmp.mkdir(exist_ok=True)
    for i, name in enumerate(parts):
        if name not in urls:
            with page.expect_event("request", lambda r: ".mp3" in r.url and part_name(r.url) == name):
                page_js(player, "i => BIF.objects.compass.at({floc: i + 0.5}).seek()", i)
        r = page.request.get(urls[name], timeout=0)
        if not r.ok:
            raise Error(f"{name}: HTTP {r.status}")
        (tmp / f"{i + 1:03}.mp3").write_bytes(r.body())
    page_js(player, "f => BIF.objects.compass.at({floc: f}).seek()", resume)

    title = re.sub(r"[^\w -]", "", loan.title)
    return tmp.rename(AUDIO / f"{title}_{loan.id}")


KINDS = {
    "book": (fulfill, OUT, "*_{}.acsm"),
    "audiobook": (listen, AUDIO, "*_{}"),
}


def run(page, dry_run: bool) -> int:
    fetched = failed = 0
    for loan in list_loans(page):
        label = f"{loan.id}  {loan.title}"
        grab, out, done = KINDS.get(loan.kind, (None, None, None))
        if not grab:
            print(f"[skip]  {label} - format={loan.kind}")
        elif next(out.glob(done.format(loan.id)), None):
            print(f"[skip]  {label} - already downloaded")
        elif dry_run:
            print(f"[would] {label}")
        else:
            print(f"[fetch] {label}")
            try:
                print(f"[ok]    saved {grab(page, loan)}")
                fetched += 1
            except Error as e:
                failed += 1
                print(f"[FAIL]  {label} - {str(e).splitlines()[0]}", file=sys.stderr)
            page.wait_for_timeout(500)
    print(f"Done: {fetched} fetched, {failed} failed.")
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", nargs="?", choices=["run", "login"], default="run")
    ap.add_argument("--dry-run", action="store_true", help="it's the opposite of a wet run")
    args = ap.parse_args()

    PROFILE.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(exist_ok=True)
    AUDIO.mkdir(exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE), channel="chromium", headless=False, no_viewport=True,
            args=["--mute-audio"],
        )
        ctx.set_default_timeout(20_000)
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            if args.command == "login":
                page.goto(BASE)
                input("Log in to Libby in the browser, then press Enter here... ")
                return 0
            return run(page, args.dry_run)
        finally:
            ctx.close()


if __name__ == "__main__":
    sys.exit(main())
