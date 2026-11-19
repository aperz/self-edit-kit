#!/usr/bin/env python3
"""Content validation: refuse bad content before anything is rendered.

    python3 checks/validate_content.py

PROTECTED file. Standard library only. It runs first in the build command
(CI, Netlify, GitHub Pages, pre-commit hook):

    python3 checks/validate_content.py && npx --no @11ty/eleventy && python3 checks/check_site.py

It checks what the client can edit (by the editor at /admin/ or by Claude):

1. content/strona.json, the home page: the same rules the old build.py had
   (field lengths, price as a whole number, ISO dates, safe links, e-mail and
   phone). The messages are unchanged.
2. content/blog/, the blog: only post files, each with exactly the five
   front-matter fields and a body that uses only the allowed Markdown.

Every rule a client could break fails here with a Polish message naming the
file and field, so a bad edit never reaches Eleventy. Eleventy itself
(eleventy.config.js) refuses the dangerous cases again (unsafe link, image
from another site), and check_site.py checks the built pages: three layers,
so one mistake in one of them doesn't publish anything unsafe.

Why the post rules are this strict: Eleventy treats some front-matter keys as
instructions (permalink, layout, eleventyComputed…), executes "---js" front
matter, and reads data files placed next to posts (*.json, *.11tydata.js).
A post is therefore allowed to be only a <slug>.md file with title, date,
excerpt, cover and cover_alt, in plain one-line YAML.
"""
from __future__ import annotations

import html
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content" / "strona.json"
BLOG = ROOT / "content" / "blog"
SITE = ROOT / "site"  # an image path /img/x.webp is the file site/img/x.webp

# Link targets allowed inside strona.json text fields. No javascript:, no data:.
SAFE_URL = re.compile(r"^(https://|mailto:|tel:|/|#)")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE = re.compile(r"^\+?[0-9 ]{9,15}$")

# Blog posts.
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")       # file name without .md
# Field → length limit. The date's limit is loose on purpose so that a
# wrong date gets the "not a RRRR-MM-DD date" message, not a length one.
POST_FIELDS = {"title": 100, "date": 40, "excerpt": 300, "cover": 200, "cover_alt": 200}
MAX_BODY = 20000
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".avif"}
POST_LINK = re.compile(r"^(https://|mailto:)", re.IGNORECASE)


class ContentError(Exception):
    pass


# ---- shared field rules ---------------------------------------------------

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
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ContentError(f"{where}: „{value}” to nie jest data w formacie RRRR-MM-DD.")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ContentError(f"{where}: „{value}” to nie jest data w formacie RRRR-MM-DD.")


def inline_links(text: str) -> None:
    """The [text](url) links in a text field must use a safe scheme.

    Same matching as the renderer (eleventy.config.js, inline()): escape
    first, find the links, unescape the address, so both see the same links.
    """
    escaped = html.escape(text, quote=True)
    for m in re.finditer(r"\[([^\]]+)\]\(([^)\s]+)\)", escaped):
        url = html.unescape(m.group(2))
        if not SAFE_URL.match(url):
            raise ContentError(f"Link „{url}” musi zaczynać się od https://, mailto: lub tel:.")


def local_image(path: str, where: str) -> None:
    """An image path must point into our own /img/ folder, at a file that exists."""
    if not path.startswith("/img/") or ".." in unquote(path) or "?" in path or "#" in path:
        raise ContentError(f"{where}: zdjęcie „{path}” musi leżeć w folderze /img/ tej strony.")
    if Path(path).suffix.lower() not in IMAGE_EXT:
        raise ContentError(f"{where}: „{path}” to nie jest zdjęcie (jpg, png, webp, gif, svg, avif).")
    if not (SITE / path.lstrip("/")).is_file():
        raise ContentError(f"{where}: nie ma zdjęcia {path} — wgraj je najpierw do site{path.rsplit('/', 1)[0]}/.")


# ---- home page --------------------------------------------------------------

