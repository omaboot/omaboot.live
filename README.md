# omaboot.live

The public site of **OmaBoot? Live**: a bootable USB image, built from Omarchy's own ISO, that tests how well Omarchy runs on an Intel Mac (2006–2020) without installing anything, and reports the results to DoesItOmarchy.com.

Static HTML, no JavaScript, no cookies, no third-party anything. Built by one Python script (stdlib only), like willitomarchy.com, and meant for Cloudflare Pages.

## Build and preview

```sh
python3 site_build.py                 # writes dist/, checks it, lists the owner TODOs
make check                            # the same, then the scrub check (tools/scrub-check.sh)
python3 site_build.py --serve 8091    # preview dist/ at http://127.0.0.1:8091/ (Ctrl+C stops)
```

`--serve` behaves like Cloudflare Pages: directory indexes, `404.html`, `_redirects` and the headers in `_headers`, including the CSP, so a CSP mistake shows up locally.

To see the Download page with a release in it without touching the real data:

```sh
python3 site_build.py --releases data/releases.example.json --out /tmp/omaboot-preview
```

(That build reports `example.com` as a problem on purpose: the check refuses example addresses in anything that ships.)

The build fails if a page links to something that doesn't exist, or if a `{{token}}`, a `TODO` or an example address is left in the output.

## Where things are

| Path | What |
|---|---|
| `pages/*.html` | The copy. One HTML fragment per page; the first two lines are `<!-- title: … -->` and `<!-- description: … -->`. `<!-- TODO(owner): … -->` notes are listed by every build and left out of `dist/`. |
| `site.css` | All styling. The OmaBoot? palette from the prototype; light and dark follow the system setting. Green is reserved for passed tests, so the site uses none. |
| `site_build.py` | The generator. Also draws Boot (the prototype's v16 sprite) and the pixel wordmark as inline SVG, and the favicon. |
| `data/site.json` | Addresses: the source org, the image repo, a contact. Empty values show as plain text, never as broken links; the build lists them as TODOs. |
| `data/releases.json` | Published releases, newest first. `[]` until the first one: the Download page then says the first release is coming soon. |
| `data/releases.example.json` | The shape of one release entry. |
| `data/editions.json` | The editions (Live, Omarchy, Lab): name, role, one line, size, and what the card says until it has a release. Each needs its startup-disk icon in `assets/editions/<id>.png`. |
| `data/tests.json` | The criteria and how OmaBoot? Live tests each one (how it tests, how it decides, how sure it is, what was seen on a real Mac, what could mislead it). Docs makes `/docs/` and one page per test from it. Made from the criteria review (`boot-wip/reviews/criteria-review.html` in the project, boot-live 0.6.3 dev) with dev history taken out; update it when a test changes. |
| `assets/screens/` | Real screens for the home page, drawn by boot-live's own code: `go run ./tools/screens -only NAME -size 180x56x16 -out DIR` (the MacBook Air 13-inch console), with the shown version set to a release (`Version:` in `tools/screens/main.go`). Hero: `hero-quick-pass.webp`, the quick pass and its results as the demo plays them, drawn with `go run ./tools/screens -movie 12 -size 180x56x16 -out FRAMES` and encoded with `ffmpeg -framerate 12 -i FRAMES/%05d.png -c:v libwebp_anim -lossless 1 -loop 0 hero-quick-pass.webp` (lossless, so the console's pixels stay sharp); `hero-results.png` is its last frame, shown instead when the reader asks for less motion; gallery: `4-quick-heat`, `h20-wifi-moving`, `h11-mic-tone-2`, `6-finish-anim`. |
| `assets/editions/` | The editions' startup-disk icons: the 256 px PNG inside each release `.VolumeIcon.icns` of the image build. |
| `assets/fonts/` | JetBrains Mono, Regular and SemiBold (OFL, `OFL.txt`), self-hosted: the CSP allows fonts from the site only. |
| `data/allowed_signers` | The release keys, published at `/allowed_signers`. The Verify page shows their fingerprints, computed at build time. |

## Publishing a release

Add the release to the top of `data/releases.json`, with `"edition"` (`live`, `omarchy` or `lab`; `live` when left out):

```json
{
  "version": "0.5.0", "date": "2026-11-02", "omarchy": "4.0.5",
  "iso": "https://…/omaboot-live-0.5.0.iso", "size": 1987654321,
  "sha256": "<64 hex digits>",
  "sha256sums": "https://…/SHA256SUMS", "signature": "https://…/SHA256SUMS.sig",
  "packages": "https://…", "difference": "https://…", "build_log": "https://github.com/…/actions/runs/…",
  "notes": "optional, one line"
}
```

Every field except `notes` is required and every address must be `https://`. With a release present, `_redirects` also gets `/latest.iso`, `/SHA256SUMS` and `/SHA256SUMS.sig` pointing at the newest one.

## Domains

omaboot.live is the site. **doesitboot.com**, **omaboot.com** and **boot.watch** redirect to it with domain-level Cloudflare redirect rules, which live in Cloudflare, not in this repo. boot.watch's redirect is temporary: it becomes the phone relay's address once that exists. `boot.watch/v1/*` (bootwatchd, the network tests' endpoints) and `status.boot.watch` (bootwatcherd, the status page) are exempt from the redirect; keep both exemptions when the redirect's target changes (bootwatchd's `deploy/cloudflare.sh` re-applies them).

## Deploying

Every push to `main` deploys: GitHub Actions (`.github/workflows/deploy.yml`) runs `make check` (the build, its link and token checks, the scrub check's generic part), then uploads `dist/` with `wrangler pages deploy` to the Cloudflare Pages project `omaboot-live`, which serves omaboot.live. Pull requests get the same checks without the deploy. The workflow needs two repository secrets: `CLOUDFLARE_API_TOKEN` (an account token with Cloudflare Pages: Edit and nothing else) and `CLOUDFLARE_ACCOUNT_ID`. Run `make check` before pushing: with the maintainers' pattern file, it also runs the scrub check's private part, which CI can't.

## Licence

The code (`site_build.py`, `site.css`, `tools/`, the Makefile) is MIT ([LICENSE](LICENSE)). The words and art (the pages' copy, the text in `data/editions.json` and `data/tests.json`, the pictures in `assets/editions/` and `assets/screens/`, and the drawings of Boot, the wordmark and the favicon) are CC BY 4.0 ([LICENSE-CONTENT](LICENSE-CONTENT)). The fonts: JetBrains Mono and Inter are OFL ([OFL.txt](assets/fonts/OFL.txt), [Inter-OFL.txt](assets/fonts/Inter-OFL.txt)); the Omarchy Font, used only for the word Omarchy in the home page's title, is MIT, by Mark Cuda ([OmarchyFont-LICENSE.txt](assets/fonts/OmarchyFont-LICENSE.txt)), a fan font: the Omarchy name and wordmark remain Omarchy's.

The scrub check in `make check` fails on private-network addresses other than the usual examples, home-directory paths, private keys and report keys, and on the maintainers' own host names, read from a patterns file outside the repo (`$OMABOOT_SCRUB_PATTERNS`; skipped with a notice when there is none).
