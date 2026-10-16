#!/usr/bin/env python3
"""Turn a release's report files into data/reports/<version>.json, from which site_build.py makes
the release's page (/releases/<version>/): what differs from the official Omarchy ISO, and why.

Usage: tools/release_report.py DIR [--out data/reports]
DIR holds the files the image build publishes with every release (all in its signed SHA256SUMS):
build-info.json, packages.tsv and diff-report.tsv (or diff-report.tsv.gz). Only public facts are
kept: no build-machine paths, and the CI run only when it's on GitHub.

Groups of differing files with more than LIST_MAX paths (the files of an added package, say) keep
their count only; the full list stays in diff-report.tsv.gz, linked from the page.
"""
import argparse
import gzip
import json
import os
import sys

LIST_MAX = 150


def rows(path):
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            yield line.rstrip("\n").split("\t")


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "reports"))
    a = ap.parse_args(argv)
    info = json.load(open(os.path.join(a.dir, "build-info.json")))
    diff = next((os.path.join(a.dir, n) for n in ("diff-report.tsv.gz", "diff-report.tsv") if os.path.exists(os.path.join(a.dir, n))), None)
    if not diff:
        sys.exit(f"{a.dir}: no diff-report.tsv(.gz)")
    version = info["tag"].removeprefix("v")

    pkgs = list(rows(os.path.join(a.dir, "packages.tsv")))  # name version repo file sha256 official
    # packages.tsv's last column: "same" when the file is the official ISO's own (its installer
    # mirror carries every package), else "added" (not on the official ISO at all)
    official = {p[0]: p[5] == "same" for p in pkgs}
    version_of = {p[0]: (p[1], p[2]) for p in pkgs}
    changes = []  # the live system's package changes against the official live system
    groups = {}
    for area, path, difference, category, explanation in rows(diff):
        if area == "package":
            changes.append({"name": path, "change": difference.split()[0], "version": version_of.get(path, ("", ""))[0],
                            "repo": version_of.get(path, ("", ""))[1], "official_file": official.get(path, False), "why": explanation})
            continue
        g = groups.setdefault((category, explanation), {"category": category, "explanation": explanation, "count": 0, "files": []})
        g["count"] += 1
        g["files"].append([area, path, difference])
    for g in groups.values():
        if g["count"] > LIST_MAX:
            g["files"] = []
    order = {"unexplained": 0, "ours": 1, "generated": 2, "package": 3}
    group_list = sorted(groups.values(), key=lambda g: (order.get(g["category"], 9), -g["count"], g["explanation"]))
    by_cat = {}
    for g in group_list:
        by_cat[g["category"]] = by_cat.get(g["category"], 0) + g["count"]

    oi = info.get("official_iso", {})
    bl = info.get("boot_live", {})
    ci = info.get("ci", {})
    run = ci.get("run_url") or ci.get("url") or ""
    out = {
        "version": version, "tag": info["tag"], "edition": info.get("edition", "live"), "omarchy": info["omarchy"],
        "built_at": info.get("built_at", ""),
        "official_iso": {k: oi.get(k, "") for k in ("url", "sha256", "omarchy_iso_commit", "signature")},
        "fork_commit": info.get("fork_commit", ""),
        "arch_archive_date": info.get("packages", {}).get("arch_archive_date", ""),
        "boot_live": {k: bl.get(k, "") for k in ("version", "tag", "commit", "sha256")},
        "build_run": run if run.startswith("https://github.com/") else "",
        "counts": {"packages": len(pkgs), "official_files": sum(official.values()),
                   "added": sum(1 for c in changes if c["change"] == "added"),
                   "removed": sum(1 for c in changes if c["change"] == "removed"),
                   "changed": sum(1 for c in changes if c["change"] not in ("added", "removed")),
                   "files_differing": sum(by_cat.values()), "unexplained": by_cat.get("unexplained", 0), "by_category": by_cat},
        "package_changes": changes,
        "groups": group_list,
    }
    os.makedirs(a.out, exist_ok=True)
    target = os.path.join(a.out, f"{version}.json")
    json.dump(out, open(target, "w"), indent=1, ensure_ascii=False)
    print(f"{target}: {out['counts']['files_differing']} differing files in {len(group_list)} groups, {out['counts']['added']} packages added, {out['counts']['official_files']} of {out['counts']['packages']} the official ISO's own files")


if __name__ == "__main__":
    main(sys.argv[1:])
