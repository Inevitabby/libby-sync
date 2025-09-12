#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["patchright"]
# ///
"""Download ACSM files (ebooks) from Libby.

Setup:  uvx patchright install chromium && ./dl.py login
Usage:  ./dl.py [--dry-run]
"""
import argparse
import re
import sys
from pathlib import Path
from typing import NamedTuple

from patchright.sync_api import Error, sync_playwright

BASE = "https://libbyapp.com"
PROFILE = Path.home() / ".config/libbydl/profile"
OUT = Path(__file__).resolve().parent / "acsm"

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
    if not epub.is_visible():  # on some books it's behind "Other Options..."
        more = page.locator(".circ-fulfill-loan-secondary-expando button")
        if not more.count():
            raise Error("no EPUB download available")
        more.click()

    with page.expect_download() as dl:
        epub.click()
    dest = OUT / dl.value.suggested_filename
    dl.value.save_as(dest)
    return dest


KINDS = {
    "book": (fulfill, OUT, "*_{}.acsm"),
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
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE), channel="chromium", headless=False, no_viewport=True,
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
