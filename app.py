from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
import pandas as pd
import os
from datetime import datetime
from openpyxl import load_workbook
from io import BytesIO

app = Flask(__name__, template_folder="templates")

WORKBOOK_PATH = os.path.join(os.getcwd(), "SCLOG.xlsx")

# -----------------------------
# Load Sheet Helper
# -----------------------------
def load_sheet_df(sheet_name):
    try:
        return pd.read_excel(WORKBOOK_PATH, sheet_name=sheet_name, engine="openpyxl")
    except:
        return pd.DataFrame()


# -----------------------------
# MULTI-DISCIPLINE MAPPING
# -----------------------------
PROFILE_SHEETS = {
    "": "Mapping",               # default
    "health": "Mapping_health",
    "sc": "Mapping_sc",
    "eng": "Mapping_eng",
    "socs": "Mapping_socs",
    "edu": "Mapping_edu",
    "bus": "Mapping_bus",
    "arts": "Mapping_arts"
}


def get_mapping_dict(profile=None):
    sheet = PROFILE_SHEETS.get(profile or "", "Mapping")
    df = load_sheet_df(sheet)
    if df.empty:
        return pd.DataFrame()
    df.columns = [c.strip() for c in df.columns]
    return df


# -----------------------------
# PLO DETAILS
# -----------------------------
def get_plo_details(plo, profile=None):
    df = get_mapping_dict(profile)
    if df.empty:
        return None

    mask = df[df.columns[0]].astype(str).str.strip().str.upper() == str(plo).strip().upper()

    if mask.any():
        row = df[mask].iloc[0]
        cols = {c.lower(): c for c in df.columns}
        return {
            "PLO": row[df.columns[0]],
            "SC_Code": row.get(cols.get("sc code"), ""),
            "SC_Desc": row.get(cols.get("sc description"), ""),
            "VBE": row.get(cols.get("vbe"), ""),
            "Domain": row.get(cols.get("domain"), "")
        }
    return None


# -----------------------------
# Criterion & Condition
# -----------------------------
def get_criterion_phrase(domain, bloom):
    df = load_sheet_df("Criterion")
    if df.empty:
        return "", ""

    df.columns = [c.strip() for c in c in df.columns]

    dom_col = next((c for c in df.columns if "domain" in c.lower()), None)
    bloom_col = next((c for c in df.columns if "bloom" in c.lower()), None)
    crit_col = next((c for c in df.columns if "criterion" in c.lower()), None)
    cond_col = next((c for c in df.columns if "condition" in c.lower()), None)

    mask = (df[dom_col].astype(str).str.lower() == domain.lower()) & \
           (df[bloom_col].astype(str).str.lower() == bloom.lower())

    if mask.any():
        row = df[mask].iloc[0]
        return str(row.get(crit_col, "")), str(row.get(cond_col, ""))
    return "", ""


# -----------------------------
# Default Teaching Condition
# -----------------------------
def get_default_condition(domain):
    mapping = {
        "cognitive": "based on case scenarios or clinical data",
        "affective": "during clinical or group activities",
        "psychomotor": "under supervised practical conditions"
    }
    return mapping.get(domain.lower(), "")


# -----------------------------
# Assessment + Evidence
# -----------------------------
def get_assessment_and_evidence(bloom, domain):
    domain_lower = domain.lower()
    if domain_lower in ("affective", "psychomotor"):
        df = load_sheet_df("Assess_Affective_Psychomotor")
    else:
        df = load_sheet_df("Bloom_Assessments")

    if df.empty:
        return "", ""

    df.columns = [c.strip() for c in df.columns]
    mask = df[df.columns[0]].astype(str).str.lower() == bloom.lower()

    if mask.any():
        row = df[mask].iloc[0]
        return str(row[df.columns[1]]), str(row[df.columns[2]])

    return "", ""


# -----------------------------
# CLO Sentence Builder
# -----------------------------
def construct_clo_sentence(verb, content, sc_desc, condition, criterion, vbe):
    text = f"{verb} {content}"
    if sc_desc: text += f" with {sc_desc.lower()}"
    if condition: text += f" {condition}"
    if criterion: text += f" {criterion}"
    if vbe: text += f" guided by {vbe.lower()}"

    text = text.strip()
    if text and not text.endswith("."):
        text = text[0].upper() + text[1:] + "."
    return text


# -----------------------------
# CLO Table Handling
# -----------------------------
def read_clo_table():
    try:
        return pd.read_excel(WORKBOOK_PATH, sheet_name="CLO_Table", engine="openpyxl")
    except:
        return pd.DataFrame()


def write_clo_table(df):
    try:
        book = load_workbook(WORKBOOK_PATH)
        if "CLO_Table" in book.sheetnames:
            del book["CLO_Table"]

        with pd.ExcelWriter(WORKBOOK_PATH, engine="openpyxl", mode="a") as writer:
            writer._book = book
            df.to_excel(writer, sheet_name="CLO_Table", index=False)
    except Exception as e:
        print("Error:", e)


