#!/usr/bin/env python3
"""Generate Zola content pages from space data in entries.yml.
Usage: python generate_site.py <entries.yml> <content_dir>
"""

import csv
import os
import re
import sys
import yaml


# "spaces" collides with the section directory name
RESERVED_SLUGS = {"spaces"}

def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def to_toml_array(items):
    return "[" + ", ".join(f'"{i}"' for i in items) + "]"


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <entries.yml> <content_dir>", file=sys.stderr)
        sys.exit(1)

    entries_path = sys.argv[1]
    content_dir = sys.argv[2]

    with open(entries_path) as f:
        all_entries = yaml.safe_load(f)

    entries = [e for e in all_entries if e.get("active", True)]
    skipped = len(all_entries) - len(entries)

    # Derive sibling paths from content_dir (e.g. content/spaces -> content, static)
    site_root = os.path.dirname(os.path.dirname(content_dir))
    os.makedirs(content_dir, exist_ok=True)

    # Remove any pre-existing .md files.
    for f in os.listdir(content_dir):
        if f.endswith(".md") and f != "_index.md":
            os.remove(os.path.join(content_dir, f))

    # Main section index
    parent_content_dir = os.path.dirname(content_dir)
    with open(os.path.join(parent_content_dir, "_index.md"), "w") as f:
        f.write("+++\ntitle = \"Community & Public Spaces in India\"\nsort_by = \"title\"\n+++\n")

    # Spaces section index (transparent so entries appear under root)
    with open(f"{content_dir}/_index.md", "w") as f:
        f.write("+++\ntitle = \"Spaces\"\nsort_by = \"title\"\ntransparent = true\n+++\n")

    # Detect duplicate name slugs and disambiguate with city
    from collections import Counter
    slug_counts = Counter(slugify(e["name"]) for e in entries)

    for entry in entries:
        city = entry['city'][0]
        base_slug = slugify(entry["name"])
        if slug_counts[base_slug] > 1 or base_slug in RESERVED_SLUGS:
            slug = f"{base_slug}-{slugify(city)}"
        else:
            slug = base_slug
        coords = entry.get("coords", [0, 0])

        frontmatter = f"""+++
title = "{entry['name'].replace('"', '\\"')}"
description = "{entry.get('description', '').replace('"', '\\"')}, {city}"

[taxonomies]
states = ["{entry['state']}"]
cities = ["{city}"]
categories = {to_toml_array(entry.get('categories', []))}

[extra]
address = "{entry.get('address', '').replace('"', '\\"')}"
pincode = "{entry.get('pincode', '')}"
lat = {coords[0]}
lng = {coords[1]}
url = "{entry.get('url', '')}"
tags = {to_toml_array(entry.get('tags', []))}
city = "{city}"
"""
        if len(entry['city']) > 1:
            frontmatter += f'city_aliases = {to_toml_array(entry["city"])}\n'
        frontmatter += "+++\n"
        body = entry.get('description', '')
        filepath = os.path.join(content_dir, f"{slug}.md")
        with open(filepath, "w") as f:
            f.write(frontmatter)
            f.write(f"\n{body}\n")

    # Generate CSV for download
    static_dir = os.path.join(site_root, "static")
    os.makedirs(static_dir, exist_ok=True)
    csv_path = os.path.join(static_dir, "spaces.csv")

    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "city", "state", "address", "pincode", "lat", "lng", "url", "description", "categories", "tags"])
        for entry in entries:
            coords = entry.get("coords", [0, 0])
            writer.writerow([
                entry["name"],
                city,
                entry["state"],
                entry.get("address", ""),
                entry.get("pincode", ""),
                coords[0],
                coords[1],
                entry.get("url", ""),
                entry.get("description", ""),
                ", ".join(entry.get("categories", [])),
                ", ".join(entry.get("tags", [])),
            ])

    print(f"generated {len(entries)} content pages + {csv_path} ({skipped} inactive skipped)")


if __name__ == "__main__":
    main()
