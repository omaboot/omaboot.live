# omaboot.live

The public site of **OmaBoot? Live**: a bootable USB image, built from Omarchy's own ISO, that tests how well Omarchy runs on an Intel Mac (2006–2020) without installing anything, and reports the results to DoesItOmarchy.com.

Static HTML, no JavaScript, no cookies, no third-party anything. Built by one Python script (stdlib only), like willitomarchy.com, and meant for Cloudflare Pages.

## Build and preview

```sh
python3 site_build.py                 # writes dist/, checks it, lists the owner TODOs
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
| `data/allowed_signers` | The release keys, published at `/allowed_signers`. The Verify page shows their fingerprints, computed at build time. |

## Publishing a release

Add the release to the top of `data/releases.json`:

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

omaboot.live is the site. **doesitboot.com**, **omaboot.com** and **boot.watch** redirect to it with domain-level Cloudflare redirect rules, which live in Cloudflare, not in this repo. boot.watch's redirect is temporary: it becomes the phone relay's address once that exists.

## Deploying

Not set up yet, on purpose: nothing goes public without the owner's approval. When it is, `dist/` is uploaded to a Cloudflare Pages project (as willitomarchy.com does with `wrangler pages deploy`).