def validate_home(c: dict) -> None:
    for path, limit in [("seo.title", 70), ("seo.description", 170),
                        ("hero.title", 80), ("hero.lead", 300), ("hero.button", 30),
                        ("o_mnie.heading", 60), ("oferta.heading", 60),
                        ("terminy.heading", 60), ("kontakt.heading", 60),
                        ("kontakt.address", 120)]:
        field(c, path, limit)

    photo = field(c, "o_mnie.photo", 200)
    if not photo.startswith("/img/") or ".." in photo:
        raise ContentError("Zdjęcie w „O mnie” musi leżeć w folderze /img/.")
    field(c, "o_mnie.photo_alt", 200)
    inline_links(field(c, "o_mnie.text", 2000))

    cards = c.get("oferta", {}).get("cards")
    if not isinstance(cards, list) or not cards:
        raise ContentError("Oferta musi mieć co najmniej jedną kartę.")
    if len(cards) > 6:
        raise ContentError(f"Oferta ma {len(cards)} kart (limit 6).")
    for i, card in enumerate(cards, 1):
        field(card, "title", 80)
        inline_links(field(card, "text", 400))
        price = card.get("price")
        if not isinstance(price, int) or isinstance(price, bool) or not 0 < price <= 100000:
            raise ContentError(f"Karta oferty {i}: cena musi być liczbą złotych (np. 290).")

    items = c.get("terminy", {}).get("items")
    if not isinstance(items, list):
        raise ContentError("Brakuje listy terminów.")
    # Numbered in the order she sees in the editor, so "Termin 2" is her
    # second row (the page sorts them by date).
    for i, it in enumerate(items, 1):
        start = iso_date(field(it, "date", 10), f"Termin {i}")
        end_raw = field(it, "end_date", 10, required=False)
        if end_raw and iso_date(end_raw, f"Termin {i}") < start:
            raise ContentError(f"Termin {start}: data końca jest wcześniejsza niż początek.")
        inline_links(field(it, "text", 200))

    inline_links(field(c, "kontakt.text", 500, required=False))
    email = field(c, "kontakt.email", 100)
    if not EMAIL.match(email):
        raise ContentError(f"„{email}” nie wygląda na adres e-mail.")
    phone = field(c, "kontakt.phone", 20)
    if not PHONE.match(phone):
        raise ContentError(f"„{phone}” nie wygląda na numer telefonu (cyfry i spacje).")


# ---- blog: front matter -----------------------------------------------------

# YAML double-quoted escapes (what the editor writes with yaml_quote: true).
DQ_ESCAPES = {"\\": "\\", '"': '"', "/": "/", "n": "\n", "t": "\t", "0": "\0",
              " ": " ", "_": " ", "N": "\u0085", "L": " ", "P": " "}
# Plain (unquoted) values YAML would read as something other than text.
NOT_TEXT = re.compile(r"^(~|null|Null|NULL|true|True|TRUE|false|False|FALSE"
                      r"|[-+]?(\.[0-9]+|[0-9][0-9_]*(\.[0-9_]*)?)([eE][-+]?[0-9]+)?"
                      r"|0x[0-9a-fA-F]+|0o[0-7]+|[-+]?\.(inf|Inf|INF)|\.(nan|NaN|NAN))$")


def yaml_scalar(raw: str, where: str) -> str:
    """One YAML value on one line: "double", 'single' or plain text.

    A deliberately small subset, so that what this script reads is exactly
    what Eleventy's YAML parser reads. Anything outside it (lists, nesting,
    multi-line values, tags like !!js, anchors) is refused rather than guessed.
    """
    if raw.startswith('"'):
        out, i = [], 1
        while i < len(raw):
            ch = raw[i]
            if ch == '"':
                if raw[i + 1:].strip():
                    raise ContentError(f"{where}: po zamykającym cudzysłowie jest jeszcze tekst.")
                return "".join(out)
            if ch == "\\":
                nxt = raw[i + 1:i + 2]
                if nxt in DQ_ESCAPES:
                    out.append(DQ_ESCAPES[nxt]); i += 2; continue
                size = {"x": 2, "u": 4, "U": 8}.get(nxt)
                code = raw[i + 2:i + 2 + size] if size else ""
                if size and re.fullmatch(r"[0-9a-fA-F]+", code) and len(code) == size:
                    out.append(chr(int(code, 16))); i += 2 + size; continue
                raise ContentError(f"{where}: nieznany znak specjalny „\\{nxt}”.")
            out.append(ch); i += 1
        raise ContentError(f"{where}: brakuje zamykającego cudzysłowu (cała wartość musi być w jednej linii).")
    if raw.startswith("'"):
        m = re.fullmatch(r"'((?:[^']|'')*)'\s*", raw)
        if not m:
            raise ContentError(f"{where}: brakuje zamykającego apostrofu (cała wartość musi być w jednej linii).")
        return m.group(1).replace("''", "'")
    # Plain text: no character YAML would treat as syntax.
    if raw[0] in "!&*[]{}|>%@`#,?:-" or ": " in raw or " #" in raw \
            or raw.endswith(":") or NOT_TEXT.match(raw):
        raise ContentError(f"{where}: ujmij tę wartość w cudzysłów \"…\".")
    return raw


