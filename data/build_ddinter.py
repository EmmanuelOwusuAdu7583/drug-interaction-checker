"""Builds data/ddinter_interactions.csv.gz from the DDInter download files.

DDInter (https://ddinter.scbdd.com) publishes its interaction list as CSV files,
one per ATC category: ddinter_downloads_code_{A,B,D,H,L,P,R,V}.csv, each with the
columns DDInterID_A, Drug_A, DDInterID_B, Drug_B, Level.

Usage: download those files into a folder, then run
    python data/build_ddinter.py <folder-with-the-csv-files>

The output keeps one row per drug pair (drug_a, drug_b, level). Pairs DDInter
rates as "Unknown" are left out because the app only shows Major/Moderate/Minor.
"""
import csv
import glob
import gzip
import os
import sys

# DDInter names for drugs the app already lists under another name.
ALIASES = {
    "acetylsalicylic acid": "Aspirin",
    "acetaminophen": "Paracetamol",
    "ethanol": "Alcohol",
    "lithium carbonate": "Lithium",
}
LEVELS = {"Major", "Moderate", "Minor"}
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ddinter_interactions.csv.gz")


def canonical(name):
    name = " ".join(name.split())
    return ALIASES.get(name.lower(), name)


def main(folder):
    files = sorted(glob.glob(os.path.join(folder, "ddinter_downloads_code_*.csv")) or
                   glob.glob(os.path.join(folder, "ddinter_*.csv")))
    if not files:
        sys.exit(f"No DDInter CSV files found in {folder}")

    pairs = {}
    skipped_unknown = 0
    for path in files:
        with open(path, encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                level = row["Level"].strip()
                if level not in LEVELS:
                    skipped_unknown += 1
                    continue
                drug_a, drug_b = canonical(row["Drug_A"]), canonical(row["Drug_B"])
                if drug_a.lower() == drug_b.lower():
                    continue
                key = tuple(sorted((drug_a.lower(), drug_b.lower())))
                pairs.setdefault(key, (drug_a, drug_b, level))

    rows = sorted(pairs.values(), key=lambda r: (r[0].lower(), r[1].lower()))
    with gzip.open(OUTPUT, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["drug_a", "drug_b", "level"])
        writer.writerows(rows)

    drugs = {name.lower() for row in rows for name in row[:2]}
    print(f"{len(files)} files -> {len(rows)} interactions across {len(drugs)} drugs "
          f"({skipped_unknown} rows with an unrated level left out)")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
