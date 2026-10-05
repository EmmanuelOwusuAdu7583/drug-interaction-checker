# ============================================
# DRUG INTERACTION CHECKER
# PostgreSQL version for persistent storage on Railway
# By Emmanuel Owusu Adu
# ============================================

from flask import Flask, render_template, jsonify, request, session, redirect, url_for
import psycopg2
import psycopg2.extras
from psycopg2.extras import execute_values
from collections import defaultdict, deque
from datetime import datetime
import csv
import gzip
import io
import json
import os
import time

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "local-dev-secret-change-this")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "local-dev-password-change-this")

DATABASE_URL = os.environ.get("DATABASE_URL")

# Interaction list imported from DDInter (https://ddinter.scbdd.com), built by
# data/build_ddinter.py. Gives severity only, so these rows are labelled with
# their own source and kept apart from the hand-written "curated" ones.
DDINTER_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "ddinter_interactions.csv.gz")
DDINTER_DRUG_CLASS = "Class not listed"
DDINTER_DESCRIPTION = (
    "Listed in the DDInter database as a {level} interaction. DDInter's public data gives the "
    "severity only; check a pharmacist or current prescribing reference for the mechanism and management."
)


# US brand names (Lipitor -> Atorvastatin) from the FDA's NDC directory, built by
# data/build_brand_names.py.
BRAND_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "brand_names.csv.gz")

# Reading drug names from a photo of the packaging uses Claude and needs
# ANTHROPIC_API_KEY. Photos are read in memory and never stored.
PHOTO_MODEL = "claude-opus-5-5"
PHOTO_MEDIA_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
PHOTO_MAX_BYTES = 5 * 1024 * 1024
PHOTO_LIMIT_COUNT = 8        # photos per visitor...
PHOTO_LIMIT_SECONDS = 600    # ...in this many seconds
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024


def photo_reading_enabled():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn


