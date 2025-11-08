from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
import pandas as pd
import os
from datetime import datetime
from openpyxl import load_workbook
from io import BytesIO

app = Flask(__name__, template_folder="templates")

WORKBOOK_PATH = os.path.join(os.getcwd(), "SCLOG.xlsx")

# ------------------------------------------------------------
# DISCIPLINE → SHEET MAP
# ------------------------------------------------------------
PROFILE_SHEET_MAP = {
    "": "Mapping",
    "health": "Mapping_health",
    "sc": "Mapping_sc",
    "eng": "Mapping_eng",
    "socs": "Mapping_socs",
    "edu": "Mapping_edu",
    "bus": "Mapping_bus",
    "arts": "Mapping_arts"
}

# ------------------------------------------------------------
# LOAD EXCEL SHEET
# ------------------------------------------------------------
def load_sheet_df(sheet_name):
    try:
        return pd.read_excel(WORKBOOK_PATH, sheet_name=sheet_name, engine="openpyxl")
    except Exception:
        return pd.DataFrame()

# ------------------------------------------------------------
# GET MAPPING TABLE
# ------------------------------------------------------------
def get_mapping_dict(profile=None):
    profile = (profile or "").strip().lower()
    sheet = PROFILE_SHEET_MAP.get(profile, "Mapping")
    df = load_sheet_df(sheet)
    if df.empty:
        return pd.DataFrame()
    df.columns = [str(c).strip() for c in df.columns]
    return df

# ------------------------------------------------------------
# ✅ BULLETPROOF PLO LOOKUP
# ------------------------------------------------------------
def get_plo_details(plo, profile=None):
    df = get_mapping_dict(profile)
    if df.empty:
        return None

    # Normalize column names
    colmap = {c.strip().lower().replace(" ", ""): c for c in df.columns}

    # First column is PLO by design
    col_plo = list(df.columns)[0]
    col_sc = colmap.get("sccode")
    col_desc = colmap.get("scdescription")
    col_vbe = colmap.get("vbe")
    col_domain = colmap.get("domain")

    mask = df[col_plo].astype(str).str.strip().str.upper() == str(plo).strip().upper()
    if not mask.any():
        return None

    row = df[mask].iloc[0]
    return {
        "PLO": row[col_plo],
        "SC_Code": row.get(col_sc, "") if col_sc else "",
        "SC_Desc": row.get(col_desc, "") if col_desc else "",
        "VBE": row.get(col_vbe, "") if col_vbe else "",
        "Domain": row.get(col_domain, "") if col_domain else ""
    }

# ------------------------------------------------------------
# CRITERION / CONDITION
# ------------------------------------------------------------
def get_criterion_phrase(domain, bloom):
    df = load_sheet_df("Criterion")
    if df.empty:
        return "", ""

    df.columns = [c.strip() for c in df.columns]
    dom_col, bloom_col, crit_col, cond_col = df.columns[:4]

    mask = (df[dom_col].astype(str).str.lower() == str(domain).lower()) & \
           (df[bloom_col].astype(str).str.lower() == str(bloom).lower())

    if not mask.any():
        return "", ""

    row = df[mask].iloc[0]
    return str(row[crit_col]).strip(), str(row[cond_col]).strip()

def get_default_condition(domain):
    mapping = {
        "cognitive": "based on case scenarios or clinical data",
        "affective": "during clinical or group activities",
        "psychomotor": "under supervised practical conditions"
    }
    return mapping.get(str(domain).lower(), "")

# ------------------------------------------------------------
# ASSESSMENT & EVIDENCE
# ------------------------------------------------------------
def get_assessment_and_evidence(bloom, domain):
    domain = str(domain).lower()
    sheet = "Assess_Affective_Psychomotor" if domain in ("affective", "psychomotor") else "Bloom_Assessments"
    df = load_sheet_df(sheet)
    if df.empty:
        return "", ""
    df.columns = [c.strip() for c in df.columns]
    bloom_col, assess_col, evid_col = df.columns[:3]
    mask = df[bloom_col].astype(str).str.lower() == str(bloom).lower()
    if not mask.any():
        return "", ""
    row = df[mask].iloc[0]
    return str(row[assess_col]).strip(), str(row[evid_col]).strip()

# ------------------------------------------------------------
# AUTO-POLISHING
# ------------------------------------------------------------
def tidy_spaces(s):
    return " ".join(str(s or "").split())

