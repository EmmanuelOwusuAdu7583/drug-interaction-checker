# ============================================
# DRUG INTERACTION CHECKER
# Building Real Health Informatics Projects
# By Emmanuel Owusu Adu
# ============================================

from flask import Flask, render_template, jsonify, request
import sqlite3
from datetime import datetime

app = Flask(__name__)

def get_db():
    conn = sqlite3.connect("drugs.db")
    conn.row_factory = sqlite3.Row
    return conn

def create_database():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS drugs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            generic_name TEXT,
            drug_class TEXT NOT NULL,
            description TEXT,
            common_uses TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            drug1_id INTEGER NOT NULL,
            drug2_id INTEGER NOT NULL,
            severity TEXT NOT NULL,
            description TEXT NOT NULL,
            clinical_effects TEXT,
            management TEXT,
            FOREIGN KEY (drug1_id) REFERENCES drugs (id),
            FOREIGN KEY (drug2_id) REFERENCES drugs (id)
        )
    """)

    conn.commit()
    seed_drug_data(cursor, conn)
    conn.close()

def seed_drug_data(cursor, conn):
    cursor.execute("SELECT COUNT(*) FROM drugs")
    if cursor.fetchone()[0] > 0:
        return

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

    cursor.executemany("""
        INSERT OR IGNORE INTO drugs (name, generic_name, drug_class, description, common_uses)
        VALUES (?, ?, ?, ?, ?)
    """, drugs)

    conn.commit()

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

    cursor.executemany("""
        INSERT INTO interactions (drug1_id, drug2_id, severity, description, clinical_effects, management)
        VALUES (?, ?, ?, ?, ?, ?)
    """, interactions)

    conn.commit()


@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/api/drugs")
def get_all_drugs():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM drugs ORDER BY name")
    drugs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(drugs)


@app.route("/api/search-drugs")
def search_drugs():
    query = request.args.get("q", "")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM drugs
        WHERE name LIKE ? OR generic_name LIKE ? OR drug_class LIKE ?
        ORDER BY name
        LIMIT 10
    """, (f"%{query}%", f"%{query}%", f"%{query}%"))
    drugs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(drugs)


@app.route("/api/check-interaction")
def check_interaction():
    drug1_name = request.args.get("drug1", "")
    drug2_name = request.args.get("drug2", "")

    if not drug1_name or not drug2_name:
        return jsonify({"error": "Please provide both drug names"})

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM drugs WHERE name LIKE ?", (f"%{drug1_name}%",))
    drug1 = cursor.fetchone()

    cursor.execute("SELECT * FROM drugs WHERE name LIKE ?", (f"%{drug2_name}%",))
    drug2 = cursor.fetchone()

    if not drug1:
        conn.close()
        return jsonify({"error": f"Drug not found: {drug1_name}"})

    if not drug2:
        conn.close()
        return jsonify({"error": f"Drug not found: {drug2_name}"})

    cursor.execute("""
        SELECT i.*, d1.name as drug1_name, d2.name as drug2_name
        FROM interactions i
        JOIN drugs d1 ON i.drug1_id = d1.id
        JOIN drugs d2 ON i.drug2_id = d2.id
        WHERE (i.drug1_id = ? AND i.drug2_id = ?)
           OR (i.drug1_id = ? AND i.drug2_id = ?)
    """, (drug1["id"], drug2["id"], drug2["id"], drug1["id"]))

    interaction = cursor.fetchone()
    conn.close()

    if interaction:
        return jsonify({
            "found": True,
            "drug1": dict(drug1),
            "drug2": dict(drug2),
            "interaction": dict(interaction)
        })
    else:
        return jsonify({
            "found": False,
            "drug1": dict(drug1),
            "drug2": dict(drug2),
            "message": "No known interaction found between these drugs in our database. Always consult a pharmacist or physician for complete drug interaction checking."
        })


@app.route("/api/drug-interactions/<int:drug_id>")
def get_drug_interactions(drug_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM drugs WHERE id = ?", (drug_id,))
    drug = cursor.fetchone()

    if not drug:
        conn.close()
        return jsonify({"error": "Drug not found"})

    cursor.execute("""
        SELECT i.*, d1.name as drug1_name, d2.name as drug2_name
        FROM interactions i
        JOIN drugs d1 ON i.drug1_id = d1.id
        JOIN drugs d2 ON i.drug2_id = d2.id
        WHERE i.drug1_id = ? OR i.drug2_id = ?
        ORDER BY
            CASE i.severity
                WHEN 'Major' THEN 1
                WHEN 'Moderate' THEN 2
                WHEN 'Minor' THEN 3
            END
    """, (drug_id, drug_id))

    interactions = []
    for row in cursor.fetchall():
        item = dict(row)
        if item["drug1_id"] == drug_id:
            item["interacts_with"] = item["drug2_name"]
        else:
            item["interacts_with"] = item["drug1_name"]
        interactions.append(item)

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

    conn.close()
    return jsonify({
        "total_drugs": total_drugs,
        "total_interactions": total_interactions,
        "major": major,
        "moderate": moderate,
        "minor": minor
    })


if __name__ == "__main__":
    create_database()
    print("Drug Interaction Checker starting...")
    print("Open your browser and go to: http://127.0.0.1:5000")
    app.run(debug=True)
