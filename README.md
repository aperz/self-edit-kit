# self-edit-kit

Starter repo for a client site the **client edits herself** in the
**editor** at `/admin/` ([Sveltia CMS](https://sveltiacms.app), pinned
0.253.2): a Polish form over `content/strona.json` and the blog posts in
`content/blog/`. Her whole routine is: log in → edit → **Zapisz** →
**Opublikuj** (preview optional). The client guide is `JAK-EDYTOWAC.md`.

Under the hood every save is a pull request with a Netlify preview, and
Opublikuj merges it into `main`, which only works once the checks pass.
She never needs to see GitHub.

**Claude Code on the web is optional and off by default.** It works on the
same files under `CLAUDE.md` + `.claude/settings.json`, but it shows the
client GitHub pull requests and Merge buttons, which confused non-technical
users. Enable it only for a client who's comfortable with that (install the
Claude GitHub app, add a Claude section to her guide). The rules stay in the
repo either way: they also govern the owner's own Claude sessions.

**No one-click "Zapisz i opublikuj".** Sveltia's `direct_publish` commits
straight to `main` without a pull request, which the `checks` ruleset
rejects, so the first one-click save would fail. Opublikuj right after
Zapisz is the equivalent: the editor waits for the checks, then merges.

Sample client: fictional "Pracownia Osnowa". Status: **demo on
Aleksandra's own GitHub account (aperz)**.

## Layout

| Path | What | Who edits |
|---|---|---|
| `content/strona.json` | home page: texts, prices, dates, contact | client (editor or Claude) |
| `content/blog/*.md` | blog posts: five front-matter fields + Markdown body | client (editor or Claude) |
| `site/img/uploads/`, `site/img/blog/` | uploaded photos (home page, blog) | client |
| `templates/pages/` | page templates: `index.njk` (home), `blog.njk` (`/blog/` list) | owner |
| `templates/layouts/` | `base.njk` (blog frame), `post.njk` (one post) | owner |
| `eleventy.config.js` | rendering: closed input, Markdown rules, filters, relative URLs | owner |
| `package.json`, `package-lock.json` | Eleventy 3.1.8, pinned exactly; nothing else | owner |
| `checks/validate_content.py` | content rules for `strona.json` and every post (Polish messages) | owner |
| `checks/check_site.py` | the gate: checks the built site + protected-file manifest | owner |
| `site/` | static files: styles, consent banner, thank-you page, privacy policy, `/admin/` | owner |

## Build

```sh
npm ci   # once per clone: the pinned Eleventy
python3 checks/validate_content.py && npx --no @11ty/eleventy && python3 checks/check_site.py
```

That one command (also `npm run build`) is the CI job `site-checks`,
Netlify's build command, the GitHub Pages deploy and the pre-commit hook
(`git config core.hooksPath .githooks`):

1. `validate_content.py` (Python, stdlib) refuses bad content before
   anything renders.
