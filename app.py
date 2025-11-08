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
    except:
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

    # Normalize column names (remove spaces, lowercase)
    colmap = {c.strip().lower().replace(" ", ""): c for c in df.columns}

    # Identify columns regardless of format in Excel
    col_plo = list(df.columns)[0]                 # first column is always PLO
    col_sc = colmap.get("sccode")
    col_desc = colmap.get("scdescription")
    col_vbe = colmap.get("vbe")
    col_domain = colmap.get("domain")

    # Match PLO
    mask = df[col_plo].astype(str).str.strip().str.upper() == str(plo).strip().upper()
    if not mask.any():
        return None

    row = df[mask].iloc[0]

    return {
        "PLO": row[col_plo],
        "SC_Code": row.get(col_sc, ""),
        "SC_Desc": row.get(col_desc, ""),
        "VBE": row.get(col_vbe, ""),
        "Domain": row.get(col_domain, "")
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

    mask = (df[dom_col].astype(str).str.lower() == domain.lower()) & \
           (df[bloom_col].astype(str).str.lower() == bloom.lower())

    if not mask.any():
        return "", ""

    row = df[mask].iloc[0]
    return str(row[crit_col]), str(row[cond_col])

def get_default_condition(domain):
    mapping = {
        "cognitive": "based on case scenarios or clinical data",
        "affective": "during clinical or group activities",
        "psychomotor": "under supervised practical conditions"
    }
    return mapping.get(domain.lower(), "")

# ------------------------------------------------------------
# ASSESSMENT & EVIDENCE
# ------------------------------------------------------------
def get_assessment_and_evidence(bloom, domain):
    domain = domain.lower()
    sheet = "Assess_Affective_Psychomotor" if domain in ("affective", "psychomotor") else "Bloom_Assessments"
    df = load_sheet_df(sheet)

    if df.empty:
        return "", ""

    df.columns = [c.strip() for c in df.columns]
    bloom_col, assess_col, evid_col = df.columns[:3]

    mask = df[bloom_col].astype(str).str.lower() == bloom.lower()

    if not mask.any():
        return "", ""

    row = df[mask].iloc[0]
    return str(row[assess_col]), str(row[evid_col])

# ------------------------------------------------------------
# POLISHED CONDITION REWRITER (Version 5)
# ------------------------------------------------------------
def polish_condition(raw_condition, profile=None, bloom=None):
    profile = (profile or "").lower()
    bloom   = (bloom or "").lower()
    cond    = (raw_condition or "").strip().lower()

    profile_contexts = {
        "":       "in discipline-relevant contexts",
        "health": "in clinical or health decision-making contexts",
        "sc":     "in computational or system-analysis contexts",
        "eng":    "in technical or engineering problem-solving contexts",
        "bus":    "in organisational or strategic decision-making contexts",
        "edu":    "in teaching, learning, or pedagogical analysis contexts",
        "socs":   "in social or behavioural evaluation contexts",
        "arts":   "in creative or cultural interpretation contexts"
    }
    default_context = profile_contexts.get(profile, "in professional contexts")

    if cond:
        if cond.startswith(("when", "while", "during")):
            cond = f"in the context of {cond[4:].strip()}"
        elif cond.startswith("based on"):
            cond = f"when working with {cond[8:].strip()}"
        else:
            cond = f"in the context of {cond}"
    else:
        bloom_contexts = {
            "remember":   "in foundational recall activities",
            "understand": "when interpreting essential concepts",
            "apply":      "in practical or real-world situations",
            "analyse":    "when examining complex information or cases",
            "evaluate":   "when making informed or evidence-based judgements",
            "create":     "in generating new ideas, strategies, or solutions"
        }
        cond = bloom_contexts.get(bloom, default_context)

    return cond


# ------------------------------------------------------------
# VERSION 5 – INTELLIGENT, POLISHED, ACADEMIC CLO REWRITER
# ------------------------------------------------------------
def construct_clo_sentence(verb, content, sc_desc, condition, criterion, vbe, profile=None, bloom=None):
    verb      = (verb or "").strip().capitalize()
    content   = (content or "").strip()
    sc_desc   = (sc_desc or "").strip()
    condition = (condition or "").strip()
    criterion = (criterion or "").strip()
    vbe       = (vbe or "").strip()
    profile   = (profile or "").strip().lower()
    bloom     = (bloom or "").strip().lower()

    # SC → elegant action phrase
    sc_lower = sc_desc.lower()
    if sc_lower.startswith("integrated"):
        sc_phrase = "through integrated problem solving"
    elif sc_lower.startswith("leadership"):
        sc_phrase = "by exercising leadership, autonomy, and responsibility"
    elif sc_lower.startswith("communication"):
        sc_phrase = "using effective communication skills"
    elif sc_lower.startswith("critical"):
        sc_phrase = "through critical and analytical reasoning"
    elif sc_lower.startswith("creative") or "creativity" in sc_lower:
        sc_phrase = "through creative and innovative thinking"
    else:
        sc_phrase = f"using {sc_lower}"

    # Bloom → sentence depth phrase
    bloom_map = {
        "remember":   "in demonstrating foundational recall",
        "understand": "in demonstrating conceptual understanding",
        "apply":      "in applying knowledge to practical situations",
        "analyse":    "in examining relationships, patterns, or structures",
        "evaluate":   "in making informed judgements or decisions",
        "create":     "in synthesising ideas into coherent solutions"
    }
    bloom_phrase = bloom_map.get(bloom, "")

    # Criterion → quality phrase
    if criterion:
        if criterion.lower().startswith(("demonstrating", "showing", "exhibiting")):
            criterion_phrase = criterion
        else:
            criterion_phrase = f"demonstrating {criterion.lower()}"
    else:
        criterion_phrase = ""

    # VBE → ethical frame
    vbe_phrase = f"in a manner guided by {vbe.lower()}" if vbe else ""

    # Build CLO
    parts = [
        f"{verb} {content}",
        sc_phrase,
        condition,
        bloom_phrase,
        criterion_phrase,
        vbe_phrase
    ]
    sentence = " ".join([p for p in parts if p]).strip()
    sentence = sentence[0].upper() + sentence[1:]
    if not sentence.endswith("."):
        sentence += "."

    return " ".join(sentence.split())


# ------------------------------------------------------------
# CLO TABLE
# ------------------------------------------------------------
def read_clo_table():
    try:
        return pd.read_excel(WORKBOOK_PATH, sheet_name="CLO_Table", engine="openpyxl")
    except:
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

    assessment, evidence = get_assessment_and_evidence(bloom, domain)

    clo = construct_clo_sentence(
        verb, content, details["SC_Desc"], condition, criterion, details["VBE"]
    )

    df = read_clo_table()

    new_row = {
        "ID": len(df)+1 if not df.empty else 1,
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

@app.route("/api/get_blooms/<plo>")
def api_get_blooms(plo):
    profile = request.args.get("profile", "").strip().lower()
    details = get_plo_details(plo, profile)
    if not details:
        return jsonify([])

    domain = details["Domain"].lower()
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

    domain = details["Domain"].lower()
    sheetmap = {
        "cognitive": "Bloom_Cognitive",
        "affective": "Bloom_Affective",
        "psychomotor": "Bloom_Psychomotor"
    }

    df = load_sheet_df(sheetmap.get(domain))
    if df.empty:
        return jsonify([])

    mask = df.iloc[:,0].astype(str).str.lower() == bloom.lower()
    if not mask.any():
        return jsonify([])

    return jsonify([v.strip() for v in str(df[mask].iloc[0,1]).split(",")])

@app.route("/api/debug_plo/<plo>")
def api_debug_plo(plo):
    profile = request.args.get("profile","")
    return jsonify({
        "plo": plo,
        "details": get_plo_details(plo, profile) or {},
        "exists": bool(get_plo_details(plo, profile))
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

