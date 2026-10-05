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
