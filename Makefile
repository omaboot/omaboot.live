# omaboot.live: build and check the site.

.PHONY: build check serve sync-fixes

# Writes dist/ and checks it (links, leftover tokens, TODOs, example addresses).
build:
	python3 site_build.py

# What to run before handing a change over: the build and its checks, the fixes copy against
# DoesItOmarchy.com's registry, then the scrub check (no private addresses, home paths, keys or the
# maintainers' host names in the repo).
check: build
	@python3 tools/sync_fixes.py --check
	@sh tools/scrub-check.sh

# Copies the OmaBoot? fixes from DoesItOmarchy.com into data/fixes.json.
sync-fixes:
	python3 tools/sync_fixes.py

serve:
	python3 site_build.py --serve 8091
