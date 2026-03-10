#!/usr/bin/env python3

import json
import re
import time
import urllib.request
import urllib.parse
import yaml

API_KEY_FILE = ".google-key"
ENTRIES_FILE = "../data/entries.yml"
OUTPUT_FILE = "../data/geocode_raw.json"

MULTI_KEYWORDS = ["multiple", "pan-india", "across india"]


def is_multi_location(entry):
    addr = entry.get("address", "").lower()
    city = entry.get("city", "").lower()
    return any(k in addr or k in city for k in MULTI_KEYWORDS)


def build_query(entry):
    name = entry.get("name", "")
    city = entry.get("city", "")
    address = entry.get("address", "")

    if is_multi_location(entry):
        # For multilocation entries, geocode the primary city.
        # Extract a real city name if city is "Various"
        if city.lower() == "various":
            # Try to extract a city from the address
            return address + ", India"
        return city + ", India"

    # Strip existing pincode from address for cleaner query
    addr_clean = re.sub(r'\b\d{6}\b', '', address).strip().rstrip(',').strip()

    if addr_clean:
        return addr_clean + ", " + city + ", India"
    else:
        return city + ", India"


def geocode(query, api_key):
    url = (
        "https://maps.googleapis.com/maps/api/geocode/json?"
        + urllib.parse.urlencode({"address": query, "key": api_key})
    )
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read().decode())


def main():
    with open(API_KEY_FILE) as f:
        api_key = f.read().strip()

    with open(ENTRIES_FILE) as f:
        entries = yaml.safe_load(f)

    print(f"Loaded {len(entries)} entries")

    results = []
    for i, entry in enumerate(entries):
        query = build_query(entry)
        print(f"[{i+1:3d}/{len(entries)}] {entry['name'][:40]:40s} → {query[:60]}")

        try:
            resp = geocode(query, api_key)
            status = resp.get("status", "UNKNOWN")
            if status != "OK":
                print(f"not ok={status}")
        except Exception as e:
            print(f"Error: {e}")
            resp = {"status": "ERROR", "error": str(e)}

        results.append({
            "index": i,
            "name": entry["name"],
            "query": query,
            "response": resp,
        })

        time.sleep(0.1)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    ok = sum(1 for r in results if r["response"].get("status") == "OK")
    print(f"\nDone. {ok}/{len(results)}. Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
