#!/usr/bin/env python3
"""Render the site: templates/ + content/strona.json + site/ -> public/.

    python3 build.py

PROTECTED file (the owner changes it, the client's editor and Claude don't).
Standard library only, so it runs unchanged in GitHub Actions, on Netlify and
locally.

Mechanism:
1. Copy site/ (static files: styles, consent script, thank-you page, privacy
   policy, images, the /admin/ editor) into a fresh public/.
2. Load content/strona.json and validate it. Every rule a client could break
   (empty heading, price as text, a date that isn't a date, a javascript: link)
   fails the build here with a Polish message naming the field, so a bad edit
   never produces a page.
3. Fill templates/index.html. `{{ a.b }}` is a text field, HTML-escaped.
   `{{ a.b_html }}` is a fragment this script builds (paragraphs, cards, the
   list of dates). An unknown or unused placeholder fails the build, so the
   template and the content can't drift apart silently.

Text fields are plain text. Inside them the client may use exactly two
markups: **bold** and [link text](https://…). Everything else stays literal
text: any HTML she types is escaped and shows up as characters on the page.
"""
from __future__ import annotations

import html
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"
OUT = ROOT / "public"
CONTENT = ROOT / "content" / "strona.json"
TEMPLATE = ROOT / "templates" / "index.html"

MONTHS = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca",
          "sierpnia", "września", "października", "listopada", "grudnia"]

# Link targets allowed inside text fields. No javascript:, no data:.
SAFE_URL = re.compile(r"^(https://|mailto:|tel:|/|#)")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE = re.compile(r"^\+?[0-9 ]{9,15}$")


class ContentError(Exception):
    pass


# ---- reading fields -------------------------------------------------------

def field(data: dict, path: str, max_len: int, required: bool = True) -> str:
    """A text field by dotted path, stripped, checked for presence and length."""
    node = data
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            raise ContentError(f"Brakuje pola „{path}”.")
        node = node[part]
    if not isinstance(node, str):
        raise ContentError(f"Pole „{path}” powinno być tekstem.")
    value = node.strip()
    if required and not value:
        raise ContentError(f"Pole „{path}” jest puste.")
    if len(value) > max_len:
        raise ContentError(f"Pole „{path}” ma {len(value)} znaków (limit {max_len}).")
    return value


def iso_date(value: str, where: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ContentError(f"{where}: „{value}” to nie jest data w formacie RRRR-MM-DD.")


# ---- rendering ------------------------------------------------------------

def inline(text: str) -> str:
    """Escape, then turn **bold** and [text](url) into HTML."""
    out = html.escape(text, quote=True)

    def link(m: re.Match) -> str:
        label, url = m.group(1), html.unescape(m.group(2))
        if not SAFE_URL.match(url):
            raise ContentError(f"Link „{url}” musi zaczynać się od https://, mailto: lub tel:.")
        rel = ' rel="noopener"' if url.startswith("https://") else ""
        return f'<a href="{html.escape(url, quote=True)}"{rel}>{label}</a>'

    out = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, out)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    return out


def paragraphs(text: str) -> str:
    """Blank line = new paragraph, single newline = line break."""
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    return "\n    ".join("<p>" + inline(b).replace("\n", "<br>") + "</p>" for b in blocks)


def polish_date(d: date) -> str:
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def date_range(start: date, end: date | None) -> str:
    if end is None or end == start:
        return polish_date(start)
    if end < start:
        raise ContentError(f"Termin {start}: data końca jest wcześniejsza niż początek.")
    if (start.year, start.month) == (end.year, end.month):
        return f"{start.day}–{polish_date(end)}"
    if start.year == end.year:
        return f"{start.day} {MONTHS[start.month - 1]} – {polish_date(end)}"
    return f"{polish_date(start)} – {polish_date(end)}"