# -----------------------------
# ROUTES
# -----------------------------
@app.route("/")
def index():
    profile = request.args.get("profile", "").strip().lower() or ""

    df_map = get_mapping_dict(profile)
    plos = df_map[df_map.columns[0]].dropna().astype(str).tolist() if not df_map.empty else []

    df_ct = read_clo_table()
    table_html = df_ct.to_html(classes="table table-striped table-sm", index=False) \
        if not df_ct.empty else "<p>No CLO records yet.</p>"

    return render_template("generator.html",
                           plos=plos,
                           table_html=table_html,
                           profile=profile)


@app.route("/generate", methods=["POST"])
def generate():
    plo = request.form.get("plo")
    bloom = request.form.get("bloom")
    verb = request.form.get("verb")
    content = request.form.get("content")
    course = request.form.get("course")
    cw = request.form.get("cw")

    profile = request.args.get("profile", "").strip().lower() or ""

    details = get_plo_details(plo, profile) or {}
    domain = details.get("Domain", "")
    sc_code = details.get("SC_Code", "")
    sc_desc = details.get("SC_Desc", "")
    vbe = details.get("VBE", "")

    criterion, condition = get_criterion_phrase(domain, bloom)
    if not condition:
        condition = get_default_condition(domain)

    assessment, evidence = get_assessment_and_evidence(bloom, domain)

    clo = construct_clo_sentence(verb, content, sc_desc, condition, criterion, vbe)

    # Save to Excel
    df = read_clo_table()
    new_row = {
        "ID": len(df) + 1 if not df.empty else 1,
        "Time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "Course": course,
        "PLO": plo,
        "Bloom": bloom,
        "FullCLO": clo,
        "Mapping (SC + VBE)": f"{sc_code} — {vbe}",
        "Assessment Methods": assessment,
        "Evidence of Assessment": evidence,
        "Coursework Assessment Percentage (%)": cw
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    write_clo_table(df)

    return jsonify({
        "clo": clo,
        "assessment": assessment,
        "evidence": evidence
    })


@app.route("/reset_table")
def reset_table():
    df_empty = pd.DataFrame(columns=[
        "ID", "Time", "Course", "PLO", "Bloom", "FullCLO",
        "Mapping (SC + VBE)", "Assessment Methods",
        "Evidence of Assessment", "Coursework Assessment Percentage (%)"
    ])

    book = load_workbook(WORKBOOK_PATH)
    if "CLO_Table" in book.sheetnames:
        del book["CLO_Table"]

    with pd.ExcelWriter(WORKBOOK_PATH, engine="openpyxl", mode="a") as writer:
        writer._book = book
        df_empty.to_excel(writer, sheet_name="CLO_Table", index=False)

    return redirect(url_for("index"))


# -----------------------------
# API ENDPOINTS
# -----------------------------
@app.route("/api/get_blooms/<plo>")
def api_get_blooms(plo):
    profile = request.args.get("profile", "").strip().lower() or ""
    details = get_plo_details(plo, profile)
    if not details:
        return jsonify([])

    domain = details.get("Domain", "").lower()
    sheet = {
        "cognitive": "Bloom_Cognitive",
        "affective": "Bloom_Affective",
        "psychomotor": "Bloom_Psychomotor"
    }.get(domain)

    df = load_sheet_df(sheet)
    if df.empty:
        return jsonify([])

    blooms = df.iloc[:, 0].dropna().astype(str).tolist()
    return jsonify(blooms)


@app.route("/api/get_verbs/<plo>/<bloom>")
def api_get_verbs(plo, bloom):
    profile = request.args.get("profile", "").strip().lower() or ""
    details = get_plo_details(plo, profile)
    if not details:
        return jsonify([])

    domain = details.get("Domain", "").lower()
    sheet = {
        "cognitive": "Bloom_Cognitive",
        "affective": "Bloom_Affective",
        "psychomotor": "Bloom_Psychomotor"
    }.get(domain)

    df = load_sheet_df(sheet)
    if df.empty:
        return jsonify([])

    mask = df.iloc[:, 0].astype(str).str.lower() == bloom.lower()
    if not mask.any():
        return jsonify([])

    raw = str(df.loc[mask].iloc[0, 1])
    verbs = [v.strip() for v in raw.split(",") if v.strip()]
    return jsonify(verbs)


@app.route("/api/debug_plo/<plo>")
def api_debug_plo(plo):
    profile = request.args.get("profile", "").strip().lower() or ""
    details = get_plo_details(plo, profile)
    return jsonify({"plo": plo, "details": details or {}, "exists": bool(details)})


# -----------------------------
# Run App
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)
