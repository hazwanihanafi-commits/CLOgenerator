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
# SAFE JSON LOADER (prevent crash)
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

# Load IEG/PEO/PLO mapping from SCLOG_front.json safely
IEP = safe_load_json(FRONT_JSON)

# Ensure JSON keys exist (avoid KeyError later)
DEFAULT_IEP = {
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

for k, v in DEFAULT_IEP.items():
    if k not in IEP:
        IEP[k] = v

print("BOOT: JSON mapping loaded successfully.")
print("BOOT: IEG count:", len(IEP.get("IEGs", [])))
print("BOOT: PEO count:", len(IEP.get("PEOs", [])))
print("BOOT: PLO count:", len(IEP.get("PLOs", [])))

# ----------------------------------------
# SAFE EXCEL CHECK (prevent crash)
# ----------------------------------------
if not os.path.exists(WORKBOOK_PATH):
    print("WARNING: SCLOG.xlsx NOT FOUND:", WORKBOOK_PATH)
else:
    print("BOOT: Excel workbook detected:", WORKBOOK_PATH)

# ------------------------------
# Ensure MAP variable (JSON mapping) available
# ------------------------------
MAP = IEP  # keep naming used by the routes later

# ------------------------------
# Safe Excel loader (small wrapper)
# ------------------------------
def load_df(sheet_name):
    """
    Safely load a sheet from SCLOG.xlsx into a pandas DataFrame.
    Returns empty DataFrame on failure.
    """
    if not os.path.exists(WORKBOOK_PATH):
        print("load_df: workbook not found:", WORKBOOK_PATH)
        return pd.DataFrame()
    try:
        return pd.read_excel(WORKBOOK_PATH, sheet_name=sheet_name, engine="openpyxl")
    except Exception as e:
        print(f"load_df: failed to read sheet '{sheet_name}':", e)
        return pd.DataFrame()

# ------------------------------
# Mapping sheet resolver
# ------------------------------
# If you have multiple profile-specific mapping sheet names, set them here:
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
    """
    Return DataFrame for mapping sheet corresponding to profile.
    profile: 'sc','health', etc.
    """
    sheet = PROFILE_SHEET_MAP.get(profile, "Mapping")
    df = load_df(sheet)
    if df.empty:
        # fallback: try a generic "Mapping" sheet if present
        df = load_df("Mapping")
    return df

# ------------------------------
# get_meta_data helper (used by generate)
# Returns a dict similar to api_get_meta output
# ------------------------------
def get_meta_data(plo, bloom, profile="sc"):
    details = get_plo_details(plo, profile)
    if not details:
        return {}

    # Domain → Bloom criterion
    domain = (details.get("Domain") or "").lower()
    criterion = ""
    condition = ""

    df = load_df("Criterion")
    if not df.empty:
        df.columns = [c.strip() for c in df.columns]
        # safer mask with lowercasing and fillna
        left = df.iloc[:, 0].astype(str).str.lower().fillna("")
        right = df.iloc[:, 1].astype(str).str.lower().fillna("")
        mask = (left == domain) & (right == bloom.lower())
        if mask.any():
            row = df[mask].iloc[0]
            criterion = str(row.iloc[2]) if len(row) > 2 else ""
            condition = str(row.iloc[3]) if len(row) > 3 else ""

    # default fallback
    if not condition:
        condition = {
            "cognitive": "interpreting tasks",
            "affective": "engaging with peers",
            "psychomotor": "performing skills"
        }.get(domain, "")

    connector = "by" if domain == "psychomotor" else "when"
    condition_final = f"{connector} {condition}"

    return {
        "sc_code": details.get("SC_Code", ""),
        "sc_desc": details.get("SC_Desc", ""),
        "vbe": details.get("VBE", ""),
        "domain": domain,
        "criterion": criterion,
        "condition": condition_final
    }

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

    # ---------------------------------------
# META (criterion + condition) – correct
# ---------------------------------------
meta_res = get_meta_data(plo, bloom, profile)

condition_core = (
    meta_res.get("condition", "")
            .replace("when ", "")
            .replace("by ", "")
            .strip()
)

criterion = meta_res.get("criterion", "")

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


