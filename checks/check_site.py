#!/usr/bin/env python3
"""Site checks: the one command that decides whether a change may go live.

Runs in GitHub Actions on every pull request (a required check, so a failing
run blocks the merge into main) and in the local pre-commit hook. Standard
library only, so CI needs no install step.

    python3 checks/check_site.py                    # run all checks
    python3 checks/check_site.py --update-manifest  # owner only: re-pin protected files

Messages are in Polish because the client may read them in the PR. Errors
(✗) fail the run; warnings (!) are printed but don't block.
"""
from __future__ import annotations

import hashlib
import sys
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
MANIFEST = ROOT / "checks" / "protected.sha256"

# Pages whose URLs other systems depend on (newsletter automation, uptime
# monitoring, links in sent emails). They must always exist.
REQUIRED = [
    "index.html",
    "dziekuje/index.html",
    "polityka-prywatnosci.html",
    "assets/wzornik-splotow.pdf",  # the gift the thank-you page hands out
]

# Files pinned by hash. A content edit never needs to touch these; changing
# them takes the owner (CODEOWNERS review + --update-manifest). Paths are
# relative to the repo root.
PROTECTED = [
    "site/assets/consent.js",
    "site/assets/style.css",
    "site/dziekuje/index.html",
    "site/polityka-prywatnosci.html",
    "site/assets/wzornik-splotow.pdf",
    "checks/check_site.py",
    ".github/workflows/checks.yml",
    ".github/CODEOWNERS",
    ".claude/settings.json",
    "CLAUDE.md",
]

MAX_IMAGE_BYTES = 500 * 1024
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".avif"}