def polish_condition(condition, profile="", bloom="", domain=""):
    """
    Light normalizer so 'Condition = under what context' reads naturally and specifically.
    Keeps your sheet-driven phrasing but adds specificity keywords per profile/domain.
    """
    base = tidy_spaces(condition)
    if not base:
        base = get_default_condition(domain)

    # Ensure it starts with a context preposition
    lowers = base.lower()
    if not lowers.startswith(("in ", "within ", "during ", "under ", "based ", "using ", "when ")):
        base = "in " + base

    # Profile-specific nudge (non-destructive)
    p = (profile or "").lower()
    d = (domain or "").lower()

    if p in ("", "health"):
        base = base.replace("case scenarios", "authentic patient case scenarios")
        base = base.replace("clinical data", "clinic and EMR data")

    if p == "sc":
        base = base.replace("case scenarios", "realistic problem sets or datasets")

    if p == "eng":
        base = base.replace("case scenarios", "design briefs or test rigs")

    if p == "socs":
        base = base.replace("case scenarios", "community or policy case scenarios")

    if p == "edu":
        base = base.replace("case scenarios", "lesson or classroom scenarios")

    if p == "bus":
        base = base.replace("case scenarios", "market or business case scenarios")

    if p == "arts":
        base = base.replace("case scenarios", "studio or performance briefs")

    # Domain gentle tweak
    if d == "psychomotor" and not any(w in lowers for w in ["simulated", "lab", "station", "practical"]):
        base += " in simulated lab/practical stations"

    return tidy_spaces(base)

def polish_sentence(s):
    s = tidy_spaces(s)
    if not s:
        return s
    s = s[0].upper() + s[1:]
    if not s.endswith("."):
        s += "."
    return s

# ------------------------------------------------------------
# CLO SENTENCE BUILDER
# ------------------------------------------------------------
def construct_clo_sentence(verb, content, sc_desc, condition, criterion, vbe):
    parts = []

    # Verb + content
    if verb and content:
        base = f"{verb.strip().lower()} {content.strip()}"
    elif content:
        base = content.strip()
    else:
        base = ""
    base = base.strip()
    if base:
        parts.append(base)

    # SC description (skills/competencies)
    if sc_desc:
        parts.append(f"using {str(sc_desc).strip().lower()}")

    # Condition (context)
    if condition:
        c = condition.strip()
        if not c.lower().startswith(("when", "during", "in", "within", "based", "under", "using")):
            c = "in " + c
        parts.append(c)

    # Criterion (quality/level)
    if criterion:
        parts.append(str(criterion).strip())

    # VBE (values)
    if vbe:
        parts.append(f"guided by {str(vbe).strip().lower()}")

    sentence = " ".join([tidy_spaces(p) for p in parts if tidy_spaces(p)])
    return polish_sentence(sentence)

# ------------------------------------------------------------
# CLO TABLE
# ------------------------------------------------------------
def read_clo_table():
    try:
        return pd.read_excel(WORKBOOK_PATH, sheet_name="CLO_Table", engine="openpyxl")
    except Exception:
        return pd.DataFrame()

def write_clo_table(df):
    book = load_workbook(WORKBOOK_PATH)
    if "CLO_Table" in book.sheetnames:
        del book["CLO_Table"]
    with pd.ExcelWriter(WORKBOOK_PATH, engine="openpyxl", mode="a") as writer:
        writer._book = book
        df.to_excel(writer, sheet_name="CLO_Table", index=False)

# ------------------------------------------------------------
# ROUTES
# ------------------------------------------------------------
@app.route("/")
def index():
    profile = request.args.get("profile", "").strip().lower()
    df_map = get_mapping_dict(profile)
    plos = df_map[df_map.columns[0]].dropna().astype(str).tolist() if not df_map.empty else []
    df_ct = read_clo_table()
    table_html = df_ct.to_html(classes="table table-striped table-sm", index=False) if not df_ct.empty else "<p>No CLO records yet.</p>"
    return render_template("generator.html", plos=plos, table_html=table_html, profile=profile)

