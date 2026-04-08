# 



 is an open-source, open-data directory of hacker/maker spaces across India. The project is inspired by and is a fork of [ooru.space]() created by [Kailash Nadh](nadh.in)

## Usage

The site is a [Zola](https://getzola.org) static site.

- Run `python scripts/generate_site.py data/entries.yml ./content/spaces/` to generate Zola content files for all entries.
- Run `zola serve` (to preview) or `zola build` to generate the full static site.


## License
- The data (`data/entries.yml` and its CSV form published on the website) are licensed under CC BY-SA 4 (Creative Commons Attribution-ShareAlike 4.0)
- The repository (excluding data) and all the code in it is licensed under the MIT License
