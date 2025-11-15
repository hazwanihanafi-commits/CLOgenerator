# ======================================================
# SCLOG — CLEAN FINAL BACKEND (EXCEL + LOGIC EXPLANATIONS)
# ======================================================

import os
import json
from io import BytesIO
from datetime import datetime
from flask import (
    Flask, render_template, jsonify, request,
    send_file
)
import pandas as pd
from openpyxl import Workbook, load_workbook

# ------------------------------------------------------
# App setup
# ------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, "static"),
    template_folder=os.path.join(BASE_DIR, "templates")
)

WORKBOOK_PATH = os.path.join(BASE_DIR, "SCLOG.xlsx")
FRONT_JSON = os.path.join(app.static_folder, "data", "SCLOG_front.json")


# ------------------------------------------------------
# Safe JSON loader
# ------------------------------------------------------
def safe_load_json(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

MAP = safe_load_json(FRONT_JSON)

DEFAULT_KEYS = {
    "IEGs": [], "PEOs": [], "PLOs": [],
    "IEGtoPEO": {}, "PEOtoPLO": {},
    "PLOstatements": {}, "PEOstatements": {},
    "PLOtoVBE": {}, "PLOIndicators": {},
    "SCmapping": {}
}
for k, v in DEFAULT_KEYS.items():
    MAP.setdefault(k, v)


# ------------------------------------------------------
# Excel helpers
# ------------------------------------------------------
def load_df(sheet_name):
    if not os.path.exists(WORKBOOK_PATH):
        return pd.DataFrame()
    try:
        return pd.read_excel(WORKBOOK_PATH, sheet_name=sheet_name, engine="openpyxl")
    except:
        return pd.DataFrame()


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


def get_plo_details(plo, profile="sc"):
    df = get_mapping_sheet(profile)
    if df.empty:
        return None

    df.columns = [str(c).strip() for c in df.columns]
    col_plo = df.columns[0]
    mask = df[col_plo].astype(str).str.upper() == str(plo).upper()

    if not mask.any():
        return None

    row = df[mask].iloc[0]
    return {
        "SC_Code": row.get("SC Code", row.get("SCCode", "")),
        "SC_Desc": row.get("SC Description", row.get("SCDescription", "")),
        "VBE": row.get("VBE", ""),
        "Domain": row.get("Domain", "")
    }


# ------------------------------------------------------
# META (Criterion + Condition)
# ------------------------------------------------------
def get_meta_data(plo, bloom, profile="sc"):
    details = get_plo_details(plo, profile)
    if not details:
        return {}

    domain = (details.get("Domain") or "").lower()
    criterion = ""
    condition = ""

    df = load_df("Criterion")
    if not df.empty:
        df.columns = [c.strip() for c in df.columns]

        left = df.iloc[:,0].astype(str).str.lower()
        right = df.iloc[:,1].astype(str).str.lower()

        mask = (left == domain) & (right == str(bloom).lower())
        if mask.any():
            row = df[mask].iloc[0]
            if len(row) > 2:
                criterion = str(row.iloc[2])
            if len(row) > 3:
                condition = str(row.iloc[3])

    if not condition:
        defaults = {
            "cognitive": "interpreting tasks",
            "affective": "engaging with peers",
            "psychomotor": "performing skills"
        }
        condition = defaults.get(domain, "")

    connector = "by" if domain == "psychomotor" else "when"
    cond_final = f"{connector} {condition}"

    return {
        "sc_code": details["SC_Code"],
        "sc_desc": details["SC_Desc"],
        "vbe": details["VBE"],
        "domain": domain,
        "criterion": criterion,
        "condition": cond_final
    }


# ------------------------------------------------------
# Assessment / Evidence
# ------------------------------------------------------
def get_assessment(plo, bloom, domain):
    b = bloom.lower()
    d = domain.lower()

    cognitive = {
        "remember": ["MCQ","Recall quiz"],
        "understand": ["Short answer","Concept explanation"],
        "apply": ["Case study","Problem-solving"],
        "analyze": ["Data analysis","Critique"],
        "analyse": ["Data analysis","Critique"],
        "evaluate": ["Evaluation report"],
        "create": ["Design project","Proposal"]
    }

    affective = {
        "receive": ["Reflection log"],
        "respond": ["Participation","Peer feedback"],
        "value": ["Value essay"],
        "organization": ["Group portfolio"],
        "characterization": ["Professional behaviour assessment"]
    }

    psychomotor = {
        "perception": ["Observation"],
        "set": ["Preparation checklist"],
        "guided response": ["Guided task"],
        "mechanism": ["Skills test"],
        "complex overt response": ["OSCE"],
        "adaptation": ["Adapted task"],
        "origination": ["Capstone practical"]
    }

    if d == "affective": return affective.get(b, [])
    if d == "psychomotor": return psychomotor.get(b, [])
    return cognitive.get(b, [])


def get_evidence_for(assessment):
    a = assessment.lower()
    mapping = {
        "mcq": ["score report"],
        "quiz": ["quiz score"],
        "analysis": ["analysis sheet"],
        "critique": ["written critique"],
        "skills": ["skills checklist"],
        "osce": ["OSCE score sheet"],
        "reflection": ["reflection journal"]
    }
    for k,v in mapping.items():
        if k in a:
            return v
    return ["assessment evidence"]


# ------------------------------------------------------
# CONTENT suggestions
# ------------------------------------------------------
CONTENT_SUGGESTIONS = {
    "Computer Science": [
        "design software modules", "analyze data structures", "build machine learning models"
    ],
    "Medical & Health": [
        "interpret ECG", "analyze rehabilitation progress", "perform screenings"
    ],
    "Engineering": [
        "apply thermodynamics", "analyze structural loads"
    ],
    "Education": [
        "design lesson plans", "evaluate learning outcomes"
    ]
}

@app.route("/api/content/<field>")
def api_content(field):
    for k in CONTENT_SUGGESTIONS:
        if k.lower() == field.lower():
            return jsonify(CONTENT_SUGGESTIONS[k])
    return jsonify([])


# ------------------------------------------------------
# MAPPING endpoints (IEG → PEO → PLO)
# ------------------------------------------------------
@app.route("/api/mapping")
def api_mapping():
    return jsonify(MAP)

@app.route("/api/get_peos/<ieg>")
def api_get_peos(ieg):
    return jsonify(MAP["IEGtoPEO"].get(ieg, []))

@app.route("/api/get_plos/<peo>")
def api_get_plos(peo):
    return jsonify(MAP["PEOtoPLO"].get(peo, []))


# ------------------------------------------------------
# LOGIC explanations
# ------------------------------------------------------
@app.route("/api/logic/ieg_peo/<ieg>")
def logic_ieg_peo(ieg):
    explanation = {
        "IEG1": "IEG1 focuses on knowledge & critical thinking. PEO1 operationalises these outcomes.",
        "IEG2": "IEG2 emphasises ethics & professionalism. PEO2 aligns with these values.",
        "IEG3": "IEG3 promotes socio-entrepreneurship. PEO3 guides this development.",
        "IEG4": "IEG4 strengthens communication. PEO4 builds communication competence.",
        "IEG5": "IEG5 focuses on leadership & lifelong learning. PEO5 supports these traits."
    }
    return explanation.get(ieg, "No logic found."), 200, {"Content-Type": "text/plain"}


@app.route("/api/logic/peo_plo/<peo>/<plo>")
def logic_peo_plo(peo, plo):
    logic_map = {
        "PEO1": {
            "PLO1":"Knowledge → foundation for PEO1",
            "PLO2":"Critical thinking → supports PEO1",
            "PLO3":"Analysis ability → supports PEO1",
            "PLO6":"Real-world application → supports PEO1",
            "PLO7":"Problem-solving → supports PEO1"
        },
        "PEO2": {"PLO11":"Ethics & professionalism → supports PEO2"},
        "PEO3": {"PLO9":"Sustainability → supports PEO3","PLO10":"Societal wellbeing → supports PEO3"},
        "PEO4": {"PLO5":"Communication skills → supports PEO4"},
        "PEO5": {"PLO4":"Teamwork → supports PEO5","PLO8":"Leadership → supports PEO5","PLO9":"Global challenges → supports PEO5"}
    }
    return logic_map.get(peo, {}).get(plo, "No logic available."), 200, {"Content-Type":"text/plain"}


# ------------------------------------------------------
# BLOOM & VERB endpoints (Excel)
# ------------------------------------------------------
@app.route("/api/get_blooms/<plo>")
def api_get_blooms(plo):
    profile = request.args.get("profile","sc").lower()
    details = get_plo_details(plo, profile)
    if not details:
        return jsonify([])
    domain = details["Domain"].lower()

    sheet_map = {
        "cognitive":"Bloom_Cognitive",
        "affective":"Bloom_Affective",
        "psychomotor":"Bloom_Psychomotor"
    }
    df = load_df(sheet_map.get(domain,"Bloom_Cognitive"))
    if df.empty:
        return jsonify([])

    blooms = df.iloc[:,0].dropna().astype(str).tolist()
    return jsonify(blooms)


@app.route("/api/get_verbs/<plo>/<bloom>")
def api_get_verbs(plo, bloom):
    profile = request.args.get("profile","sc").lower()
    details = get_plo_details(plo, profile)
    if not details:
        return jsonify([])

    domain = details["Domain"].lower()
    sheet_map = {
        "cognitive":"Bloom_Cognitive",
        "affective":"Bloom_Affective",
        "psychomotor":"Bloom_Psychomotor"
    }

    df = load_df(sheet_map.get(domain,"Bloom_Cognitive"))
    if df.empty:
        return jsonify([])

    mask = df.iloc[:,0].astype(str).str.lower() == bloom.lower()
    if not mask.any():
        return jsonify([])

    raw = df[mask].iloc[0,1]
    verbs = [v.strip() for v in str(raw).split(",") if v.strip()]
    return jsonify(verbs)


# ------------------------------------------------------
# META endpoint
# ------------------------------------------------------
@app.route("/api/get_meta/<plo>/<bloom>")
def api_get_meta(plo, bloom):
    profile = request.args.get("profile","sc").lower()
    return jsonify(get_meta_data(plo, bloom, profile))


# ------------------------------------------------------
# STATEMENT endpoint
# ------------------------------------------------------
@app.route("/api/get_statement/<level>/<stype>/<code>")
def api_get_statement(level, stype, code):
    if stype == "PEO":
        return jsonify(MAP["PEOstatements"].get(level, {}).get(code, ""))
    if stype == "PLO":
        return jsonify(MAP["PLOstatements"].get(level, {}).get(code, ""))
    return jsonify("")


# ------------------------------------------------------
# GENERATE CLO
# ------------------------------------------------------
LAST_CLO = {}

@app.route("/generate", methods=["POST"])
def generate():
    profile = request.form.get("profile","sc")
    plo = request.form.get("plo","")
    bloom = request.form.get("bloom","")
    verb = request.form.get("verb","")
    content = request.form.get("content","")
    level = request.form.get("level","Degree")

    details = get_plo_details(plo, profile)
    if not details:
        return jsonify({"error":"Invalid PLO"}), 400

    domain = details["Domain"].lower()
    sc_desc = details["SC_Desc"]
    vbe = details["VBE"]

    meta = get_meta_data(plo, bloom, profile)
    condition_clean = meta["condition"].replace("when ","").replace("by ","")

    # Remove duplicated verb in content
    ACTIONS = {"explain","evaluate","analyze","analyse","apply","perform","design"}
    words = content.strip().lower().split()
    if words and words[0] in ACTIONS:
        content = " ".join(words[1:])

    connector = "when" if domain != "psychomotor" else "by"

    clo = (
        f"{verb.lower()} {content} using {sc_desc.lower()} "
        f"{connector} {condition_clean} guided by {vbe.lower()}."
    ).capitalize()

    variants = {
        "Standard": clo,
        "Critical Thinking": clo.replace("using","critically using"),
        "Short": f"{verb.capitalize()} {content}."
    }

    # find PEO + IEG
    peo = None
    for p,plos in MAP["PEOtoPLO"].items():
        if plo in plos:
            peo = p
            break

    ieg = None
    for i,peos in MAP["IEGtoPEO"].items():
        if peo in peos:
            ieg = i
            break

    last = {
        "clo": clo,
        "variants": variants,
        "plo": plo,
        "peo": peo,
        "ieg": ieg,
        "sc_code": details["SC_Code"],
        "sc_desc": details["SC_Desc"],
        "vbe": vbe,
        "domain": domain,
        "criterion": meta["criterion"],
        "condition": condition_clean,
        "plo_indicator": MAP["PLOIndicators"].get(plo,""),
        "plo_statement": MAP["PLOstatements"].get(level,{}).get(plo,""),
        "peo_statement": MAP["PEOstatements"].get(level,{}).get(peo,""),
        "assessments": get_assessment(plo, bloom, domain),
        "evidence": {},
    }

    # fill evidence
    for a in last["assessments"]:
        last["evidence"][a] = get_evidence_for(a)

    global LAST_CLO
    LAST_CLO = last

    return jsonify(last)


# ------------------------------------------------------
# DOWNLOADS
# ------------------------------------------------------
@app.route("/download")
def download_clo():
    if not LAST_CLO:
        return "No CLO generated", 400

    wb = Workbook()
    ws = wb.active
    ws.title = "CLO"

    ws.append(["Field","Value"])

    for key, val in LAST_CLO.items():
        if isinstance(val, dict):
            continue
        if isinstance(val, list):
            val = "; ".join(str(x) for x in val)
        ws.append([key, val])

    out = BytesIO()
    wb.save(out)
    out.seek(0)
    fname = f"CLO_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"

    return send_file(
        out,
        as_attachment=True,
        download_name=fname,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.route("/download_rubric")
def download_rubric():
    if not LAST_CLO:
        return "Generate CLO first", 400

    wb = Workbook()
    ws = wb.active
    ws.title = "Rubric"

    ws.append(["Component","Description"])
    ws.append(["Indicator", f"Ability to {LAST_CLO['clo']}"])
    ws.append(["Excellent","Performs at excellent level"])
    ws.append(["Good","Performs well"])
    ws.append(["Satisfactory","Meets minimum level"])
    ws.append(["Poor","Below expected"])

    out = BytesIO()
    wb.save(out)
    out.seek(0)
    fname = f"Rubric_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"

    return send_file(
        out, as_attachment=True,
        download_name=fname,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# ------------------------------------------------------
# UI
# ------------------------------------------------------
@app.route("/")
def index():
    return render_template("generator.html")


# ------------------------------------------------------
# RUN
# ------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")