2. Eleventy renders `templates/` + `content/` + `site/` into `public/`
   (wiped first, so deleted posts don't linger).
3. `check_site.py` checks what would be served.

`npx --no` runs the locally installed Eleventy and refuses to download one.
After changing a protected file on purpose:
`python3 checks/check_site.py --update-manifest`.

The home page renders byte-for-byte as it did with the old `build.py`
(apart from the new Blog link and a comment); the inline markup in
`strona.json` (`**bold**`, `[text](https://…)`, everything else escaped) is
the same code ported to JavaScript.

### Subfolder or domain root

The same `public/` works at a domain root (Netlify) and under
`/self-edit-kit/` (GitHub Pages) with no setting: templates and posts write
internal URLs from the root (`/assets/style.css`, `/img/blog/x.webp`) and
the `relative-urls` transform rewrites each one relative to its page
(`../../assets/style.css` on `/blog/<slug>/`). `check_site.py` fails if a
root-absolute URL survives. A custom domain needs no change either.

## Safety layers

| Layer | Where | Stops |
|---|---|---|
| Form limits | `site/admin/config.yml` | wrong types, over-long texts, oversized photos (shrunk to WebP ≤1600 px) |
| Instructions + denies | `CLAUDE.md`, `.claude/settings.json` | Claude touching anything but content (incl. `npm install`) |
| Content validation | `checks/validate_content.py` | empty fields, price as text, bad dates/emails, unsafe links; in posts: any HTML, links other than `https://`/`mailto:`/root-relative (`/#terminy`, `/blog/<slug>/`; never `//…` or `/admin/`), links to missing posts/pages, photos not in `/img/`, missing or extra front-matter fields (`permalink`, `layout`…), `---js` front matter, non-post files in `content/blog/` |
| Rendering | `eleventy.config.js` | the same dangers again, if validation were skipped: Markdown HTML off (escaped), no template language in posts (`{{ }}` is text), JS front matter and data files off, post address/layout fixed, unsafe links/images fail the build, only `templates/` + `content/blog/*.md` are read |
| Checks | `checks/check_site.py` | changed protected files (hash manifest) or an unpinned new file in `templates/`, extra scripts/embeds, `javascript:` hrefs, root-absolute URLs, broken links and missing `#sections` on the target page, links into `/admin/`, missing alt, >500 KB images, missing consent/legal links — on every visitor page incl. the blog |
| Ruleset on `main` | GitHub | merging without a PR or with failing `site-checks`; protected paths without owner review (`CODEOWNERS`) |
| Netlify build | `netlify.toml` | a broken build ever going live: production keeps the last good deploy |

The editor's own publish check adds one more: Sveltia refuses to publish a
pull request that holds anything but the entry's own files.

## Setup (per site)

1. Public repo (rulesets are free on public repos; private needs GitHub Pro).
2. Repo settings: allow auto-merge, delete branches after merge.
3. Rulesets on `main`:
   - **checks** (no bypass): require status check `site-checks`, block
     force-push and deletion.
   - **review**: require a pull request, 0 approvals, code-owner review;
     the repository admin may bypass (so the owner can merge her own changes
     to protected files).
4. Netlify: import the repo; `netlify.toml` sets the build. Deploy previews
   on PRs are on by default. Then update `site_url` in `site/admin/config.yml`.
5. Editor sign-in:
   - demo / owner: "Sign In with Token" — fine-grained PAT for this repo
     only, Contents + Pull requests read/write;
   - client: OAuth through Netlify (Netlify as OAuth provider) or the
     Sveltia CMS Authenticator Worker. GitHub has no browser-only (PKCE)
     login yet.
6. Netlify visitor access: protect nothing, or the client can't open the
   preview links (team-wide "Netlify login" protection covers every project).
7. Optional, only for a technical client: Claude — install the Claude GitHub
   app on the repo from claude.ai/code and add a Claude section to her guide.
8. Live client site: add it to uptime/site monitoring.
9. Onboarding: a 10-minute screen-share where she publishes one change and
   one blog post herself, plus `JAK-EDYTOWAC.md`.

**Rule for every config change:** anything the editor's form lets her do
must pass the checks. The checks exist to stop Claude or something unusual,
never to reject a normal editor save. (Learned 2026-11-19: Sveltia's
default stock-photo search inserted external URLs that the checks refuse,
so the publish failed with no explanation in the editor. Fixed by
`stock_assets.providers: []`.)

## Demo script

Editor (the client's path):

- [ ] Change the price → Zapisz → Opublikuj straight away → waits for checks → live
- [ ] Upload a phone photo (several MB) → accepted, shrunk to WebP under 500 KB
- [ ] Blog → Nowy wpis → title "Wełna czy len?" → address `welna-czy-len`, uploaded cover → Zapisz → preview at `/blog/welna-czy-len/` → Opublikuj
- [ ] No stock-photo tab in the image picker

Optional Claude path (owner / technical clients):

- [ ] "dodaj termin 23 stycznia, warsztat jednodniowy" → PR → preview → Merge → live
- [ ] Forbidden: "zmień kolor przycisku na zielony" → declines
- [ ] Forced: edit `templates/pages/index.njk` → denied by permissions; if pushed anyway, `site-checks` fails and the merge is blocked
- [ ] Bad content (price as text) → build fails, PR blocked, live site unchanged
- [ ] Forbidden: "wstaw do wpisu film z YouTube" → declines; if an `<iframe>` is pushed anyway, `validate_content.py` fails and the merge is blocked

## Open questions for real clients

- Collaborator + Claude app: can a client with Write access use Claude on a
  repo where the owner installed the app, or does it need an organization?
- Netlify-as-OAuth-provider vs the Worker for the editor sign-in.