class Page(HTMLParser):
    """Collects the bits of one HTML page the checks look at."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lang = None
        self.title = ""
        self._in_title = False
        self.h1_count = 0
        self.ids: set[str] = set()
        self.refs: list[tuple[str, str, str]] = []  # (tag, attr, url)
        self.scripts: list[str | None] = []  # src, or None for inline
        self.imgs_without_alt: list[str] = []
        self.has_consent_open = False
        self.dates: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.add(a["id"])
        if "data-consent-open" in a:
            self.has_consent_open = True
        if tag == "html":
            self.lang = a.get("lang")
        elif tag == "title":
            self._in_title = True
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "script":
            self.scripts.append(a.get("src"))
        elif tag == "img" and not a.get("alt"):
            self.imgs_without_alt.append(a.get("src", "?"))
        elif tag == "time" and a.get("datetime"):
            self.dates.append(a["datetime"])
        for attr in ("href", "src"):
            if a.get(attr):
                self.refs.append((tag, attr, a[attr]))

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_manifest() -> dict[str, str]:
    out = {}
    if MANIFEST.exists():
        for line in MANIFEST.read_text().splitlines():
            if line.strip():
                digest, name = line.split(maxsplit=1)
                out[name] = digest
    return out


def update_manifest() -> None:
    lines = [f"{sha256(ROOT / p)}  {p}" for p in PROTECTED]
    MANIFEST.write_text("\n".join(lines) + "\n")
    print(f"Zapisano {MANIFEST.relative_to(ROOT)} ({len(lines)} plików).")


def resolve_local(page: Path, url: str) -> Path:
    """Map a site-relative or page-relative URL onto a file under site/."""
    path = unquote(urlsplit(url).path)
    target = SITE / path.lstrip("/") if path.startswith("/") else page.parent / path
    if path.endswith("/") or target.is_dir():
        target = target / "index.html"
    return target.resolve()


def check() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    for rel in REQUIRED:
        if not (SITE / rel).is_file():
            errors.append(f"Brakuje wymaganego pliku site/{rel} — ten adres musi istnieć.")

    pinned = load_manifest()
    for rel in PROTECTED:
        f = ROOT / rel
        if not f.is_file():
            errors.append(f"Brakuje chronionego pliku {rel}.")
        elif pinned.get(rel) != sha256(f):
            errors.append(f"Zmieniono chroniony plik {rel} — to zmiana dla Aleksandry, nie treści.")

    pages = sorted(SITE.rglob("*.html"))
    parsed: dict[Path, Page] = {}
    for p in pages:
        pg = Page()
        pg.feed(p.read_text(encoding="utf-8"))
        parsed[p.resolve()] = pg

    today = date.today().isoformat()
    for p, pg in parsed.items():
        name = p.relative_to(SITE.resolve())
        if pg.lang != "pl":
            errors.append(f"{name}: brak lang=\"pl\" w <html>.")
        if not pg.title.strip():
            errors.append(f"{name}: pusty <title>.")
        if pg.h1_count != 1:
            errors.append(f"{name}: strona powinna mieć dokładnie jeden nagłówek <h1> (jest {pg.h1_count}).")

        # Consent: every page loads consent.js, and nothing else runs scripts.
        # Any extra script (inline or external) could set cookies or track
        # visitors before consent — that needs the owner, not a content edit.
        local_scripts = [s for s in pg.scripts if s and s.endswith("assets/consent.js")]
        if not local_scripts:
            errors.append(f"{name}: strona nie wczytuje assets/consent.js (baner cookies).")
        for s in pg.scripts:
            if s is None or not s.endswith("assets/consent.js"):
                errors.append(f"{name}: dodatkowy skrypt ({s or 'wbudowany <script>'}) — skrypty dodaje tylko Aleksandra.")

        for tag, attr, url in pg.refs:
            parts = urlsplit(url)
            if parts.scheme in ("mailto", "tel"):
                continue
            if parts.scheme or url.startswith("//"):
                # Outgoing links are fine; embedded third-party resources
                # (images, iframes, styles, fonts) leak visitor IPs without consent.
                if tag != "a":
                    errors.append(f"{name}: <{tag}> wczytuje zewnętrzny zasób {url} — wgraj plik do site/ zamiast linkować.")
                continue
            if url.startswith("#"):
                if url != "#" and url[1:] not in pg.ids:
                    errors.append(f"{name}: kotwica {url} nie wskazuje żadnej sekcji.")
                continue
            target = resolve_local(p, url)
            if SITE.resolve() not in target.parents:
                errors.append(f"{name}: link {url} wychodzi poza katalog strony.")
            elif not target.exists():
                errors.append(f"{name}: link {url} prowadzi do nieistniejącego pliku.")

        for src in pg.imgs_without_alt:
            errors.append(f"{name}: obrazek {src} nie ma opisu alt (potrzebny dla czytników ekranu).")

        for d in pg.dates:
            if d[:10] < today:
                warnings.append(f"{name}: termin {d} już minął — może warto go usunąć.")

    index = parsed.get((SITE / "index.html").resolve())
    if index:
        targets = {u for _, _, u in index.refs}
        if "polityka-prywatnosci.html" not in targets:
            errors.append("index.html: w stopce brakuje linku do polityki prywatności.")
        if not index.has_consent_open:
            errors.append("index.html: w stopce brakuje linku „Ustawienia cookies”.")

    for f in SITE.rglob("*"):
        if f.suffix.lower() in IMAGE_EXT and f.stat().st_size > MAX_IMAGE_BYTES:
            kb = f.stat().st_size // 1024
            errors.append(f"{f.relative_to(SITE)}: obrazek ma {kb} KB (limit 500 KB) — trzeba go zmniejszyć.")

    return errors, warnings


def main() -> int:
    if "--update-manifest" in sys.argv:
        update_manifest()
        return 0
    errors, warnings = check()
    for w in warnings:
        print(f"! {w}")
    for e in errors:
        print(f"✗ {e}")
    if errors:
        print(f"\nBłędy: {len(errors)}. Ta zmiana nie może trafić na stronę, dopóki ich nie poprawimy.")
        return 1
    print("✓ Wszystkie sprawdzenia przeszły.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
