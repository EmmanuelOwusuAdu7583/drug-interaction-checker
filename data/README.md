# DDInter data

`ddinter_interactions.csv.gz` holds drug pairs and their severity (Major, Moderate, Minor) taken from
[DDInter](https://ddinter.scbdd.com), a drug-drug interaction database:

> Xiong G, et al. DDInter: an online drug-drug interaction database towards improving clinical
> decision-making and patient safety. Nucleic Acids Research, 2022.

DDInter is free for non-commercial use (CC BY-NC-SA 4.0). This project uses it for a non-commercial
student project; do not reuse this file commercially.

The download gives severity only, with no mechanism or management text. Pairs DDInter rates as "Unknown"
are left out. The app loads this file into Postgres once, on first start (`import_ddinter_data` in `app.py`).

To rebuild it, download the `ddinter_downloads_code_*.csv` files from the DDInter download page into a
folder and run `python data/build_ddinter.py <folder>`.

# Brand names

`brand_names.csv.gz` maps US brand names to the drugs in this app (for example Lipitor to Atorvastatin). It is
built from the FDA National Drug Code directory, published by [openFDA](https://open.fda.gov/data/downloads/)
and in the public domain. openFDA asks that its data not be relied on for medical decisions; here it is used
only to recognise a brand name, and the page always shows which drug a brand was matched to.

Only brands whose products are (nearly all) one single drug are included, so combination products and brands
sold only outside the US are not covered. The app loads this file into Postgres once, on first start
(`import_brand_names` in `app.py`).

To rebuild it, download and unzip the "Drug > NDC" file from the openFDA downloads page and run
`python data/build_brand_names.py <path-to-drug-ndc-0001-of-0001.json>`.