def create_database():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS drugs (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            generic_name TEXT,
            drug_class TEXT NOT NULL,
            description TEXT,
            common_uses TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS interactions (
            id SERIAL PRIMARY KEY,
            drug1_id INTEGER NOT NULL REFERENCES drugs (id),
            drug2_id INTEGER NOT NULL REFERENCES drugs (id),
            severity TEXT NOT NULL,
            description TEXT NOT NULL,
            clinical_effects TEXT,
            management TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS submitters (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            profession TEXT,
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS submitted_interactions (
            id SERIAL PRIMARY KEY,
            submitter_id INTEGER NOT NULL REFERENCES submitters (id),
            drug1_name TEXT NOT NULL,
            drug2_name TEXT NOT NULL,
            severity TEXT NOT NULL,
            description TEXT NOT NULL,
            clinical_effects TEXT,
            management TEXT,
            submitted_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS brand_names (
            id SERIAL PRIMARY KEY,
            brand TEXT NOT NULL UNIQUE,
            drug_id INTEGER NOT NULL REFERENCES drugs (id)
        )
    """)

    cursor.execute("ALTER TABLE interactions ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'curated'")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_interactions_pair ON interactions (drug1_id, drug2_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_interactions_pair_reverse ON interactions (drug2_id, drug1_id)")

    conn.commit()
    cursor.close()
    seed_drug_data(conn)
    import_ddinter_data(conn)
    import_brand_names(conn)
    conn.close()


def seed_drug_data(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM drugs")
    drugs_already_seeded = cursor.fetchone()["count"] > 0

    drugs = [
        ("Warfarin", "Warfarin Sodium", "Anticoagulant", "Blood thinner used to prevent blood clots", "DVT, Pulmonary embolism, Atrial fibrillation"),
        ("Aspirin", "Acetylsalicylic Acid", "NSAID / Antiplatelet", "Pain reliever and blood thinner", "Pain, Fever, Heart attack prevention"),
        ("Ibuprofen", "Ibuprofen", "NSAID", "Non-steroidal anti-inflammatory drug", "Pain, Fever, Inflammation"),
        ("Metformin", "Metformin HCL", "Antidiabetic", "First-line medication for type 2 diabetes", "Type 2 Diabetes"),
        ("Lisinopril", "Lisinopril", "ACE Inhibitor", "Used to treat high blood pressure and heart failure", "Hypertension, Heart failure, Kidney protection"),
        ("Atorvastatin", "Atorvastatin Calcium", "Statin", "Cholesterol-lowering medication", "High cholesterol, Cardiovascular disease prevention"),
        ("Amoxicillin", "Amoxicillin", "Antibiotic (Penicillin)", "Broad spectrum antibiotic", "Bacterial infections, Pneumonia, UTI"),
        ("Ciprofloxacin", "Ciprofloxacin HCL", "Antibiotic (Fluoroquinolone)", "Broad spectrum antibiotic", "UTI, Respiratory infections, Typhoid"),
        ("Metronidazole", "Metronidazole", "Antibiotic / Antiparasitic", "Used for bacterial and parasitic infections", "Bacterial vaginosis, Amebiasis, H. pylori"),
        ("Diazepam", "Diazepam", "Benzodiazepine", "Anti-anxiety and sedative medication", "Anxiety, Seizures, Muscle spasms"),
        ("Omeprazole", "Omeprazole", "Proton Pump Inhibitor", "Reduces stomach acid production", "GERD, Peptic ulcer, Gastritis"),
        ("Paracetamol", "Acetaminophen", "Analgesic / Antipyretic", "Pain reliever and fever reducer", "Pain, Fever, Headache"),
        ("Amlodipine", "Amlodipine Besylate", "Calcium Channel Blocker", "Used to treat high blood pressure and chest pain", "Hypertension, Angina"),
        ("Furosemide", "Furosemide", "Loop Diuretic", "Water pill used to reduce fluid retention", "Heart failure, Edema, Hypertension"),
        ("Digoxin", "Digoxin", "Cardiac Glycoside", "Used to treat heart failure and irregular heartbeat", "Heart failure, Atrial fibrillation"),
        ("Phenytoin", "Phenytoin Sodium", "Anticonvulsant", "Used to control seizures", "Epilepsy, Seizure disorders"),
        ("Fluconazole", "Fluconazole", "Antifungal", "Used to treat fungal infections", "Candidiasis, Cryptococcal meningitis"),
        ("Rifampicin", "Rifampicin", "Antibiotic (Rifamycin)", "Used to treat tuberculosis and other infections", "Tuberculosis, Leprosy, Meningitis prophylaxis"),
        ("Alcohol", "Ethanol", "Substance", "Alcoholic beverages - interacts with many medications", "N/A - Substance"),
        ("Potassium Chloride", "Potassium Chloride", "Electrolyte Supplement", "Used to treat low potassium levels", "Hypokalemia, Potassium deficiency"),
        ("Codeine", "Codeine Phosphate", "Opioid Analgesic", "Used for pain relief and cough suppression", "Moderate pain, Cough"),
        ("Lithium", "Lithium Carbonate", "Mood Stabilizer", "Used to treat bipolar disorder", "Bipolar disorder, Mania"),
        ("Chloroquine", "Chloroquine Phosphate", "Antimalarial", "Used to prevent and treat malaria", "Malaria, Rheumatoid arthritis"),
        ("Artemether", "Artemether", "Antimalarial", "Used to treat malaria", "Malaria treatment"),
        ("Insulin", "Insulin", "Antidiabetic Hormone", "Used to control blood sugar in diabetes", "Type 1 Diabetes, Type 2 Diabetes"),
    ]

    if not drugs_already_seeded:
        execute_values(cursor, """
            INSERT INTO drugs (name, generic_name, drug_class, description, common_uses)
            VALUES %s
            ON CONFLICT (name) DO NOTHING
        """, drugs)
        conn.commit()

    # Check interactions independently of drugs — if a previous deploy seeded
    # drugs but was interrupted (crash/restart) before interactions were
    # inserted, this makes sure interactions still get backfilled instead of
    # being skipped forever.
    cursor.execute("SELECT COUNT(*) as count FROM interactions")
    if cursor.fetchone()["count"] > 0:
        cursor.close()
        return

    cursor.execute("SELECT id, name FROM drugs")
    drug_map = {row["name"]: row["id"] for row in cursor.fetchall()}

    interactions = [
        (drug_map["Warfarin"], drug_map["Aspirin"], "Major",
         "Concurrent use significantly increases bleeding risk",
         "Increased risk of serious bleeding including gastrointestinal and intracranial hemorrhage",
         "Avoid combination if possible. If necessary, monitor INR closely and watch for signs of bleeding"),

        (drug_map["Warfarin"], drug_map["Ibuprofen"], "Major",
         "NSAIDs increase anticoagulant effect of warfarin and cause GI irritation",
         "Increased bleeding risk, GI ulceration and hemorrhage",
         "Avoid combination. Use paracetamol for pain relief instead"),

        (drug_map["Warfarin"], drug_map["Fluconazole"], "Major",
         "Fluconazole inhibits metabolism of warfarin leading to increased anticoagulant effect",
         "Significantly elevated INR, increased bleeding risk",
         "Reduce warfarin dose by 25-50% and monitor INR closely"),

        (drug_map["Warfarin"], drug_map["Rifampicin"], "Major",
         "Rifampicin is a potent inducer of CYP enzymes that metabolize warfarin",
         "Markedly reduced anticoagulant effect, risk of thrombosis",
         "Increase warfarin dose significantly and monitor INR frequently"),

        (drug_map["Warfarin"], drug_map["Metronidazole"], "Major",
         "Metronidazole inhibits warfarin metabolism",
         "Increased INR and bleeding risk",
         "Reduce warfarin dose and monitor INR closely during and after metronidazole course"),

        (drug_map["Metformin"], drug_map["Alcohol"], "Moderate",
         "Alcohol increases risk of lactic acidosis with metformin",
         "Lactic acidosis, hypoglycemia",
         "Advise patients to limit alcohol consumption while taking metformin"),

        (drug_map["Lisinopril"], drug_map["Potassium Chloride"], "Major",
         "ACE inhibitors reduce potassium excretion, risk of hyperkalemia",
         "Potentially fatal hyperkalemia causing cardiac arrhythmias",
         "Monitor potassium levels closely. Avoid potassium supplements unless hypokalemia confirmed"),

        (drug_map["Lisinopril"], drug_map["Ibuprofen"], "Moderate",
         "NSAIDs can reduce antihypertensive effect and impair kidney function",
         "Reduced blood pressure control, acute kidney injury",
         "Monitor blood pressure and kidney function. Consider alternative pain relief"),

        (drug_map["Atorvastatin"], drug_map["Fluconazole"], "Moderate",
         "Fluconazole inhibits statin metabolism leading to increased statin levels",
         "Increased risk of myopathy and rhabdomyolysis",
         "Consider dose reduction of statin or temporary discontinuation during antifungal course"),

        (drug_map["Digoxin"], drug_map["Furosemide"], "Moderate",
         "Furosemide causes potassium loss which increases digoxin toxicity risk",
         "Hypokalemia leading to digoxin toxicity including arrhythmias",
         "Monitor potassium levels and supplement if necessary. Monitor for digoxin toxicity"),

        (drug_map["Digoxin"], drug_map["Amlodipine"], "Moderate",
         "Amlodipine may increase digoxin blood levels",
         "Digoxin toxicity including nausea, visual disturbances, arrhythmias",
         "Monitor digoxin levels and reduce dose if necessary"),

        (drug_map["Diazepam"], drug_map["Alcohol"], "Major",
         "Additive CNS depression between benzodiazepines and alcohol",
         "Severe sedation, respiratory depression, coma, death",
         "Strictly avoid alcohol while taking benzodiazepines"),

        (drug_map["Diazepam"], drug_map["Codeine"], "Major",
         "Additive CNS and respiratory depression",
         "Severe respiratory depression, sedation, risk of death",
         "Avoid combination. If necessary, use lowest effective doses with close monitoring"),

        (drug_map["Phenytoin"], drug_map["Fluconazole"], "Major",
         "Fluconazole inhibits phenytoin metabolism",
         "Phenytoin toxicity including nystagmus, ataxia, confusion",
         "Monitor phenytoin levels closely and reduce dose if necessary"),

        (drug_map["Phenytoin"], drug_map["Rifampicin"], "Major",
         "Rifampicin induces metabolism of phenytoin",
         "Reduced seizure control",
         "Monitor phenytoin levels and increase dose as needed"),

        (drug_map["Phenytoin"], drug_map["Warfarin"], "Major",
         "Complex interaction - phenytoin initially increases then decreases warfarin effect",
         "Unpredictable changes in anticoagulation",
         "Monitor INR very closely during initiation and discontinuation of phenytoin"),

        (drug_map["Ciprofloxacin"], drug_map["Warfarin"], "Major",
         "Ciprofloxacin inhibits warfarin metabolism and affects gut flora",
         "Significantly increased INR and bleeding risk",
         "Monitor INR closely during and after ciprofloxacin course"),

        (drug_map["Ciprofloxacin"], drug_map["Omeprazole"], "Minor",
         "Omeprazole may slightly reduce absorption of ciprofloxacin",
         "Slightly reduced antibiotic effectiveness",
         "Take ciprofloxacin 2 hours before or 6 hours after omeprazole"),

        (drug_map["Metronidazole"], drug_map["Alcohol"], "Major",
         "Metronidazole inhibits alcohol metabolism causing disulfiram-like reaction",
         "Severe nausea, vomiting, flushing, headache, palpitations",
         "Strictly avoid alcohol during and for 48 hours after metronidazole treatment"),

        (drug_map["Rifampicin"], drug_map["Chloroquine"], "Major",
         "Rifampicin significantly reduces chloroquine levels",
         "Treatment failure for malaria",
         "Avoid combination. Use alternative antimalarial therapy"),

        (drug_map["Chloroquine"], drug_map["Artemether"], "Moderate",
         "Potential additive QT prolongation risk",
         "Cardiac arrhythmias, QT prolongation",
         "Monitor ECG if combination cannot be avoided"),

        (drug_map["Insulin"], drug_map["Alcohol"], "Moderate",
         "Alcohol can mask hypoglycemia symptoms and affect blood sugar control",
         "Unpredictable hypoglycemia, delayed hypoglycemia",
         "Advise patients to monitor blood glucose carefully and eat when drinking alcohol"),

        (drug_map["Insulin"], drug_map["Ciprofloxacin"], "Moderate",
         "Fluoroquinolones can affect blood glucose levels",
         "Hypoglycemia or hyperglycemia",
         "Monitor blood glucose closely during antibiotic course"),

        (drug_map["Lithium"], drug_map["Ibuprofen"], "Major",
         "NSAIDs reduce lithium excretion leading to toxicity",
         "Lithium toxicity including tremor, confusion, seizures, cardiac effects",
         "Avoid NSAIDs in patients on lithium. Use paracetamol instead"),

        (drug_map["Lithium"], drug_map["Furosemide"], "Major",
         "Diuretics reduce lithium excretion causing toxicity",
         "Lithium toxicity",
         "Monitor lithium levels closely and adjust dose. Ensure adequate hydration"),

        (drug_map["Amoxicillin"], drug_map["Warfarin"], "Moderate",
         "Antibiotics can affect gut flora reducing vitamin K production",
         "Increased INR and bleeding risk",
         "Monitor INR during and after antibiotic course"),

        (drug_map["Paracetamol"], drug_map["Alcohol"], "Moderate",
         "Chronic alcohol use increases hepatotoxicity risk of paracetamol",
         "Liver damage, hepatotoxicity",
         "Limit paracetamol dose in regular alcohol users. Avoid in heavy drinkers"),

        (drug_map["Omeprazole"], drug_map["Metformin"], "Minor",
         "Omeprazole may slightly increase metformin levels",
         "Slightly increased metformin effect",
         "No specific action required but monitor blood glucose"),

        (drug_map["Amlodipine"], drug_map["Rifampicin"], "Major",
         "Rifampicin dramatically reduces amlodipine blood levels",
         "Loss of blood pressure control",
         "Avoid combination. Use alternative antihypertensive"),

        (drug_map["Codeine"], drug_map["Alcohol"], "Major",
         "Additive CNS and respiratory depression",
         "Severe respiratory depression, sedation, overdose risk",
         "Strictly avoid alcohol while taking opioid medications"),
    ]

    execute_values(cursor, """
        INSERT INTO interactions (drug1_id, drug2_id, severity, description, clinical_effects, management)
        VALUES %s
    """, interactions)

    conn.commit()
    cursor.close()


def import_ddinter_data(conn):
    """Loads the DDInter drug list and interactions once. Runs in a single
    transaction, so an interrupted import leaves nothing behind and is retried
    on the next start. Hand-written (curated) interactions always win: a DDInter
    pair is skipped when that pair already has an entry."""
    if not os.path.exists(DDINTER_DATA_PATH):
        return

    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM interactions WHERE source = 'ddinter' LIMIT 1")
    if cursor.fetchone():
        cursor.close()
        return

    with gzip.open(DDINTER_DATA_PATH, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader)
        rows = [tuple(row) for row in reader if len(row) == 3]

    cursor.execute("CREATE TEMP TABLE ddinter_stage (drug_a TEXT, drug_b TEXT, level TEXT) ON COMMIT DROP")
    execute_values(cursor, "INSERT INTO ddinter_stage (drug_a, drug_b, level) VALUES %s", rows, page_size=5000)

    cursor.execute("""
        INSERT INTO drugs (name, drug_class)
        SELECT staged.name, %s
        FROM (SELECT drug_a AS name FROM ddinter_stage UNION SELECT drug_b FROM ddinter_stage) staged
        WHERE NOT EXISTS (SELECT 1 FROM drugs d WHERE LOWER(d.name) = LOWER(staged.name))
        ON CONFLICT (name) DO NOTHING
    """, (DDINTER_DRUG_CLASS,))

    cursor.execute("""
        INSERT INTO interactions (drug1_id, drug2_id, severity, description, source)
        SELECT d1.id, d2.id, s.level, REPLACE(%s, '{level}', s.level), 'ddinter'
        FROM ddinter_stage s
        JOIN (SELECT LOWER(name) AS key, MIN(id) AS id FROM drugs GROUP BY LOWER(name)) d1 ON d1.key = LOWER(s.drug_a)
        JOIN (SELECT LOWER(name) AS key, MIN(id) AS id FROM drugs GROUP BY LOWER(name)) d2 ON d2.key = LOWER(s.drug_b)
        WHERE NOT EXISTS (
            SELECT 1 FROM interactions i
            WHERE (i.drug1_id = d1.id AND i.drug2_id = d2.id)
               OR (i.drug1_id = d2.id AND i.drug2_id = d1.id)
        )
    """, (DDINTER_DESCRIPTION,))

    conn.commit()
    cursor.close()


def import_brand_names(conn):
    """Loads the brand name list once, after the drugs it points to exist."""
    if not os.path.exists(BRAND_DATA_PATH):
        return

    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM brand_names LIMIT 1")
    if cursor.fetchone():
        cursor.close()
        return

    with gzip.open(BRAND_DATA_PATH, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader)
        rows = [tuple(row) for row in reader if len(row) == 2]

    cursor.execute("CREATE TEMP TABLE brand_stage (brand TEXT, drug TEXT) ON COMMIT DROP")
    execute_values(cursor, "INSERT INTO brand_stage (brand, drug) VALUES %s", rows, page_size=1000)
    cursor.execute("""
        INSERT INTO brand_names (brand, drug_id)
        SELECT s.brand, d.id
        FROM brand_stage s
        JOIN (SELECT LOWER(name) AS key, MIN(id) AS id FROM drugs GROUP BY LOWER(name)) d ON d.key = LOWER(s.drug)
        ON CONFLICT (brand) DO NOTHING
    """)

    conn.commit()
    cursor.close()


@app.route("/")
def index():
    return render_template("dashboard.html", photo_enabled=photo_reading_enabled())


@app.route("/api/drugs")
def get_all_drugs():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM drugs ORDER BY name")
    drugs = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return jsonify(drugs)


@app.route("/api/search-drugs")
def search_drugs():
    """Matches drug names, generic names, classes and brand names. A brand match
    returns its drug with "matched_brand" set, so the page can show which brand
    led to it. Names that start with the typed text come first."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])
    contains, starts = f"%{query}%", f"{query}%"

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT *, (name ILIKE %s) AS starts_with FROM drugs
        WHERE name ILIKE %s OR generic_name ILIKE %s OR drug_class ILIKE %s
        ORDER BY (name ILIKE %s) DESC, name
        LIMIT 10
    """, (starts, contains, contains, contains, starts))
    drug_rows = [dict(row) for row in cursor.fetchall()]

    cursor.execute("""
        SELECT d.*, b.brand AS matched_brand, (b.brand ILIKE %s) AS starts_with
        FROM brand_names b
        JOIN drugs d ON d.id = b.drug_id
        WHERE b.brand ILIKE %s
        ORDER BY (b.brand ILIKE %s) DESC, b.brand
        LIMIT 10
    """, (starts, contains, starts))
    brand_rows = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    conn.close()

    ordered = (
        [row for row in drug_rows if row["starts_with"]]
        + [row for row in brand_rows if row["starts_with"]]
        + [row for row in drug_rows if not row["starts_with"]]
        + [row for row in brand_rows if not row["starts_with"]]
    )
    results = []
    seen_ids = set()
    for row in ordered:
        if row["id"] in seen_ids:
            continue
        seen_ids.add(row["id"])
        row.pop("starts_with")
        results.append(row)
        if len(results) == 10:
            break
    return jsonify(results)


@app.route("/api/check-interaction")
def check_interaction():
    drug1_name = request.args.get("drug1", "")
    drug2_name = request.args.get("drug2", "")

    if not drug1_name or not drug2_name:
        return jsonify({"error": "Please provide both drug names"})

    conn = get_db()
    cursor = conn.cursor()

    # Exact name first — with a large drug list a partial match is rarely unique.
    drug_lookup = """
        SELECT * FROM drugs WHERE name ILIKE %s
        ORDER BY (LOWER(name) = LOWER(%s)) DESC, LENGTH(name), name
        LIMIT 1
    """
    cursor.execute(drug_lookup, (f"%{drug1_name}%", drug1_name))
    drug1 = cursor.fetchone() or _find_drug_by_brand(cursor, drug1_name)

    cursor.execute(drug_lookup, (f"%{drug2_name}%", drug2_name))
    drug2 = cursor.fetchone() or _find_drug_by_brand(cursor, drug2_name)

    if drug1 and drug2:
        cursor.execute("""
            SELECT i.*, d1.name as drug1_name, d2.name as drug2_name
            FROM interactions i
            JOIN drugs d1 ON i.drug1_id = d1.id
            JOIN drugs d2 ON i.drug2_id = d2.id
            WHERE (i.drug1_id = %s AND i.drug2_id = %s)
               OR (i.drug1_id = %s AND i.drug2_id = %s)
            ORDER BY (i.source = 'curated') DESC
            LIMIT 1
        """, (drug1["id"], drug2["id"], drug2["id"], drug1["id"]))
        builtin_interaction = cursor.fetchone()

        # A DDInter entry has a severity but no detail, so a community submission
        # for the same pair (checked below) is shown in its place when one exists.
        if builtin_interaction and builtin_interaction["source"] != "ddinter":
            cursor.close()
            conn.close()
            return jsonify({
                "found": True,
                "source": "verified",
                "drug1": dict(drug1),
                "drug2": dict(drug2),
                "interaction": dict(builtin_interaction)
            })
        ddinter_interaction = builtin_interaction
    else:
        ddinter_interaction = None

    cursor.execute("""
        SELECT si.*, sub.name as submitter_name, sub.profession
        FROM submitted_interactions si
        JOIN submitters sub ON si.submitter_id = sub.id
        WHERE (si.drug1_name ILIKE %s AND si.drug2_name ILIKE %s)
           OR (si.drug1_name ILIKE %s AND si.drug2_name ILIKE %s)
        ORDER BY si.submitted_at DESC
        LIMIT 1
    """, (f"%{drug1_name}%", f"%{drug2_name}%", f"%{drug2_name}%", f"%{drug1_name}%"))
    community_interaction = cursor.fetchone()

    cursor.close()
    conn.close()

    if community_interaction:
        return jsonify({
            "found": True,
            "source": "community",
            "drug1": {"name": drug1_name, "generic_name": "", "description": "", "drug_class": ""} if not drug1 else dict(drug1),
            "drug2": {"name": drug2_name, "generic_name": "", "description": "", "drug_class": ""} if not drug2 else dict(drug2),
            "interaction": dict(community_interaction),
            "submitted_by": community_interaction["submitter_name"],
            "submitter_profession": community_interaction["profession"],
            "ddinter_severity": ddinter_interaction["severity"] if ddinter_interaction else None
        })

    if ddinter_interaction:
        return jsonify({
            "found": True,
            "source": "ddinter",
            "drug1": dict(drug1),
            "drug2": dict(drug2),
            "interaction": dict(ddinter_interaction)
        })

    if drug1 and drug2:
        return jsonify({
            "found": False,
            "drug1": dict(drug1),
            "drug2": dict(drug2),
            "message": "No known interaction found between these drugs in our database or community submissions. Always consult a pharmacist or physician for complete drug interaction checking."
        })

    return jsonify({
        "error": f"Drug not found: {drug1_name if not drug1 else drug2_name}. You can submit this interaction manually if you have clinical knowledge of it."
    })


SEVERITY_ORDER = {"Major": 1, "Moderate": 2, "Minor": 3}


def _find_drug_by_brand(cursor, name):
    cursor.execute("""
        SELECT d.* FROM brand_names b
        JOIN drugs d ON d.id = b.drug_id
        WHERE LOWER(b.brand) = LOWER(%s)
        LIMIT 1
    """, (name.strip(),))
    return cursor.fetchone()


def _find_drug_exact(cursor, name):
    """Exact match on the drug's name or generic name, then on a brand name."""
    cursor.execute("""
        SELECT * FROM drugs
        WHERE LOWER(name) = LOWER(%s) OR LOWER(generic_name) = LOWER(%s)
        ORDER BY (LOWER(name) = LOWER(%s)) DESC
        LIMIT 1
    """, (name, name, name))
    return cursor.fetchone() or _find_drug_by_brand(cursor, name)


def _resolve_drug(cursor, name):
    """Match a typed drug name to a drug in the database.
    Exact match on name, generic name or brand name first; otherwise accept a
    partial match only when it is unambiguous (exactly one drug)."""
    row = _find_drug_exact(cursor, name)
    if row:
        return row

    cursor.execute("SELECT * FROM drugs WHERE name ILIKE %s LIMIT 2", (f"%{name}%",))
    rows = cursor.fetchall()
    if len(rows) == 1:
        return rows[0]
    return None


def _resolve_printed_name(cursor, text):
    """Match a name as printed on packaging, which often carries a salt or form
    after the drug name ("warfarin sodium"). Exact matches only, dropping up to
    two trailing words — a name read from a photo must never be guessed at."""
    words = " ".join(str(text).split()).split(" ")
    for keep in range(len(words), max(len(words) - 3, 0), -1):
        candidate = " ".join(words[:keep])
        if len(candidate) < 3:
            break
        row = _find_drug_exact(cursor, candidate)
        if row:
            return row
    return None


@app.route("/api/check-medication-list", methods=["POST"])
def check_medication_list():
    """Automatically flag every known interaction within a list of medications."""
    data = request.get_json(silent=True) or {}
    raw_names = data.get("drugs", [])

    names = []
    seen = set()
    if isinstance(raw_names, list):
        for item in raw_names:
            if isinstance(item, str) and item.strip():
                key = item.strip().lower()
                if key not in seen:
                    seen.add(key)
                    names.append(item.strip())

    if len(names) < 2:
        return jsonify({"error": "Add at least two different medications to check."}), 400
    if len(names) > 20:
        return jsonify({"error": "Please check 20 medications or fewer at a time."}), 400

    conn = get_db()
    cursor = conn.cursor()

    resolved = {}
    unrecognized = []
    for name in names:
        drug = _resolve_drug(cursor, name)
        if drug:
            resolved[name] = drug
        else:
            unrecognized.append(name)

    # Tell the user when a typed name (a brand, say) was checked as another drug,
    # and when two entries turn out to be the same drug.
    matched = [
        {"entered": name, "drug": drug["name"]}
        for name, drug in resolved.items()
        if name.lower() != drug["name"].lower()
    ]
    by_drug = defaultdict(list)
    for name, drug in resolved.items():
        by_drug[drug["name"]].append(name)
    duplicates = [
        {"drug": drug_name, "entered": entered}
        for drug_name, entered in by_drug.items()
        if len(entered) > 1
    ]

    flags = []
    pairs_checked = 0
    seen_pairs = set()
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            name_a, name_b = names[i], names[j]
            drug_a, drug_b = resolved.get(name_a), resolved.get(name_b)

            # Two entries for the same drug (a brand and its generic) would
            # otherwise repeat every flag; the duplicate is reported separately.
            if drug_a and drug_b:
                if drug_a["id"] == drug_b["id"]:
                    continue
                pair = frozenset((drug_a["id"], drug_b["id"]))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
            pairs_checked += 1

            # A DDInter entry has a severity but no detail, so a community
            # submission for the same pair is shown in its place when one exists.
            ddinter_row = None
            if drug_a and drug_b and drug_a["id"] != drug_b["id"]:
                cursor.execute("""
                    SELECT * FROM interactions
                    WHERE (drug1_id = %s AND drug2_id = %s)
                       OR (drug1_id = %s AND drug2_id = %s)
                    ORDER BY (source = 'curated') DESC
                    LIMIT 1
                """, (drug_a["id"], drug_b["id"], drug_b["id"], drug_a["id"]))
                row = cursor.fetchone()
                if row and row["source"] != "ddinter":
                    flags.append({
                        "drug1": drug_a["name"],
                        "drug2": drug_b["name"],
                        "severity": row["severity"],
                        "description": row["description"],
                        "clinical_effects": row["clinical_effects"],
                        "management": row["management"],
                        "source": "verified",
                    })
                    continue
                ddinter_row = row

            label_a = drug_a["name"] if drug_a else name_a
            label_b = drug_b["name"] if drug_b else name_b
            cursor.execute("""
                SELECT si.*, sub.name AS submitter_name, sub.profession
                FROM submitted_interactions si
                JOIN submitters sub ON si.submitter_id = sub.id
                WHERE (LOWER(TRIM(si.drug1_name)) = LOWER(%s) AND LOWER(TRIM(si.drug2_name)) = LOWER(%s))
                   OR (LOWER(TRIM(si.drug1_name)) = LOWER(%s) AND LOWER(TRIM(si.drug2_name)) = LOWER(%s))
                ORDER BY si.submitted_at DESC
                LIMIT 1
            """, (label_a, label_b, label_b, label_a))
            row = cursor.fetchone()
            if row:
                flags.append({
                    "drug1": label_a,
                    "drug2": label_b,
                    "severity": row["severity"],
                    "description": row["description"],
                    "clinical_effects": row["clinical_effects"],
                    "management": row["management"],
                    "source": "community",
                    "submitted_by": row["submitter_name"],
                    "submitter_profession": row["profession"],
                    "ddinter_severity": ddinter_row["severity"] if ddinter_row else None,
                })
            elif ddinter_row:
                flags.append({
                    "drug1": drug_a["name"],
                    "drug2": drug_b["name"],
                    "severity": ddinter_row["severity"],
                    "description": ddinter_row["description"],
                    "clinical_effects": ddinter_row["clinical_effects"],
                    "management": ddinter_row["management"],
                    "source": "ddinter",
                })

    cursor.close()
    conn.close()

    # A community entry is ranked and counted by the more severe of its own rating and
    # DDInter's, so an under-rated submission cannot push a pair down the list.
    def severity_rank(flag):
        ranks = [SEVERITY_ORDER.get(flag["severity"], 4)]
        if flag.get("ddinter_severity"):
            ranks.append(SEVERITY_ORDER.get(flag["ddinter_severity"], 4))
        return min(ranks)

    source_order = {"verified": 0, "ddinter": 1}
    flags.sort(key=lambda f: (severity_rank(f), source_order.get(f["source"], 2)))

    return jsonify({
        "checked": names,
        "pairs_checked": pairs_checked,
        "flags": flags,
        "unrecognized": unrecognized,
        "matched": matched,
        "duplicates": duplicates,
        "counts": {
            "major": sum(1 for f in flags if severity_rank(f) == 1),
            "moderate": sum(1 for f in flags if severity_rank(f) == 2),
            "minor": sum(1 for f in flags if severity_rank(f) == 3),
        },
    })


PHOTO_INSTRUCTIONS = """You read medicine packaging for a drug interaction checker. Look at the photo \
(a medicine box, blister pack, bottle label or prescription) and list each medicine shown.

For each medicine give:
- brand_name: the brand or product name printed on it, or "" if none is visible.
- active_ingredients: the generic name of each active ingredient, one per entry, without salt form, strength \
or dose form ("warfarin", not "warfarin sodium 5 mg tablets"). Use the name as printed; if it is printed in \
another language, give the English generic name.
- ingredients_printed: true if you read the active ingredients from the packaging; false if they are not \
legible and you are giving them from the brand name alone. Only do that for a brand you are sure of; \
otherwise leave active_ingredients empty.

Report only what the photo shows. Do not guess at text you cannot read, and ignore people's names, \
addresses and other personal details. If the photo shows no medicine, return an empty list."""

PHOTO_SCHEMA = {
    "type": "object",
    "properties": {
        "medicines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "brand_name": {"type": "string"},
                    "active_ingredients": {"type": "array", "items": {"type": "string"}},
                    "ingredients_printed": {"type": "boolean"},
                },
                "required": ["brand_name", "active_ingredients", "ingredients_printed"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["medicines"],
    "additionalProperties": False,
}

_photo_requests = defaultdict(deque)


def _photo_limit_reached(visitor):
    """Each photo costs money to read, so cap how many one visitor can send."""
    now = time.time()
    recent = _photo_requests[visitor]
    while recent and now - recent[0] > PHOTO_LIMIT_SECONDS:
        recent.popleft()
    if len(recent) >= PHOTO_LIMIT_COUNT:
        return True
    recent.append(now)
    return False


def _image_media_type(image_bytes):
    if image_bytes[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if image_bytes[:4] == b"GIF8":
        return "image/gif"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    return None


def read_medicines_from_photo(image_bytes, media_type):
    """Returns the medicines Claude reads from the photo, as a list of
    {"brand_name", "active_ingredients", "ingredients_printed"} dicts."""
    import anthropic
    import base64

    client = anthropic.Anthropic()
    response = client.beta.messages.create(
        model=PHOTO_MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=PHOTO_INSTRUCTIONS,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": PHOTO_SCHEMA}},
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": base64.standard_b64encode(image_bytes).decode("utf-8"),
                }},
                {"type": "text", "text": "List the medicines shown in this photo."},
            ],
        }],
    )
    if response.stop_reason != "end_turn":
        raise ValueError(f"photo read stopped early: {response.stop_reason}")
    text = next(block.text for block in response.content if block.type == "text")
    return json.loads(text)["medicines"]


@app.route("/api/read-drug-photo", methods=["POST"])
def read_drug_photo():
    """Reads drug names from a photo and matches them to the database. Nothing is
    added to a list here — the page shows the result for the user to confirm."""
    if not photo_reading_enabled():
        return jsonify({"error": "Photo reading is not set up on this server."}), 503

    visitor = (request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0]).strip()
    if _photo_limit_reached(visitor):
        return jsonify({"error": "Too many photos in a short time. Please wait a few minutes and try again."}), 429

    photo = request.files.get("photo")
    image_bytes = photo.read() if photo else b""
    if not image_bytes:
        return jsonify({"error": "Choose or take a photo first."}), 400
    if len(image_bytes) > PHOTO_MAX_BYTES:
        return jsonify({"error": "That photo is too large. Please use one under 5 MB."}), 400
    media_type = _image_media_type(image_bytes)
    if media_type not in PHOTO_MEDIA_TYPES:
        return jsonify({"error": "That file is not a photo this app can read. Use a JPG, PNG or WEBP."}), 400

    try:
        medicines = read_medicines_from_photo(image_bytes, media_type)
    except Exception:
        app.logger.exception("Reading a drug photo failed")
        return jsonify({"error": "The photo could not be read just now. Please try again, or type the names instead."}), 502

    conn = get_db()
    cursor = conn.cursor()
    recognized = []
    unrecognized = []
    seen_drugs = set()
    seen_unknown = set()

    def add_unknown(label):
        label = " ".join(str(label).split())[:80]
        if label and label.lower() not in seen_unknown:
            seen_unknown.add(label.lower())
            unrecognized.append(label)

    for medicine in medicines[:20]:
        brand = " ".join(str(medicine.get("brand_name") or "").split())[:80]
        ingredients = [" ".join(str(item).split())[:80] for item in (medicine.get("active_ingredients") or [])[:10]]
        ingredients = [item for item in ingredients if item]
        printed = bool(medicine.get("ingredients_printed"))

        # Ingredients first; the brand name only when no ingredient was given.
        candidates = [(item, printed) for item in ingredients] or ([(brand, True)] if brand else [])
        for label, was_printed in candidates:
            drug = _resolve_printed_name(cursor, label)
            if not drug:
                add_unknown(label)
            elif drug["id"] not in seen_drugs:
                seen_drugs.add(drug["id"])
                recognized.append({
                    "drug": drug["name"],
                    "read": label,
                    "brand": brand,
                    "ingredients_printed": was_printed,
                })

    cursor.close()
    conn.close()
    return jsonify({"recognized": recognized, "unrecognized": unrecognized})


