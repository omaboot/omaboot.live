# omaboot.live: build and check the site.

.PHONY: build check serve

# Writes dist/ and checks it (links, leftover tokens, TODOs, example addresses).
build:
	python3 site_build.py

# What to run before handing a change over: the build and its checks, then the scrub check (no
# private addresses, home paths, keys or the maintainers' host names in the repo).
check: build
	@sh tools/scrub-check.sh

serve:
	python3 site_build.py --serve 8091
