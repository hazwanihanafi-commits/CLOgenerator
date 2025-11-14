import pandas as pd
import os
import json
from flask import Flask, render_template, request, jsonify, send_file
from openpyxl import load_workbook
from io import BytesIO
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, "static"),
    template_folder=os.path.join(BASE_DIR, "templates")
)

WORKBOOK_PATH = os.path.join(BASE_DIR, "SCLOG.xlsx")
FRONT_JSON = os.path.join(app.static_folder, "data", "SCLOG_front.json")

# ----------------------------------------------------
# LOAD FRONT JSON (IEG, PEO, PLO, Statements, Indicators)
# ----------------------------------------------------
with open(FRONT_JSON, "r", encoding="utf-8") as f:
    MAP = json.load(f)


# ----------------------------------------------------
# HELPERS TO LOAD EXCEL SHEETS
# ----------------------------------------------------
def load_df(sheet):
    """Load a sheet safely"""
    try:
        return pd.read_excel(WORKBOOK_PATH, sheet_name=sheet, engine="openpyxl")
    except Exception:
        return pd.DataFrame()


def get_mapping_sheet(profile):
    """Return SC Mapping sheet based on profile"""
    mapping_sheets = {
        "health": "Mapping_health",
        "sc": "Mapping_sc",
        "eng": "Mapping_eng",
        "socs": "Mapping_socs",
        "edu": "Mapping_edu",
        "bus": "Mapping_bus",
        "arts": "Mapping_arts"
    }
    return load_df(mapping_sheets.get(profile, "Mapping_sc"))


# ----------------------------------------------------
# GET PLO DETAILS (from Excel → Mapping_sc etc.)
# ----------------------------------------------------
def get_plo_details(plo, profile):
    df = get_mapping_sheet(profile)
    if df.empty:
        return None

    df.columns = [str(c).strip() for c in df.columns]
    col_plo = df.columns[0]

    row = df[df[col_plo].astype(str).str.upper() == plo.upper()]
    if row.empty:
        return None

    r = row.iloc[0]

    return {
        "SC_Code": r.get("SC Code", ""),
        "SC_Desc": r.get("SC Description", ""),
        "VBE": r.get("VBE", ""),
        "Domain": r.get("Domain", "")
    }


# ----------------------------------------------------
# LOAD BLOOMS (from Excel)
# ----------------------------------------------------
@app.route("/api/get_blooms/<plo>")
def api_get_blooms(plo):
    profile = request.args.get("profile", "sc").lower()
    details = get_plo_details(plo, profile)

    if not details:
        return jsonify([])

    domain = (details["Domain"] or "").lower()

    sheet_map = {
        "cognitive": "Bloom_Cognitive",
        "affective": "Bloom_Affective",
        "psychomotor": "Bloom_Psychomotor"
    }

    df = load_df(sheet_map.get(domain, "Bloom_Cognitive"))
    if df.empty:
        return jsonify([])

    blooms = df.iloc[:, 0].dropna().astype(str).tolist()
    return jsonify(blooms)


# ----------------------------------------------------
# LOAD VERBS (from Excel)
# ----------------------------------------------------
@app.route("/api/get_verbs/<plo>/<bloom>")
def api_get_verbs(plo, bloom):
    profile = request.args.get("profile", "sc").lower()
    details = get_plo_details(plo, profile)

    if not details:
        return jsonify([])

    domain = (details["Domain"] or "").lower()

    sheet_map = {
        "cognitive": "Bloom_Cognitive",
        "affective": "Bloom_Affective",
        "psychomotor": "Bloom_Psychomotor"
    }

    df = load_df(sheet_map.get(domain, "Bloom_Cognitive"))
    if df.empty:
        return jsonify([])

    mask = df.iloc[:, 0].astype(str).str.lower() == bloom.lower()
    if not mask.any():
        return jsonify([])

    verbs = [
        v.strip() for v in str(df[mask].iloc[0, 1]).split(",")
        if v.strip()
    ]
    return jsonify(verbs)


