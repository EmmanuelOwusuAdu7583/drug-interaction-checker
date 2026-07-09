# ============================================
# DRUG INTERACTION CHECKER - COMMUNITY SUBMISSIONS MODULE
# Adds ability for users to submit new drug interactions
# and an admin dashboard to review all submissions
# By Emmanuel Owusu Adu
# ============================================

# Add these imports near the top of your existing app.py, alongside what's already there:
#
# import os
# from flask import session, redirect, url_for
#
# Then add these two lines right after app = Flask(__name__):
#
# app.secret_key = os.environ.get("SECRET_KEY", "local-dev-secret-change-this")
# ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "local-dev-password-change-this")


# ============ ADD THIS TABLE TO YOUR create_database() FUNCTION ============
#
# Add this cursor.execute() block inside your existing create_database() function,
# alongside your existing drugs and interactions CREATE TABLE statements:
#
# cursor.execute("""
#     CREATE TABLE IF NOT EXISTS submitters (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         name TEXT NOT NULL,
#         email TEXT NOT NULL,
#         profession TEXT,
#         created_at TEXT NOT NULL
#     )
# """)
#
# cursor.execute("""
#     CREATE TABLE IF NOT EXISTS submitted_interactions (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         submitter_id INTEGER NOT NULL,
#         drug1_name TEXT NOT NULL,
#         drug2_name TEXT NOT NULL,
#         severity TEXT NOT NULL,
#         description TEXT NOT NULL,
#         clinical_effects TEXT,
#         management TEXT,
#         submitted_at TEXT NOT NULL,
#         FOREIGN KEY (submitter_id) REFERENCES submitters (id)
#     )
# """)


# ============ PASTE EVERYTHING BELOW THIS LINE INTO app.py ============
# Place it above your existing "if __name__ == '__main__':" block


# ============ PUBLIC ROUTES ============

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

    cursor.execute("SELECT id FROM submitters WHERE email = ?", (email,))
    existing = cursor.fetchone()

    if existing:
        submitter_id = existing["id"]
    else:
        cursor.execute("""
            INSERT INTO submitters (name, email, profession, created_at)
            VALUES (?, ?, ?, ?)
        """, (name, email, profession, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        submitter_id = cursor.lastrowid

    cursor.execute("""
        INSERT INTO submitted_interactions
        (submitter_id, drug1_name, drug2_name, severity, description, clinical_effects, management, submitted_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (submitter_id, drug1_name, drug2_name, severity, description, clinical_effects, management,
          datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Thank you. Your submitted interaction has been added and is now visible in the interaction checker."
    })


# ============ MODIFY YOUR EXISTING check_interaction ROUTE ============
# Your existing /api/check-interaction route only checks the built-in `interactions` table.
# Replace that entire function with this version, which checks BOTH the built-in database
# AND community-submitted interactions, so newly added ones show up in searches too.

@app.route("/api/check-interaction")
def check_interaction_with_community():
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

    # Check the built-in interactions table first, if both drugs exist there
    if drug1 and drug2:
        cursor.execute("""
            SELECT i.*, d1.name as drug1_name, d2.name as drug2_name
            FROM interactions i
            JOIN drugs d1 ON i.drug1_id = d1.id
            JOIN drugs d2 ON i.drug2_id = d2.id
            WHERE (i.drug1_id = ? AND i.drug2_id = ?)
               OR (i.drug1_id = ? AND i.drug2_id = ?)
        """, (drug1["id"], drug2["id"], drug2["id"], drug1["id"]))
        builtin_interaction = cursor.fetchone()

        if builtin_interaction:
            conn.close()
            return jsonify({
                "found": True,
                "source": "verified",
                "drug1": dict(drug1),
                "drug2": dict(drug2),
                "interaction": dict(builtin_interaction)
            })

    # Check community-submitted interactions regardless of whether drugs are in the main database
    cursor.execute("""
        SELECT si.*, sub.name as submitter_name, sub.profession
        FROM submitted_interactions si
        JOIN submitters sub ON si.submitter_id = sub.id
        WHERE (LOWER(si.drug1_name) LIKE LOWER(?) AND LOWER(si.drug2_name) LIKE LOWER(?))
           OR (LOWER(si.drug1_name) LIKE LOWER(?) AND LOWER(si.drug2_name) LIKE LOWER(?))
        ORDER BY si.submitted_at DESC
        LIMIT 1
    """, (f"%{drug1_name}%", f"%{drug2_name}%", f"%{drug2_name}%", f"%{drug1_name}%"))
    community_interaction = cursor.fetchone()

    conn.close()

    if community_interaction:
        return jsonify({
            "found": True,
            "source": "community",
            "drug1": {"name": drug1_name, "generic_name": "", "description": "", "drug_class": ""} if not drug1 else dict(drug1),
            "drug2": {"name": drug2_name, "generic_name": "", "description": "", "drug_class": ""} if not drug2 else dict(drug2),
            "interaction": dict(community_interaction),
            "submitted_by": community_interaction["submitter_name"],
            "submitter_profession": community_interaction["profession"]
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


# ============ ADMIN ROUTES ============

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
