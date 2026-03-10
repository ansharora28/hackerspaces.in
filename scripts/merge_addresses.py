#!/usr/bin/env python3
import json
import re
import yaml

ENTRIES_FILE = "../data/entries.yml"
GEOCODE_FILE = "../data/geocode_raw.json"
OUTPUT_FILE = "../data/entries.yml"

MULTI_KEYWORDS = ["multiple", "pan-india", "across india"]

# Header comment to preserve
HEADER = "# Community/Public spaces directory - India.\n# https://ooru.space\n"


def extract_components(result):
    """Extract structured address components from a geocode API result."""
    if not result.get("response", {}).get("results"):
        return {}

    geo = result["response"]["results"][0]
    comps = {}
    for c in geo.get("address_components", []):
        for t in c["types"]:
            comps[t] = c["long_name"]

    loc = geo.get("geometry", {}).get("location", {})
    comps["lat"] = loc.get("lat")
    comps["lng"] = loc.get("lng")
    return comps


def extract_pincode(entry, comps):
    """Extract pincode: prefer original embedded pincode, fall back to API postal_code."""
    # From original address (user-provided, more specific)
    addr = entry.get("address", "")
    m = re.search(r'\b(\d{6})\b', addr)
    if m:
        return m.group(1)

    # From API
    pin = comps.get("postal_code")
    if pin and re.match(r'^\d{6}$', str(pin)):
        return str(pin)

    return None


def strip_pincode(address):
    """Remove 6-digit pincode from address string."""
    return re.sub(r'\s*\b\d{6}\b', '', address).strip().rstrip(',').strip()


def normalize(s):
    """Normalize string for comparison."""
    return re.sub(r'\s+', ' ', s).strip().lower()


def is_noisy_sublocality(s):
    """Detect noisy API sublocalities (apartment complexes, colonies named after buildings)."""
    noise_patterns = [
        r'(?i)apparte?ments?$', r'(?i)towers?$', r'(?i)heights?$',
        r'(?i)residenc[ey]$', r'(?i)complex$', r'(?i)plaza$',
        r'(?i)society$', r'(?i)enclave$',
    ]
    return any(re.search(p, s.strip()) for p in noise_patterns)


def dedupe_parts(parts):
    """Remove duplicate and near-duplicate address parts (case-insensitive, substring-aware)."""
    result = []
    for p in parts:
        p = p.strip().rstrip(',').strip()
        if not p:
            continue
        pn = normalize(p)
        # Check if this part is already covered by an existing part (substring match)
        already_covered = False
        to_remove = None
        for i, existing in enumerate(result):
            en = normalize(existing)
            if pn == en:
                already_covered = True
                break
            # If existing contains this part as a substring (e.g., "New Delhi" covers "Delhi")
            if len(pn) > 3 and pn in en:
                already_covered = True
                break
            # If this part contains existing as substring, replace existing with this
            if len(en) > 3 and en in pn:
                to_remove = i
                break
        if to_remove is not None:
            result[to_remove] = p
        elif not already_covered:
            result.append(p)
    return result


def build_improved_address(entry, comps):
    """Build improved address by merging original details with API sublocalities.

    Returns the address string with state removed (state goes to its own field).
    """
    original = entry.get("address", "")
    city = entry.get("city", "")

    # Strip pincode from original
    original_clean = strip_pincode(original)

    # Parse original into parts
    orig_parts = [p.strip() for p in original_clean.split(",") if p.strip()]

    # API-provided sublocalities and locality
    api_parts = []
    for key in ["sublocality_level_2", "sublocality_level_1", "locality"]:
        val = comps.get(key)
        if val:
            api_parts.append(val)

    # State from API
    state = comps.get("administrative_area_level_1", "")

    # Collect all known parts from original address (normalized for dedup)
    orig_normalized = {normalize(p) for p in orig_parts}

    # Add API sublocalities that aren't already in the original (skip noisy ones)
    # Also skip if a fuzzy match exists (e.g., "Khirki Extension" vs "Khirkee Extension")
    enrichment = []
    for ap in api_parts:
        apn = normalize(ap)
        if apn == normalize(city):
            continue
        if is_noisy_sublocality(ap):
            continue
        # Check exact match
        if apn in orig_normalized:
            continue
        # Check fuzzy substring containment (either direction)
        fuzzy_match = False
        for op in orig_normalized:
            # If >60% of characters overlap, skip (handles spelling variants)
            if len(apn) > 4 and len(op) > 4:
                common = len(set(apn.split()) & set(op.split()))
                if common > 0:
                    fuzzy_match = True
                    break
            # Substring containment
            if apn in op or op in apn:
                fuzzy_match = True
                break
        if not fuzzy_match:
            enrichment.append(ap)

    # Limit API enrichment: if original already has 3+ parts, add at most 1 sublocality
    if len(orig_parts) >= 3 and len(enrichment) > 1:
        enrichment = enrichment[:1]

    # Build final address parts:
    # Start with original (granular details first), then add missing sublocalities
    all_parts = list(orig_parts)

    # Insert API sublocalities after the most granular parts but before city/state
    # Find where city/state appear in original to insert before them
    insert_pos = len(all_parts)
    for i, p in enumerate(all_parts):
        pn = normalize(p)
        if pn == normalize(city) or pn == normalize(state) or (state and pn == normalize(state)):
            insert_pos = i
            break
        # Also check for district-level matches
        district = comps.get("administrative_area_level_2", "")
        if district and pn == normalize(district):
            insert_pos = i
            break

    for j, ep in enumerate(enrichment):
        all_parts.insert(insert_pos + j, ep)

    # Deduplicate
    final = dedupe_parts(all_parts)

    # Remove "India" and state from address (state goes to its own field)
    final = [p for p in final if normalize(p) != "india"]
    if state:
        final = [p for p in final if normalize(p) != normalize(state)]

    return ", ".join(final)


