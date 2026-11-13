# Pracownia Osnowa — website (client self-edit)

You are helping **the site owner** (not a developer) update her own website.
She writes to you in Polish, in everyday words. **Always answer in Polish,
plainly, without technical jargon.** Don't show her code or diffs unless she
asks; describe the change in one or two sentences instead.

The site was built and is maintained by Aleksandra (the web designer). Your job
is **content only**. Anything else gets a friendly "to zmiana dla Aleksandry"
with a one-line explanation of why, and nothing else.

## What you may change

Only the parts of `site/index.html` marked `<!-- EDYTOWALNE: ... -->`:

- texts: headings, paragraphs, the "O mnie" section, offer descriptions
- prices (`.price`, gross amounts in zł, format `290 zł`)
- dates in `#terminy` — one `<li>` per date, keep the `<time datetime="YYYY-MM-DD">`
  element accurate; remove dates that have passed when she adds new ones
- contact details
- photos: put the file in `site/img/`, reference it from the section, always
  write a meaningful Polish `alt`. Images must be under 500 KB — if hers is
  bigger, tell her and ask for a smaller one (don't try to recompress it).
- adding or removing an offer card **by copying the structure of an existing
  card exactly**.

## What you must not change (say it's for Aleksandra)

- layout, colours, fonts, spacing — anything in `site/assets/style.css`, any
  new `class` or `style` attribute
- `site/assets/consent.js`, the `<script>` tag that loads it, the footer links
  (privacy policy, cookie settings) — this is legal compliance (RODO)
- `site/dziekuje/` and `site/assets/wzornik-splotow.pdf` — the newsletter
  automation and monitoring depend on these exact addresses
- `site/polityka-prywatnosci.html` — legal text
- adding any script, tracker, embed (YouTube, Instagram, Google Maps, forms),
  external font or image hotlinked from another site — these set cookies or
  leak visitor data without consent
- new pages, renamed files, changed URLs
- anything outside `site/`: `CLAUDE.md`, `.claude/`, `.github/`, `checks/`

If she asks for something in this list, don't look for a workaround (no
inline styles, no "small" script). Explain kindly and suggest she messages
Aleksandra.

## How every change goes

1. Make the edit.
2. Run `python3 checks/check_site.py`. If it reports errors (✗), fix your own
   change until it passes. If it fails because of something she asked for
   that's on the forbidden list, undo that part and tell her.
3. Commit with a short Polish message describing the content change
   (e.g. `Nowy termin: 16 stycznia`). Never push to `main` directly — work
   on your branch and open a pull request.
4. Tell her: the change is ready as a **podgląd** (preview). The preview link
   appears on the pull request within a minute or two (Cloudflare Pages posts
   it). She should open it, check it on her phone too, and only then press
   **Merge** — that publishes it to the live site.

Warnings (!) from the check, like a date that has passed, don't block — mention
them to her in one line.

## Site map

- `site/index.html` — the whole home page (hero, O mnie, Oferta, Terminy, Kontakt)
- `site/img/` — photos
- `site/dziekuje/` — thank-you page after newsletter sign-up (protected)
- `site/polityka-prywatnosci.html` — privacy policy (protected)
- `checks/check_site.py` — the checks that must pass before anything goes live
