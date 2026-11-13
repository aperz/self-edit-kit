# self-edit-kit

Starter repo for a client site the **client edits herself**, through two
doors that end in the same place:

1. **Editor** at `/admin/` ([Sveltia CMS](https://sveltiacms.app), pinned
   0.253.2): a Polish form over `content/strona.json`.
2. **Claude Code on the web** (claude.ai/code, her own Pro plan): "dodaj
   termin 23 stycznia" → Claude edits the same JSON file.

Either way the change becomes a pull request with a Netlify preview, and
publishing it means merging it into `main`, which only works once the checks
pass. Sample client: fictional "Pracownia Osnowa". Status: **demo on
Aleksandra's own GitHub account (aperz)**.

## Layout

| Path | What | Who edits |
|---|---|---|
| `content/strona.json` | all texts, prices, dates, contact | client (editor or Claude) |
| `site/img/uploads/` | uploaded photos | client |
| `templates/index.html` | page layout with `{{ placeholders }}` | owner |
| `build.py` | renders template + content + `site/` → `public/`; validates content | owner |
| `site/` | static files: styles, consent banner, thank-you page, privacy policy, `/admin/` | owner |
| `checks/check_site.py` | the gate: checks the built site + protected-file manifest | owner |

`python3 build.py && python3 checks/check_site.py` is the single check
command: the CI job `site-checks`, Netlify's build command and the
pre-commit hook (`git config core.hooksPath .githooks`). After changing a
protected file on purpose: `python3 checks/check_site.py --update-manifest`.

## Safety layers

| Layer | Where | Stops |
|---|---|---|
| Form limits | `site/admin/config.yml` | wrong types, over-long texts, oversized photos (shrunk to WebP ≤1600 px) |
| Instructions + denies | `CLAUDE.md`, `.claude/settings.json` | Claude touching anything but content |
| Content validation | `build.py` | empty fields, price as text, bad dates/emails, `javascript:` links; HTML always escaped |
| Checks | `checks/check_site.py` | changed protected files (hash manifest), extra scripts/embeds, broken links, missing alt, >500 KB images, missing consent/legal links |
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
6. Claude: install the Claude GitHub app on the repo from claude.ai/code.
7. Live client site: add to `~/Projects/nubaraOS/site-watch/sites.conf` +
   `clients.toml`.

## Demo script

- [ ] Editor: change the price → Save → PR `cms/strona/glowna` + Netlify preview → Publikuj → waits for checks → live
- [ ] Editor: upload a large photo → shrunk to WebP, under 500 KB
- [ ] Claude: "dodaj termin 23 stycznia, warsztat jednodniowy" → PR → preview → Merge → live
- [ ] Claude, forbidden: "zmień kolor przycisku na zielony" → declines
- [ ] Claude, forced: edit `templates/index.html` → denied by permissions; if pushed anyway, `site-checks` fails and the merge is blocked
- [ ] Bad content (price as text) via Claude → build fails, PR blocked, live site unchanged

## Open questions for real clients

- Collaborator + Claude app: can a client with Write access use Claude on a
  repo where the owner installed the app, or does it need an organization?
- Netlify-as-OAuth-provider vs the Worker for the editor sign-in.
