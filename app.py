import pandas as pd
import os
import json
from flask import Flask, render_template, request, jsonify, send_file
from openpyxl import load_workbook
from io import BytesIO
from datetime import datetime

# ----------------------------------------
# PATH SETUP
# ----------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, "static"),
    template_folder=os.path.join(BASE_DIR, "templates")
)

print("BOOT: STATIC =", app.static_folder)
print("BOOT: TEMPLATES =", app.template_folder)

# ----------------------------------------
# FILE PATHS
# ----------------------------------------
WORKBOOK_PATH = os.path.join(BASE_DIR, "SCLOG.xlsx")
FRONT_JSON = os.path.join(app.static_folder, "data", "SCLOG_front.json")

# ----------------------------------------
# SAFE JSON LOADER
# ----------------------------------------
def safe_load_json(path):
    print(f"BOOT: Loading JSON → {path}")
    if not os.path.exists(path):
        print("ERROR: JSON file not found:", path)
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("JSON LOAD ERROR:", e)
        return {}

# Load JSON
MAP = safe_load_json(FRONT_JSON)

# Default keys
DEFAULT_MAP = {
    "IEGs": [],
    "PEOs": [],
    "PLOs": [],
    "IEGtoPEO": {},
    "PEOtoPLO": {},
    "PLOstatements": {},
    "PEOstatements": {},
    "PLOtoVBE": {},
    "PLOIndicators": {},
    "SCmapping": {}
}

for k, v in DEFAULT_MAP.items():
    if k not in MAP:
        MAP[k] = v

print("BOOT: JSON mapping loaded successfully")

# ----------------------------------------
# SAFE EXCEL LOADER
# ----------------------------------------
def load_df(sheet_name):
    if not os.path.exists(WORKBOOK_PATH):
        print("load_df: Excel not found:", WORKBOOK_PATH)
        return pd.DataFrame()

    try:
        return pd.read_excel(WORKBOOK_PATH, sheet_name=sheet_name, engine="openpyxl")
    except Exception as e:
        print(f"load_df: failed reading '{sheet_name}':", e)
        return pd.DataFrame()

# ----------------------------------------
# PROFILE → MAPPING SHEET
# ----------------------------------------
PROFILE_SHEET_MAP = {
    "health": "Mapping_health",
    "sc": "Mapping_sc",
    "eng": "Mapping_eng",
    "socs": "Mapping_socs",
    "edu": "Mapping_edu",
    "bus": "Mapping_bus",
    "arts": "Mapping_arts"
}

def get_mapping_sheet(profile):
    sheet = PROFILE_SHEET_MAP.get(profile, "Mapping")
    df = load_df(sheet)

    if df.empty:
        df = load_df("Mapping")

    return df

# ----------------------------------------
# GET PLO DETAILS
# ----------------------------------------
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

# ----------------------------------------
# get_meta_data — used inside generator
# ----------------------------------------
def get_meta_data(plo, bloom, profile="sc"):
    details = get_plo_details(plo, profile)
    if not details:
        return {}

    domain = (details["Domain"] or "").lower()
    criterion = ""
    condition = ""

    df = load_df("Criterion")
    if not df.empty:
        df.columns = [c.strip() for c in df.columns]

        mask = (
            (df.iloc[:, 0].astype(str).str.lower() == domain) &
            (df.iloc[:, 1].astype(str).str.lower() == bloom.lower())
        )
        if mask.any():
            row = df[mask].iloc[0]
            criterion = str(row.iloc[2])
            condition = str(row.iloc[3])

    if not condition:
        condition = {
            "cognitive": "interpreting tasks",
            "affective": "engaging with peers",
            "psychomotor": "performing skills"
        }.get(domain, "")

    connector = "by" if domain == "psychomotor" else "when"
    condition_final = f"{connector} {condition}"

    return {
        "sc_code": details["SC_Code"],
        "sc_desc": details["SC_Desc"],
        "vbe": details["VBE"],
        "domain": domain,
        "criterion": criterion,
        "condition": condition_final
    }

# ----------------------------------------
# API: BLOOMS
# ----------------------------------------
@app.route("/api/get_blooms/<plo>")
def api_get_blooms(plo):
    profile = request.args.get("profile", "sc").lower()
    details = get_plo_details(plo, profile)

    if not details:
        return jsonify([])

    domain = details["Domain"].lower()

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

# ----------------------------------------
# API: VERBS
# ----------------------------------------
@app.route("/api/get_verbs/<plo>/<bloom>")
def api_get_verbs(plo, bloom):
    profile = request.args.get("profile", "sc").lower()
    details = get_plo_details(plo, profile)
    if not details:
        return jsonify([])

    domain = details["Domain"].lower()

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

# ----------------------------------------
# API: META
# ----------------------------------------
@app.route("/api/get_meta/<plo>/<bloom>")
def api_get_meta(plo, bloom):
    profile = request.args.get("profile", "sc").lower()
    return jsonify(get_meta_data(plo, bloom, profile))

# ----------------------------------------
# IEG/PEO/PLO APIs
# ----------------------------------------
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

# ----------------------------------------
# GENERATE CLO — FIXED VERSION
# ----------------------------------------
@app.route("/generate", methods=["POST"])
def generate():
    profile = request.form.get("profile", "sc").lower()

    plo = request.form.get("plo", "")
    bloom = request.form.get("bloom", "")
    verb = request.form.get("verb", "")
    content = request.form.get("content", "")
    level = request.form.get("level", "Degree")

    details = get_plo_details(plo, profile)
    if not details:
        return jsonify({"error": "Invalid PLO"}), 400

    domain = details["Domain"].lower()
    sc_desc = details["SC_Desc"]
    vbe = details["VBE"]

    # META
    meta_res = get_meta_data(plo, bloom, profile)

    condition_core = (
        meta_res["condition"]
        .replace("when ", "")
        .replace("by ", "")
        .strip()
    )

    criterion = meta_res["criterion"]
    connector = "when" if domain != "psychomotor" else "by"

    clo = (
        f"{verb.lower()} {content} using {sc_desc.lower()} "
        f"{connector} {condition_core} guided by {vbe.lower()}."
    ).capitalize()

    variants = {
        "Standard": clo,
        "Critical Thinking": clo.replace("using", "critically using"),
        "Action": clo.replace("when", "while"),
    }

    # IEG → PEO chain
    peo = None
    ieg = None

    for p, plos in MAP["PEOtoPLO"].items():
        if plo in plos:
            peo = p
            break

    for i, peos in MAP["IEGtoPEO"].items():
        if peo in peos:
            ieg = i
            break

    # Statements
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
    })

# ----------------------------------------
# RUN
# ----------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