def yaml_quote(s):
    """Quote a string for YAML output."""
    if s is None:
        return '""'
    # Use double quotes, escape internal double quotes
    s = str(s).replace('\\', '\\\\').replace('"', '\\"')
    return f'"{s}"'


def write_yaml(entries, filepath):
    """Write entries to YAML with exact formatting control."""
    lines = [HEADER]

    for entry in entries:
        lines.append(f'- name: {yaml_quote(entry["name"])}')
        lines.append(f'  city: {yaml_quote(entry["city"])}')
        if entry.get("state"):
            lines.append(f'  state: {yaml_quote(entry["state"])}')
        lines.append(f'  address: {yaml_quote(entry["address"])}')

        if entry.get("pincode"):
            lines.append(f'  pincode: {yaml_quote(entry["pincode"])}')

        if entry.get("coords"):
            lat, lng = entry["coords"]
            lines.append(f'  coords: [{lat}, {lng}]')

        lines.append(f'  url: {yaml_quote(entry["url"])}')
        lines.append(f'  description: {yaml_quote(entry["description"])}')

        lines.append('  categories:')
        for cat in entry.get("categories", []):
            lines.append(f'    - {cat}')

        if "tags" in entry:
            if entry["tags"]:
                lines.append('  tags:')
                for tag in entry["tags"]:
                    lines.append(f'    - {tag}')
            else:
                lines.append('  tags: []')

        lines.append("")  # blank line between entries

    with open(filepath, "w") as f:
        f.write("\n".join(lines))


def main():
    with open(ENTRIES_FILE) as f:
        entries = yaml.safe_load(f)

    with open(GEOCODE_FILE) as f:
        geocode_results = json.load(f)

    print(f"Loaded {len(entries)} entries, {len(geocode_results)} geocode results")

    stats = {"improved": 0, "pin_api": 0, "pin_regex": 0, "no_pin": 0, "no_result": 0}

    for i, entry in enumerate(entries):
        geo = geocode_results[i]
        comps = extract_components(geo)

        if not comps:
            print(f"no geocode result for: {entry['name']}")
            stats["no_result"] += 1
            # Still strip pincode from address if present
            pin_match = re.search(r'\b(\d{6})\b', entry.get("address", ""))
            if pin_match:
                entry["pincode"] = pin_match.group(1)
                entry["address"] = strip_pincode(entry["address"])
            continue

        # Check if it's a multi-location entry
        addr_lower = entry.get("address", "").lower()
        city_lower = entry.get("city", "").lower()
        is_multi = any(k in addr_lower or k in city_lower for k in MULTI_KEYWORDS)

        # Extract pincode (skip for multi-location with "Various" city)
        if is_multi and city_lower == "various":
            stats["no_pin"] += 1
        else:
            pincode = extract_pincode(entry, comps)
            if pincode:
                entry["pincode"] = pincode
                if comps.get("postal_code") and re.match(r'^\d{6}$', str(comps["postal_code"])):
                    stats["pin_api"] += 1
                else:
                    stats["pin_regex"] += 1
            else:
                stats["no_pin"] += 1

        # Extract state from API
        api_state = comps.get("administrative_area_level_1", "")
        if api_state:
            entry["state"] = api_state

        if not is_multi:
            entry["address"] = build_improved_address(entry, comps)
        else:
            # For multi-location entries, still strip state from address if present
            if api_state:
                parts = [p.strip() for p in entry["address"].split(",")]
                parts = [p for p in parts if normalize(p) != normalize(api_state)]
                entry["address"] = ", ".join(parts)

        # Set coords (rounded to 4 decimals)
        if comps.get("lat") is not None and comps.get("lng") is not None:
            entry["coords"] = [round(comps["lat"], 4), round(comps["lng"], 4)]

        stats["improved"] += 1

    print(f"\nStats:")
    print(f"  improved: {stats['improved']}")
    print(f"  PIN from API: {stats['pin_api']}")
    print(f"  PIN from regex: {stats['pin_regex']}")
    print(f"  No PIN found: {stats['no_pin']}")
    print(f"  No geocode result: {stats['no_result']}")

    write_yaml(entries, OUTPUT_FILE)
    print(f"\nWritten to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
