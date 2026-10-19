#!/usr/bin/env python3
"""Copy the OmaBoot? fixes from DoesItOmarchy.com into data/fixes.json, or check that copy.

Usage: tools/sync_fixes.py [--from SNAPSHOT.json]           write data/fixes.json
       tools/sync_fixes.py --check [--from SNAPSHOT.json]   exit 1 when data/fixes.json is stale

The fix registry lives in DoesItOmarchy's data/fixes.yaml: reports are checked against its IDs, so
it stays the only place a fix is defined. The site builds /fixes/ from this copy, taken from the
catalog snapshot (GET /api/v1/snapshot, the same file OmaBoot? Live carries), with the levels a fix
can live at (fix_levels) and the names of the configurations and criteria the fixes mention. What
only this site says about a fix is in data/fixes-detail.json.

--check fetches the snapshot and compares; `make check` runs it, so CI fails once the registry
changes until the copy is synced. When DoesItOmarchy.com can't be reached it says so and passes:
an outage shouldn't block a deploy. Stdlib only.
"""
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "data", "fixes.json")
SITE = json.load(open(os.path.join(HERE, "data", "site.json")))["doesitomarchy"]
SNAPSHOT = SITE + "/api/v1/snapshot"


def fetch():
    req = urllib.request.Request(SNAPSHOT, headers={"User-Agent": "omaboot.live site build (tools/sync_fixes.py)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def extract(snap):
    """The fixes, and the names of what they mention, from a catalog snapshot."""
    fixes = snap["fixes"]
    if "fix_levels" not in snap or any("levels" not in f for f in fixes):
        sys.exit("sync_fixes: the snapshot has no fix levels: DoesItOmarchy.com needs the release that adds them (fix_levels)")
    want = {c for f in fixes for c in f.get("configs", []) + f.get("tested_on", [])}
    configs = {}
    for m in snap["match"]["macs"]:
        for r in m["releases"]:
            for c in r["configs"]:
                if c["id"] in want:
                    configs[c["id"]] = {"name": r["name"], "identifier": m["identifier"],
                                        "url": f'{SITE}/mac/{m["identifier"].replace(",", "-")}#cfg-{c["id"]}'}
    missing = want - set(configs)
    if missing:
        sys.exit(f"sync_fixes: configurations not in the snapshot: {', '.join(sorted(missing))}")
    used = {c for f in fixes for c in f.get("criteria", [])}
    criteria = {c["id"]: c["name"] for c in snap["capabilities"] if c["id"] in used}
    return {"_source": f"{SNAPSHOT} (fixes), by tools/sync_fixes.py: don't edit by hand",
            "fixes": fixes, "fix_levels": snap["fix_levels"], "configs": dict(sorted(configs.items())),
            "criteria": dict(sorted(criteria.items()))}


def main(argv):
    src = argv[argv.index("--from") + 1] if "--from" in argv else None
    try:
        snap = json.load(open(src)) if src else fetch()
    except OSError as e:
        if "--check" in argv and not src:
            print(f"sync_fixes: {SNAPSHOT} unreachable ({e}); fixes copy not checked", file=sys.stderr)
            return 0
        raise
    data = extract(snap)
    if "--check" in argv:
        have = json.load(open(OUT)) if os.path.exists(OUT) else None
        if have != data:
            print("sync_fixes: data/fixes.json differs from DoesItOmarchy.com's fix registry: run tools/sync_fixes.py, "
                  "then update data/fixes-detail.json for any new fix", file=sys.stderr)
            return 1
        print(f"sync_fixes: data/fixes.json matches DoesItOmarchy.com ({len(data['fixes'])} fixes)", file=sys.stderr)
        return 0
    with open(OUT, "w") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(f"sync_fixes: wrote data/fixes.json ({len(data['fixes'])} fixes)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