@app.route("/generate", methods=["POST"])
def generate():
    profile = request.args.get("profile", "").strip().lower()
    plo = request.form.get("plo")
    bloom = request.form.get("bloom")
    verb = request.form.get("verb")
    content = request.form.get("content")
    course = request.form.get("course")
    cw = request.form.get("cw")

    details = get_plo_details(plo, profile)
    if not details:
        return jsonify({"error": "PLO not found"}), 400

    domain = details["Domain"]

    criterion, condition = get_criterion_phrase(domain, bloom)
    if not condition:
        condition = get_default_condition(domain)

    # auto-assessment/evidence by bloom & domain
    assessment, evidence = get_assessment_and_evidence(bloom, domain)

    # auto-polish condition
    polished_condition = polish_condition(condition, profile=profile, bloom=bloom, domain=domain)

    # build CLO
    clo = construct_clo_sentence(
        verb=verb,
        content=content,
        sc_desc=details["SC_Desc"],
        condition=polished_condition,
        criterion=criterion,
        vbe=details["VBE"]
    )

    # Save CLO into table
    df = read_clo_table()
    new_row = {
        "ID": len(df) + 1 if not df.empty else 1,
        "Time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "Course": course,
        "PLO": plo,
        "Bloom": bloom,
        "FullCLO": clo,
        "Mapping (SC + VBE)": f"{details['SC_Code']} — {details['VBE']}",
        "Assessment Methods": assessment,
        "Evidence of Assessment": evidence,
        "Coursework Assessment Percentage (%)": cw,
        "Profile": profile
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    write_clo_table(df)

    return jsonify({"clo": clo, "assessment": assessment, "evidence": evidence})

@app.route("/api/get_meta/<plo>/<bloom>")
def api_get_meta(plo, bloom):
    """Single call the frontend uses to auto-fill everything after PLO + Bloom."""
    profile = request.args.get("profile", "").strip().lower()
    details = get_plo_details(plo, profile)
    if not details:
        return jsonify({})

    domain = details["Domain"]
    criterion, condition = get_criterion_phrase(domain, bloom)
    if not condition:
        condition = get_default_condition(domain)
    condition = polish_condition(condition, profile=profile, bloom=bloom, domain=domain)

    assessment, evidence = get_assessment_and_evidence(bloom, domain)

    return jsonify({
        "sc_code": details.get("SC_Code", ""),
        "sc_desc": details.get("SC_Desc", ""),
        "vbe": details.get("VBE", ""),
        "domain": domain,
        "criterion": criterion,
        "condition": condition,
        "assessment": assessment,
        "evidence": evidence
    })

@app.route("/api/get_blooms/<plo>")
def api_get_blooms(plo):
    profile = request.args.get("profile", "").strip().lower()
    details = get_plo_details(plo, profile)
    if not details:
        return jsonify([])

    domain = str(details["Domain"]).lower()
    sheetmap = {
        "cognitive": "Bloom_Cognitive",
        "affective": "Bloom_Affective",
        "psychomotor": "Bloom_Psychomotor"
    }
    df = load_sheet_df(sheetmap.get(domain))
    if df.empty:
        return jsonify([])

    return jsonify(df.iloc[:, 0].dropna().astype(str).tolist())

@app.route("/api/get_verbs/<plo>/<bloom>")
def api_get_verbs(plo, bloom):
    profile = request.args.get("profile", "").strip().lower()
    details = get_plo_details(plo, profile)
    if not details:
        return jsonify([])

    domain = str(details["Domain"]).lower()
    sheetmap = {
        "cognitive": "Bloom_Cognitive",
        "affective": "Bloom_Affective",
        "psychomotor": "Bloom_Psychomotor"
    }
    df = load_sheet_df(sheetmap.get(domain))
    if df.empty:
        return jsonify([])

    mask = df.iloc[:, 0].astype(str).str.lower() == str(bloom).lower()
    if not mask.any():
        return jsonify([])

    # verbs assumed in 2nd column comma-separated
    return jsonify([v.strip() for v in str(df[mask].iloc[0, 1]).split(",") if v.strip()])

@app.route("/api/debug_plo/<plo>")
def api_debug_plo(plo):
    profile = request.args.get("profile","")
    det = get_plo_details(plo, profile)
    return jsonify({
        "plo": plo,
        "details": det or {},
        "exists": bool(det)
    })

@app.route("/reset_table")
def reset_table():
    df = pd.DataFrame(columns=[
        "ID","Time","Course","PLO","Bloom","FullCLO",
        "Mapping (SC + VBE)","Assessment Methods","Evidence of Assessment",
        "Coursework Assessment Percentage (%)","Profile"
    ])

    book = load_workbook(WORKBOOK_PATH)
    if "CLO_Table" in book.sheetnames:
        del book["CLO_Table"]

    with pd.ExcelWriter(WORKBOOK_PATH, engine="openpyxl", mode="a") as writer:
        writer._book = book
        df.to_excel(writer, sheet_name="CLO_Table", index=False)

    return redirect(url_for("index"))

@app.route("/download")
def download():
    df = read_clo_table()
    if df.empty:
        return "<p>No CLO table to download.</p>"

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="CLO_Table")
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="CLO_Table.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

if __name__ == "__main__":
    app.run(debug=True)