def front_matter(text: str, name: str) -> tuple[dict[str, str], str]:
    """Split a post into its five fields and its Markdown body."""
    if text.startswith("﻿"):
        text = text[1:]
    if not text.startswith("---\n"):
        raise ContentError(f"{name}: wpis musi zaczynać się linią --- (nagłówek z tytułem, datą…).")
    end = text.find("\n---\n", 3)
    if end == -1:
        if text.endswith("\n---"):
            end = len(text) - 4
        else:
            raise ContentError(f"{name}: brakuje linii --- zamykającej nagłówek wpisu.")
    head, body = text[4:end + 1], text[end + 5:]

    data: dict[str, str] = {}
    for n, line in enumerate(head.splitlines(), 2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.fullmatch(r"([a-z_]+):(?:\s+(.*?))?\s*", line)
        if not m or line[0].isspace():
            raise ContentError(f"{name}, linia {n}: oczekiwano „pole: wartość” w jednej linii.")
        key, raw = m.group(1), m.group(2) or ""
        if key not in POST_FIELDS:
            raise ContentError(f"{name}: pole „{key}” jest niedozwolone (dozwolone: {', '.join(POST_FIELDS)}).")
        if key in data:
            raise ContentError(f"{name}: pole „{key}” występuje dwa razy.")
        data[key] = yaml_scalar(raw, f"{name}, pole „{key}”") if raw else ""
    return data, body


# ---- blog: body ---------------------------------------------------------------

# Markdown inline links and images: [text](url) and ![alt](url "title").
MD_LINK = re.compile(r"(!?)\[(?:[^\]\\]|\\.)*\]\(\s*(<[^>]*>|[^\s)]*)")
# Reference definitions: [name]: url
MD_REF = re.compile(r"^ {0,3}\[[^\]]+\]:\s*(<[^>]*>|\S+)", re.MULTILINE)
# Autolinks: <https://…>, <mailto:…>, <javascript:…>
MD_AUTOLINK = re.compile(r"<([A-Za-z][A-Za-z0-9+.-]{1,31}:[^<>\s]*)>")
# Anything that looks like an HTML tag: <script>, </div>, <iframe src=…>, <!-- -->
HTML_TAG = re.compile(r"<(/?[A-Za-z][A-Za-z0-9-]*)(?=[\s/>])[^>]*>|<!--")


def validate_body(body: str, name: str) -> None:
    if len(body) > MAX_BODY:
        raise ContentError(f"{name}: treść ma {len(body)} znaków (limit {MAX_BODY}).")

    # Raw HTML would only show up as literal text (Markdown HTML is switched
    # off), so it is always a mistake: say so instead of publishing it.
    m = HTML_TAG.search(MD_AUTOLINK.sub("", body))
    if m:
        tag = m.group(1) or "!--"
        raise ContentError(f"{name}: we wpisie jest kod HTML (<{tag}…>). Filmy, mapy, formularze i skrypty dodaje "
                           f"tylko Aleksandra; w treści działają nagłówki, pogrubienie, kursywa, listy, cytaty, "
                           f"linki i zdjęcia.")

    for m in MD_LINK.finditer(body):
        is_image, url = m.group(1) == "!", m.group(2).strip("<>")
        if is_image:
            local_image(url, name)
        else:
            post_link(url, name)
    for m in MD_REF.finditer(body):
        # A reference can serve a link or an image; both start with "/" when
        # local, and an image path is also a valid internal link target.
        post_link(m.group(1).strip("<>"), name)
    for m in MD_AUTOLINK.finditer(body):
        if not POST_LINK.match(m.group(1)):
            raise ContentError(f"{name}: link „{m.group(1)}” musi zaczynać się od https:// lub mailto:.")


def post_link(url: str, name: str) -> None:
    """A link in a post: https://, mailto:, or a page of this site.

    Internal links are written from the site root ("/#terminy",
    "/blog/welna-czy-len/"); Eleventy makes them relative per page, so they
    work in a subfolder too. Here we check that the page exists; whether a
    #section exists is checked on the built site by check_site.py, which
    knows every page's ids.
    """
    if POST_LINK.match(url):
        return
    path = unquote(url)  # browsers decode %2e%2e to "..", so check decoded
    if not path.startswith("/") or path.startswith("//") or ".." in path or "\\" in path:
        raise ContentError(f"{name}: link „{url}” musi zaczynać się od https://, mailto: albo / "
                           f"(strona tej witryny, np. /#terminy).")
    page = urlsplit(path).path
    if re.match(r"^/admin(/|$)", page, re.IGNORECASE):
        raise ContentError(f"{name}: link „{url}” prowadzi do edytora — tam linkować nie można.")
    if page in ("/", "/blog", "/blog/"):
        return
    m = re.fullmatch(r"/blog/([^/]+)/?", page)
    if m:
        if not (BLOG / f"{m.group(1)}.md").is_file():
            raise ContentError(f"{name}: link „{url}” prowadzi do wpisu, którego nie ma "
                               f"(brak pliku content/blog/{m.group(1)}.md).")
        return
    target = SITE / page.lstrip("/")
    if not (target.is_file() or (target / "index.html").is_file()):
        raise ContentError(f"{name}: link „{url}” prowadzi do strony, której nie ma.")


def validate_post(path: Path) -> None:
    name = f"content/blog/{path.name}"
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise ContentError(f"{name}: plik nie jest zapisany jako tekst UTF-8.")
    data, body = front_matter(text, name)
    for key, limit in POST_FIELDS.items():
        if key not in data:
            raise ContentError(f"{name}: brakuje pola „{key}”.")
        value = data[key].strip()
        if not value:
            raise ContentError(f"{name}: pole „{key}” jest puste.")
        if len(value) > limit:
            raise ContentError(f"{name}: pole „{key}” ma {len(value)} znaków (limit {limit}).")
    iso_date(data["date"].strip(), name)
    local_image(data["cover"].strip(), f"{name}, okładka")
    if not body.strip():
        raise ContentError(f"{name}: wpis nie ma treści.")
    validate_body(body, name)


def validate_blog() -> int:
    if not BLOG.is_dir():
        return 0
    count = 0
    for p in sorted(BLOG.iterdir()):
        if p.name == ".gitkeep":
            continue
        rel = f"content/blog/{p.name}"
        if p.is_dir():
            raise ContentError(f"{rel}: w folderze bloga nie może być podfolderów — tylko pliki wpisów .md.")
        if p.suffix != ".md":
            raise ContentError(f"{rel}: w folderze bloga mogą leżeć tylko wpisy .md.")
        if not SLUG.match(p.stem):
            raise ContentError(f"{rel}: nazwa pliku to adres wpisu — tylko małe litery bez polskich znaków, "
                               f"cyfry i myślniki (np. jak-wybrac-przedze.md).")
        validate_post(p)
        count += 1
    return count


def main() -> int:
    try:
        try:
            content = json.loads(CONTENT.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ContentError(f"content/strona.json jest uszkodzony (linia {e.lineno}): {e.msg}.")
        validate_home(content)
        posts = validate_blog()
    except ContentError as e:
        print(f"✗ {e}")
        return 1
    print(f"✓ Treść w porządku (strona główna; wpisy na blogu: {posts}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