def render_values(c: dict) -> dict[str, str]:
    """Every placeholder value for the template, validated."""
    v: dict[str, str] = {}
    for path, limit in [("seo.title", 70), ("seo.description", 170),
                        ("hero.title", 80), ("hero.lead", 300), ("hero.button", 30),
                        ("o_mnie.heading", 60), ("oferta.heading", 60),
                        ("terminy.heading", 60), ("kontakt.heading", 60),
                        ("kontakt.address", 120)]:
        v[path] = html.escape(field(c, path, limit), quote=True)

    photo = field(c, "o_mnie.photo", 200)
    if not photo.startswith("/img/") or ".." in photo:
        raise ContentError("Zdjęcie w „O mnie” musi leżeć w folderze /img/.")
    alt = field(c, "o_mnie.photo_alt", 200)
    v["o_mnie.photo_html"] = (f'<img src="{html.escape(photo[1:], quote=True)}" '
                              f'alt="{html.escape(alt, quote=True)}" loading="lazy">')
    v["o_mnie.text_html"] = paragraphs(field(c, "o_mnie.text", 2000))

    cards = c.get("oferta", {}).get("cards")
    if not isinstance(cards, list) or not cards:
        raise ContentError("Oferta musi mieć co najmniej jedną kartę.")
    if len(cards) > 6:
        raise ContentError(f"Oferta ma {len(cards)} kart (limit 6).")
    parts = []
    for i, card in enumerate(cards, 1):
        title = field(card, "title", 80)
        text = field(card, "text", 400)
        price = card.get("price")
        if not isinstance(price, int) or isinstance(price, bool) or not 0 < price <= 100000:
            raise ContentError(f"Karta oferty {i}: cena musi być liczbą złotych (np. 290).")
        price_txt = f"{price:,}".replace(",", " ") + " zł"
        parts.append(f'      <article class="card">\n'
                     f'        <h3>{html.escape(title)}</h3>\n'
                     f'        <p>{inline(text)}</p>\n'
                     f'        <p class="price">{price_txt}</p>\n'
                     f'      </article>')
    v["oferta.cards_html"] = "\n".join(parts)

    items = c.get("terminy", {}).get("items")
    if not isinstance(items, list):
        raise ContentError("Brakuje listy terminów.")
    # Validate in the order she sees in the editor (so "Termin 2" means her
    # second row), then sort by date for the page.
    rows = []
    for i, it in enumerate(items, 1):
        start = iso_date(field(it, "date", 10), f"Termin {i}")
        end_raw = field(it, "end_date", 10, required=False)
        end = iso_date(end_raw, f"Termin {i}") if end_raw else None
        rows.append((start, end, field(it, "text", 200)))
    lis = []
    for start, end, text in sorted(rows, key=lambda r: r[0]):
        lis.append(f'      <li><time datetime="{start.isoformat()}">{date_range(start, end)}</time>'
                   f' — {inline(text)}</li>')
    if not lis:
        lis.append("      <li>Nowe terminy wkrótce.</li>")
    v["terminy.items_html"] = "\n".join(lis)

    v["kontakt.text_html"] = paragraphs(field(c, "kontakt.text", 500, required=False))
    email = field(c, "kontakt.email", 100)
    if not EMAIL.match(email):
        raise ContentError(f"„{email}” nie wygląda na adres e-mail.")
    phone = field(c, "kontakt.phone", 20)
    if not PHONE.match(phone):
        raise ContentError(f"„{phone}” nie wygląda na numer telefonu (cyfry i spacje).")
    e = html.escape(email, quote=True)
    v["kontakt.email_html"] = f'<a href="mailto:{e}">{e}</a>'
    v["kontakt.phone_html"] = f'<a href="tel:{phone.replace(" ", "")}">{html.escape(phone)}</a>'
    return v


def fill(template: str, values: dict[str, str]) -> str:
    used: set[str] = set()

    def sub(m: re.Match) -> str:
        key = m.group(1)
        if key not in values:
            raise ContentError(f"Szablon używa nieznanego pola {{{{ {key} }}}}.")
        used.add(key)
        return values[key]

    out = re.sub(r"\{\{\s*([\w.]+)\s*\}\}", sub, template)
    unused = set(values) - used
    if unused:
        raise ContentError(f"Szablon nie używa pól: {', '.join(sorted(unused))}.")
    return out


def build() -> None:
    try:
        content = json.loads(CONTENT.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ContentError(f"content/strona.json jest uszkodzony (linia {e.lineno}): {e.msg}.")
    page = fill(TEMPLATE.read_text(encoding="utf-8"), render_values(content))
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SITE, OUT, ignore=shutil.ignore_patterns(".gitkeep"))
    (OUT / "index.html").write_text(page, encoding="utf-8")


def main() -> int:
    try:
        build()
    except ContentError as e:
        print(f"✗ {e}")
        return 1
    print(f"✓ Zbudowano stronę w {OUT.relative_to(ROOT)}/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