# ----------------------------------------------------
# META INFO (SC Code + SC Desc + VBE + Condition + Criterion)
# ----------------------------------------------------
@app.route("/api/get_meta/<plo>/<bloom>")
def api_get_meta(plo, bloom):
    profile = request.args.get("profile", "sc").lower()

    details = get_plo_details(plo, profile)
    if not details:
        return jsonify({})

    # Domain → Bloom criterion
    domain = (details["Domain"] or "").lower()
    criterion = ""
    condition = ""

    df = load_df("Criterion")
    if not df.empty:
        df.columns = [c.strip() for c in df.columns]
        mask = (
            (df.iloc[:,0].str.lower() == domain) &
            (df.iloc[:,1].str.lower() == bloom.lower())
        )
        if mask.any():
            row = df[mask].iloc[0]
            criterion = row.iloc[2]
            condition = row.iloc[3]

    # default fallback
    if not condition:
        condition = {
            "cognitive": "interpreting tasks",
            "affective": "engaging with peers",
            "psychomotor": "performing skills"
        }.get(domain, "")

    connector = "by" if domain == "psychomotor" else "when"
    condition_final = f"{connector} {condition}"

    return jsonify({
        "sc_code": details["SC_Code"],
        "sc_desc": details["SC_Desc"],
        "vbe": details["VBE"],
        "domain": domain,
        "criterion": criterion,
        "condition": condition_final
    })


# ----------------------------------------------------
# IEG → PEO → PLO mapping APIs (from JSON)
# ----------------------------------------------------
@app.route("/api/mapping")
def api_mapping():
    return jsonify(MAP)


@app.route("/api/get_peos/<ieg>")
def api_get_peos(ieg):
    return jsonify(MAP["IEGtoPEO"].get(ieg, []))


@app.route("/api/get_plos/<peo>")
def api_get_plos(peo):
    return jsonify(MAP["PEOtoPLO"].get(peo, []))


@app.route("/api/get_statement/<level>/<stype>/<code>")
def api_get_statement(level, stype, code):
    stype = stype.upper()

    if stype == "PEO":
        return jsonify(MAP["PEOstatements"].get(level, {}).get(code, ""))

    if stype == "PLO":
        return jsonify(MAP["PLOstatements"].get(level, {}).get(code, ""))

    return jsonify("")


# ----------------------------------------------------
# GENERATE CLO
# ----------------------------------------------------
@app.route("/generate", methods=["POST"])
def generate():
    profile = request.form.get("profile", "sc").lower()

    plo = request.form.get("plo", "")
    bloom = request.form.get("bloom", "")
    verb = request.form.get("verb", "")
    content = request.form.get("content", "")
    course = request.form.get("course", "")
    cw = request.form.get("cw", "")
    level = request.form.get("level", "Degree")

    details = get_plo_details(plo, profile)
    if not details:
        return jsonify({"error": "Invalid PLO"}), 400

    domain = details["Domain"].lower()
    sc_desc = details["SC_Desc"]
    vbe = details["VBE"]

    # Meta from Excel
    meta = get_meta_data(plo, bloom, profile=None) if False else None

    # Condition + Criterion
    meta_res = api_get_meta(plo, bloom).json
    condition_core = meta_res["condition"].replace("when ", "").replace("by ", "")
    criterion = meta_res["criterion"]

    connector = "when" if domain != "psychomotor" else "by"

    clo = (
        f"{verb.lower()} {content} using {sc_desc.lower()} "
        f"{connector} {condition_core} "
        f"guided by {vbe.lower()}."
    ).capitalize()

    # Variants
    variants = {
        "Standard": clo,
        "Critical Thinking": clo.replace("using", "critically using"),
        "Action": clo.replace("when", "while"),
    }

    # IEG–PEO chain
    peo = None
    ieg = None

    for p, plos in MAP["PEOtoPLO"].items():
        if plo in plos:
            peo = p

    for i, peos in MAP["IEGtoPEO"].items():
        if peo in peos:
            ieg = i

    plo_statement = MAP["PLOstatements"][level].get(plo, "")
    peo_statement = MAP["PEOstatements"][level].get(peo, "")

    return jsonify({
        "clo": clo,
        "clo_options": variants,
        "sc_code": details["SC_Code"],
        "sc_desc": sc_desc,
        "vbe": vbe,
        "domain": domain,
        "criterion": criterion,
        "condition": condition_core,
        "ieg": ieg,
        "peo": peo,
        "plo_statement": plo_statement,
        "peo_statement": peo_statement,
        "assessment": "",
        "evidence": "",
        "rubric": {
            "indicator": f"Ability to {verb.lower()} {sc_desc.lower()}",
            "excellent": "Performs at an excellent level",
            "good": "Performs well",
            "satisfactory": "Meets minimum level",
            "poor": "Below expected"
        }
    })


# ----------------------------------------------------
# RUN APP
# ----------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
