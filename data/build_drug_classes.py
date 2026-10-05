"""Builds data/drug_classes.csv.gz: drug name -> pharmacologic class, from the FDA's NDC directory.

The openFDA NDC download (https://open.fda.gov/data/downloads/, "Drug > NDC", public
domain) tags each product with the FDA "Established Pharmacologic Class" (EPC) of its
ingredient, for example "HMG-CoA Reductase Inhibitor [EPC]".

Usage: unzip drug-ndc-0001-of-0001.json.zip, then run
    python data/build_drug_classes.py <path-to-drug-ndc-0001-of-0001.json>

Only single-ingredient products are used, so a class always belongs to one drug. A drug
keeps the classes found on at least half of its products; several classes are joined
with "; " (aspirin is both an NSAID and a platelet aggregation inhibitor).
"""
import collections
import csv
import gzip
import json
import os
import sys

from build_brand_names import ingredient_to_drug, load_app_drugs

OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "drug_classes.csv.gz")
MIN_SHARE = 0.5


def main(ndc_path):
    drugs = load_app_drugs()
    with open(ndc_path, encoding="utf-8") as handle:
        products = json.load(handle)["results"]

    product_count = collections.Counter()
    class_count = collections.defaultdict(collections.Counter)
    for product in products:
        if product.get("product_type") not in ("HUMAN PRESCRIPTION DRUG", "HUMAN OTC DRUG"):
            continue
        ingredients = product.get("active_ingredients") or []
        if len(ingredients) != 1:
            continue
        drug = ingredient_to_drug(ingredients[0]["name"], drugs)
        classes = {
            " ".join(entry[:-len("[EPC]")].split())
            for entry in product.get("pharm_class") or []
            if entry.endswith("[EPC]")
        }
        if not drug or not classes:
            continue
        product_count[drug] += 1
        for name in classes:
            class_count[drug][name] += 1

    rows = []
    for drug in sorted(product_count, key=str.lower):
        kept = sorted(name for name, count in class_count[drug].items() if count / product_count[drug] >= MIN_SHARE)
        if kept:
            rows.append((drug, "; ".join(kept)))

    with gzip.open(OUTPUT, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["drug", "classes"])
        writer.writerows(rows)

    print(f"{len(rows)} of {len(drugs)} drugs have a class ({len({c for _, cs in rows for c in cs.split('; ')})} distinct classes)")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
