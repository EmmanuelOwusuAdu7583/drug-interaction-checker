"""Builds data/brand_names.csv.gz: brand name -> drug name, from the FDA's NDC directory.

The openFDA NDC download (https://open.fda.gov/data/downloads/, "Drug > NDC", public
domain) lists every US drug product with its brand name and active ingredient.

Usage: unzip drug-ndc-0001-of-0001.json.zip, then run
    python data/build_brand_names.py <path-to-drug-ndc-0001-of-0001.json>

Only a brand whose products are (nearly all) one single drug already in the app's list
is kept, from prescription and over-the-counter products, with generic-style and
descriptive names ("Pain Relief", "Aspirin 81 mg") left out. These are US brand names;
brands sold only in other countries are not covered.
"""
import collections
import csv
import gzip
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(HERE, "brand_names.csv.gz")

# Drugs the app seeds by hand (see seed_drug_data in app.py).
CURATED_DRUGS = [
    "Warfarin", "Aspirin", "Ibuprofen", "Metformin", "Digoxin", "Furosemide", "Lisinopril", "Amlodipine",
    "Atorvastatin", "Omeprazole", "Fluconazole", "Ciprofloxacin", "Phenytoin", "Diazepam", "Codeine", "Lithium",
    "Rifampicin", "Metronidazole", "Amoxicillin", "Chloroquine", "Artemether", "Paracetamol", "Alcohol",
    "Potassium Chloride", "Insulin",
]

# US ingredient names for drugs the app lists under their international name.
SYNONYMS = {
    "acetaminophen": "paracetamol",
    "acetylsalicylic acid": "aspirin",
    "rifampin": "rifampicin",
    "lithium carbonate": "lithium",
    "albuterol": "salbutamol",
    "levalbuterol": "levosalbutamol",
    "glyburide": "glibenclamide",
    "meperidine": "pethidine",
}

# Salt and hydrate words that follow the drug name in an ingredient ("warfarin sodium").
SALT_WORDS = (
    "sodium|potassium|calcium|magnesium|hydrochloride|dihydrochloride|hydrobromide|sulfate|bisulfate|phosphate|"
    "acetate|maleate|fumarate|tartrate|bitartrate|succinate|citrate|mesylate|besylate|tosylate|nitrate|bromide|"
    "chloride|anhydrous|monohydrate|dihydrate|trihydrate|hemihydrate|disodium|dipotassium|lactate|gluconate|"
    "carbonate|valerate|propionate|dipropionate|furoate|pamoate|decanoate|palmitate|hyclate|axetil|medoxomil|"
    "etexilate|marboxil|proxetil|pivoxil|cilexetil|mofetil|disoproxil|alafenamide|oxalate|malate|stearate|"
    "butyrate|benzoate|napsylate|estolate|ethylsuccinate|tromethamine|meglumine|hcl"
)
SALT_SUFFIX = re.compile(r"\s+(" + SALT_WORDS + r")$")

# Words that mark a descriptive product name rather than a brand.
DESCRIPTIVE = re.compile(
    r"\b(relief|reliever|pain|fever|cold|flu|cough|allergy|sinus|sleep|nighttime|daytime|strength|regular|maximum|"
    r"extra|childrens|children|kids|infants|infant|junior|adult|womens|mens|care|health|aid|aids|antacid|laxative|"
    r"stool|softener|acid|reducer|heartburn|nasal|spray|cream|ointment|gel|lotion|tablet|tablets|capsule|capsules|"
    r"caplet|caplets|liquid|solution|suspension|injection|oral|topical|drops|chewable|dose|hour|day|night|low|"
    r"itch|anti|antibiotic|antifungal|first|medicated|original|formula|plus|basic|premium|quality|choice|value)\b"
)


MIN_SHARE = 0.75
SKIP_DRUGS = {"Alcohol"}  # hand sanitisers, not medicines


def brand_key(brand_name):
    """'TYLENOL Extra Strength' -> 'TYLENOL': drops trailing strength/form words."""
    words = brand_name.split(",")[0].split()
    while len(words) > 1 and DESCRIPTIVE.fullmatch(words[-1].lower().replace("'", "")):
        words.pop()
    return " ".join(words)


def load_app_drugs():
    drugs = {name.lower(): name for name in CURATED_DRUGS}
    with gzip.open(os.path.join(HERE, "ddinter_interactions.csv.gz"), "rt", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader)
        for drug_a, drug_b, _ in reader:
            drugs.setdefault(drug_a.lower(), drug_a)
            drugs.setdefault(drug_b.lower(), drug_b)
    return drugs


def ingredient_to_drug(ingredient, drugs):
    name = " ".join(ingredient.lower().replace(",", " ").split())
    for _ in range(4):
        name = SYNONYMS.get(name, name)
        if name in drugs:
            return drugs[name]
        shorter = SALT_SUFFIX.sub("", name)
        if shorter == name:
            return None
        name = shorter
    return None


def is_real_brand(brand, drug, drugs):
    key = brand.lower()
    if not 3 <= len(brand) <= 40 or len(brand.split()) > 3:
        return False
    if any(ch.isdigit() for ch in brand) or not re.fullmatch(r"[A-Za-z][A-Za-z .'\-]*", brand):
        return False
    if key in drugs or drug.lower() in key or any(name in key for name in SYNONYMS) or DESCRIPTIVE.search(key):
        return False
    return True


def main(ndc_path):
    drugs = load_app_drugs()
    with open(ndc_path, encoding="utf-8") as handle:
        products = json.load(handle)["results"]

    # brand (lowercase) -> how many products under that name contain each drug.
    # None counts combination products and ingredients the app does not list.
    seen = collections.defaultdict(lambda: {"drugs": collections.Counter(), "spelling": collections.Counter()})
    for product in products:
        if product.get("product_type") not in ("HUMAN PRESCRIPTION DRUG", "HUMAN OTC DRUG"):
            continue
        ingredients = product.get("active_ingredients") or []
        brand = brand_key(product.get("brand_name") or "")
        if not brand or not ingredients:  # kits and starter packs list no ingredient
            continue
        entry = seen[brand.lower()]
        drug = ingredient_to_drug(ingredients[0]["name"], drugs) if len(ingredients) == 1 else None
        entry["drugs"][drug] += 1
        entry["spelling"][brand] += 1

    rows = []
    for entry in seen.values():
        drug, count = entry["drugs"].most_common(1)[0]
        # Keep a brand only when nearly all its products are the same single drug
        # ("Tylenol" is paracetamol even though a few Tylenol-branded combinations exist).
        if drug is None or drug in SKIP_DRUGS or count / sum(entry["drugs"].values()) < MIN_SHARE:
            continue
        brand = entry["spelling"].most_common(1)[0][0]
        if brand.isupper() or brand.islower():
            brand = brand.title()
        if is_real_brand(brand, drug, drugs):
            rows.append((brand, drug))

    rows.sort(key=lambda row: row[0].lower())
    with gzip.open(OUTPUT, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["brand", "drug"])
        writer.writerows(rows)

    print(f"{len(products)} products -> {len(rows)} brand names for {len({drug for _, drug in rows})} drugs")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