@app.route("/api/drug-interactions/<int:drug_id>")
def get_drug_interactions(drug_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM drugs WHERE id = %s", (drug_id,))
    drug = cursor.fetchone()

    if not drug:
        cursor.close()
        conn.close()
        return jsonify({"error": "Drug not found"})

    cursor.execute("""
        SELECT i.*, d1.name as drug1_name, d2.name as drug2_name
        FROM interactions i
        JOIN drugs d1 ON i.drug1_id = d1.id
        JOIN drugs d2 ON i.drug2_id = d2.id
        WHERE i.drug1_id = %s OR i.drug2_id = %s
        ORDER BY
            (i.source = 'curated') DESC,
            CASE i.severity
                WHEN 'Major' THEN 1
                WHEN 'Moderate' THEN 2
                WHEN 'Minor' THEN 3
            END,
            d1.name, d2.name
    """, (drug_id, drug_id))

    interactions = []
    for row in cursor.fetchall():
        item = dict(row)
        if item["drug1_id"] == drug_id:
            item["interacts_with"] = item["drug2_name"]
        else:
            item["interacts_with"] = item["drug1_name"]
        interactions.append(item)

    cursor.close()
    conn.close()
    return jsonify({
        "drug": dict(drug),
        "interactions": interactions,
        "total": len(interactions)
    })


@app.route("/api/summary")
def get_summary():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as total FROM drugs")
    total_drugs = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as total FROM interactions")
    total_interactions = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as total FROM interactions WHERE severity = 'Major'")
    major = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as total FROM interactions WHERE severity = 'Moderate'")
    moderate = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as total FROM interactions WHERE severity = 'Minor'")
    minor = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as total FROM interactions WHERE source = 'ddinter'")
    from_ddinter = cursor.fetchone()["total"]

    cursor.close()
    conn.close()
    return jsonify({
        "total_drugs": total_drugs,
        "total_interactions": total_interactions,
        "major": major,
        "moderate": moderate,
        "minor": minor,
        "from_ddinter": from_ddinter
    })


@app.route("/submit-interaction")
def submit_interaction_form():
    return render_template("submit_interaction.html")


@app.route("/api/submit-interaction", methods=["POST"])
def submit_interaction():
    data = request.json

    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    profession = data.get("profession", "").strip()
    drug1_name = data.get("drug1_name", "").strip()
    drug2_name = data.get("drug2_name", "").strip()
    severity = data.get("severity", "").strip()
    description = data.get("description", "").strip()
    clinical_effects = data.get("clinical_effects", "").strip()
    management = data.get("management", "").strip()

    if not name or not email:
        return jsonify({"error": "Name and email are required"}), 400

    if not drug1_name or not drug2_name or not severity or not description:
        return jsonify({"error": "Both drug names, severity, and description are required"}), 400

    if severity not in ["Major", "Moderate", "Minor"]:
        return jsonify({"error": "Severity must be Major, Moderate, or Minor"}), 400

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM submitters WHERE email = %s", (email,))
    existing = cursor.fetchone()

    if existing:
        submitter_id = existing["id"]
    else:
        cursor.execute("""
            INSERT INTO submitters (name, email, profession, created_at)
            VALUES (%s, %s, %s, %s) RETURNING id
        """, (name, email, profession, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        submitter_id = cursor.fetchone()["id"]

    cursor.execute("""
        INSERT INTO submitted_interactions
        (submitter_id, drug1_name, drug2_name, severity, description, clinical_effects, management, submitted_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (submitter_id, drug1_name, drug2_name, severity, description, clinical_effects, management,
          datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Thank you. Your submitted interaction has been added and is now visible in the interaction checker."
    })


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))
        error = "Incorrect password. Please try again."
    return render_template("admin_login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))


def admin_required():
    return session.get("is_admin", False)


@app.route("/admin")
def admin_dashboard():
    if not admin_required():
        return redirect(url_for("admin_login"))
    return render_template("admin_dashboard.html")


@app.route("/api/admin/submitted-interactions")
def admin_get_submitted_interactions():
    if not admin_required():
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT si.*, sub.name as submitter_name, sub.email as submitter_email, sub.profession
        FROM submitted_interactions si
        JOIN submitters sub ON si.submitter_id = sub.id
        ORDER BY si.submitted_at DESC
    """)
    data = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return jsonify(data)


@app.route("/api/admin/summary")
def admin_summary():
    if not admin_required():
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as total FROM submitted_interactions")
    total_submitted = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(DISTINCT submitter_id) as total FROM submitted_interactions")
    total_submitters = cursor.fetchone()["total"]

    cursor.execute("""
        SELECT severity, COUNT(*) as count
        FROM submitted_interactions
        GROUP BY severity
    """)
    by_severity = [dict(row) for row in cursor.fetchall()]

    cursor.execute("""
        SELECT profession, COUNT(*) as count
        FROM submitters
        WHERE profession IS NOT NULL AND profession != ''
        GROUP BY profession
        ORDER BY count DESC
    """)
    by_profession = [dict(row) for row in cursor.fetchall()]

    cursor.close()
    conn.close()

    return jsonify({
        "total_submitted": total_submitted,
        "total_submitters": total_submitters,
        "by_severity": by_severity,
        "by_profession": by_profession
    })


@app.route("/api/admin/export-csv")
def export_csv():
    if not admin_required():
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT si.id, si.drug1_name, si.drug2_name, si.severity, si.description,
               si.clinical_effects, si.management, si.submitted_at,
               sub.name as submitter_name, sub.email as submitter_email, sub.profession
        FROM submitted_interactions si
        JOIN submitters sub ON si.submitter_id = sub.id
        ORDER BY si.submitted_at DESC
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Drug 1", "Drug 2", "Severity", "Description", "Clinical Effects",
                      "Management", "Submitted At", "Submitter Name", "Submitter Email", "Profession"])

    for row in rows:
        writer.writerow([row["id"], row["drug1_name"], row["drug2_name"], row["severity"],
                          row["description"], row["clinical_effects"], row["management"],
                          row["submitted_at"], row["submitter_name"], row["submitter_email"], row["profession"]])

    csv_data = output.getvalue()
    output.close()

    return csv_data, 200, {
        "Content-Type": "text/csv",
        "Content-Disposition": "attachment; filename=submitted_drug_interactions.csv"
    }


_db_initialized = False


@app.before_request
def initialize_database_once():
    global _db_initialized
    if not _db_initialized:
        create_database()
        _db_initialized = True


if __name__ == "__main__":
    print("Drug Interaction Checker starting...")
    print("Open your browser and go to: http://127.0.0.1:5000")
    app.run(debug=True)
