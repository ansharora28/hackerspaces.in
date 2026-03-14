.PHONY: generate build

generate:
	uv run --with pyyaml scripts/generate_site.py data/entries.yml content/spaces

build: generate
	zola build

