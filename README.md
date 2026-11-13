# self-edit-kit

Starter repo for a client site the **client edits herself through Claude Code
on the web** (claude.ai/code, her own Pro plan). Sample client: fictional
"Pracownia Osnowa". Status: **pilot — tested by Aleksandra on her own
account first**, not yet used with a real client.

## How it works

The client asks Claude, in Polish, for a content change. Claude edits on a
`claude/…` branch and opens a pull request. The hosting posts a preview link
on the PR, she checks the preview, presses Merge, and `main` deploys live.

Safety doesn't rely on Claude behaving. The layers, weakest to strongest:

| Layer | File | Stops |
|---|---|---|
| Instructions | `CLAUDE.md` | Claude knows what counts as content and what to hand back to Aleksandra |
| Permission denies | `.claude/settings.json` | Claude's Edit/Write tools on protected files, force/main pushes |
| Checks | `checks/check_site.py` | protected files changed by any route (hash manifest), extra scripts/trackers/embeds, broken links/anchors, missing alt, >500 KB images, missing consent/legal links |
| Branch protection | GitHub settings | merging while checks fail; touching protected paths without owner review (`CODEOWNERS`) |

`python3 checks/check_site.py` is the single check command. It runs in CI and
in `.githooks/pre-commit`. After changing a protected file on purpose, re-pin it
with `python3 checks/check_site.py --update-manifest`.

## Setup per site

1. **GitHub repo.** Branch protection needs a public repo or GitHub Pro. A
   public repo is fine for a static site (nothing secret lives here).
2. Replace `@OWNER` in `.github/CODEOWNERS`, then run `--update-manifest` and
   commit.
3. **Branch protection on `main`:** require a pull request, require status
   check `site-checks`, require review from Code Owners, block force pushes.
   Don't require approvals on every PR: content PRs should be mergeable by
   her alone.
4. **Cloudflare Pages:** connect the repo, no build command, output dir
   `site`, production branch `main`. Preview deployments for PRs are on by
   default.
5. **Client access:** she gets a GitHub account plus write access, signs in
   to claude.ai/code with GitHub, and the Claude GitHub app is installed on
   the repo. *(Verify during the pilot: whether a collaborator can use a repo
   where the owner installed the app, or whether the repo should live in an
   org she's a member of.)*
6. Custom domain on Cloudflare, then add the site to
   `~/Projects/nubaraOS/site-watch/sites.conf` + `clients.toml`.
7. Give her `JAK-EDYTOWAC.md`.

## Pilot test plan (own account)

- [ ] Content edit: "dodaj termin 23 stycznia, warsztat jednodniowy" → PR, preview, merge, live
- [ ] Photo swap from the phone app
- [ ] Forbidden ask: "zmień kolor przycisku na zielony" → Claude declines, nothing changed
- [ ] Forbidden ask: "dodaj film z YouTube" → declines; if forced, CI fails
- [ ] Deny rule: "edytuj consent.js" → Edit refused by permissions (confirms the `/path` rule syntax)
- [ ] Merge blocked while a check fails
- [ ] Note: as PR author you can't approve your own CODEOWNERS PR — use admin bypass for the test
