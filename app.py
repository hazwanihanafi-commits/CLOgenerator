# app.py — corrected, complete
import os
import json
from io import BytesIO
from datetime import datetime

from flask import Flask, render_template, request, jsonify, send_file
import pandas as pd
from openpyxl import Workbook, load_workbook

# ----------------------------------------
# PATH SETUP
# ----------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, "static"),
    template_folder=os.path.join(BASE_DIR, "templates")
)

WORKBOOK_PATH = os.path.join(BASE_DIR, "SCLOG.xlsx")
FRONT_JSON_PATH = os.path.join(app.static_folder, "data", "SCLOG_front.json")

print("BOOT: STATIC =", app.static_folder)
print("BOOT: TEMPLATES =", app.template_folder)
print("BOOT: WORKBOOK_PATH =", WORKBOOK_PATH)
print("BOOT: FRONT_JSON_PATH =", FRONT_JSON_PATH)


# ----------------------------------------
# Load mapping JSON safely
# ----------------------------------------
def safe_load_json(path):
    if not os.path.exists(path):
        app.logger.warning("JSON mapping not found: %s", path)
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        app.logger.exception("Failed to load JSON mapping %s: %s", path, e)
        return {}

MAP = safe_load_json(FRONT_JSON_PATH) or {}

# Ensure keys exist
DEFAULT_KEYS = {
    "IEGs": [], "PEOs": [], "PLOs": [],
    "IEGtoPEO": {}, "PEOtoPLO": {},
    "PLOstatements": {}, "PEOstatements": {},
    "PLOtoVBE": {}, "PLOIndicators": {}, "SCmapping": {}
}
for k, v in DEFAULT_KEYS.items():
    MAP.setdefault(k, v)

# ----------------------------------------
# Utility: safe Excel loader to pandas DataFrame
# ----------------------------------------
def load_df(sheet_name):
    """Return pandas DataFrame for sheet_name or empty DataFrame on failure."""
    if not os.path.exists(WORKBOOK_PATH):
        app.logger.warning("Workbook not found: %s", WORKBOOK_PATH)
        return pd.DataFrame()
    try:
        return pd.read_excel(WORKBOOK_PATH, sheet_name=sheet_name, engine="openpyxl")
    except Exception as e:
        app.logger.warning("Failed to read sheet '%s': %s", sheet_name, e)
        return pd.DataFrame()


# ----------------------------------------
# Profile -> mapping sheet names
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
    """Return mapping DataFrame for profile, fallback to generic 'Mapping'."""
    sheet = PROFILE_SHEET_MAP.get(profile, "Mapping")
    df = load_df(sheet)
    if df.empty:
        df = load_df("Mapping")
    return df


# ----------------------------------------
# PLO details from mapping sheet
# ----------------------------------------
def get_plo_details(plo, profile="sc"):
    if not plo:
        return None
    df = get_mapping_sheet(profile)
    if df.empty:
        return None
    df.columns = [str(c).strip() for c in df.columns]
    col_plo = df.columns[0]
    mask = df[col_plo].astype(str).str.upper().str.strip() == str(plo).strip().upper()
    if not mask.any():
        return None
    row = df[mask].iloc[0]
    return {
        "PLO": row.get(col_plo, plo),
        "SC_Code": row.get("SC Code", "") or row.get("SCCode", "") or "",
        "SC_Desc": row.get("SC Description", "") or row.get("SCDescription", "") or "",
        "VBE": row.get("VBE", "") or "",
        "Domain": row.get("Domain", "") or ""
    }


# ----------------------------------------
# get_meta_data helper (criterion + condition)
# ----------------------------------------
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
        # build mask safely
        left = df.iloc[:, 0].astype(str).str.lower().fillna("")
        right = df.iloc[:, 1].astype(str).str.lower().fillna("")
        mask = (left == domain) & (right == str(bloom).lower())
        if mask.any():
            row = df[mask].iloc[0]
            # guard for row length
            if len(row) >= 3: criterion = str(row.iloc[2])
            if len(row) >= 4: condition = str(row.iloc[3])
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


# ----------------------------------------
# Assessment & Evidence engine
# ----------------------------------------
def get_assessment(plo, bloom, domain):
    """
    Return a list of suggested assessment methods for a (plo, bloom, domain).
    This mapping is intentionally simple and can be extended.
    """
    if not bloom:
        return []

    b = bloom.lower().strip()
    d = (domain or "").lower().strip()

    # cognitive mapping (common bloom verbs/levels)
    cognitive = {
        "remember": ["MCQ", "Recall Quiz"],
        "understand": ["Short Answer Test", "Concept Explanation"],
        "apply": ["Case Study", "Problem-Solving Task"],
        "analyse": ["Data Analysis Task", "Critique Assignment"],
        "analyze": ["Data Analysis Task", "Critique Assignment"],
        "evaluate": ["Evaluation Report", "Evidence-Based Review"],
        "create": ["Design Project", "Research Proposal"]
    }

    psychomotor = {
        # placeholder labels — align with your Bloom sheet if uses different terms
        "perform": ["OSCE", "Skills Test", "Practical Exam"],
        "demonstrate": ["Skill Demonstration", "Checklist Assessment"]
    }

    affective = {
        "value": ["Reflection Log", "Value-Based Assignment"],
        "respond": ["Group Participation", "Peer Evaluation"],
        "receive": ["Observation Checklist"]
    }

    # Preference: domain-specific mapping
    if d == "psychomotor":
        # use psychomotor mapping if bloom matches key; fallback to general
        return psychomotor.get(b, ["OSCE", "Skills Test"])
    if d == "affective":
        return affective.get(b, ["Reflection Log", "Peer Evaluation"])
    return cognitive.get(b, ["Assignment", "Quiz"])


def get_evidence(assessment_method):
    """Return list of evidence items for a given assessment method (approximate)."""
    if not assessment_method:
        return []
    key = assessment_method.lower()
    evidence_map = {
        "mcq": ["Score report", "Automated grade output"],
        "recall quiz": ["Quiz score", "Answer log"],
        "short answer": ["Marked answers", "Marker rubric"],
        "case study": ["Case analysis rubric", "Annotated report"],
        "problem-solving": ["Solution sheet", "Reasoning steps"],
        "data analysis": ["Analysis report", "Code / spreadsheet"],
        "critique": ["Critique essay", "Evaluator comments"],
        "evaluation report": ["Evaluation sheet", "Analytical justification"],
        "design project": ["Project files", "Prototype", "Design documentation"],
        "research proposal": ["Proposal document", "Panel feedback"],
        "osce": ["OSCE checklist", "Examiner score sheet"],
        "skills test": ["Performance score", "Competency checklist"],
        "skill demonstration": ["Skills checklist", "Instructor feedback"],
        "reflection log": ["Reflection journal", "Instructor comments"],
        "portfolio": ["Portfolio files", "Growth documentation"],
        "group participation": ["Peer evaluation", "Participation log"],
    }
    # find best match
    for k, v in evidence_map.items():
        if k in key:
            return v
    # fallback
    return ["Performance evidence", "Rubric score"]


# ----------------------------------------
# Content suggestions mapping (for frontend)
# ----------------------------------------
CONTENT_SUGGESTIONS = {
  "Computer Science": [
    "debug algorithms", "design software modules", "analyze data structures",
    "implement machine learning models", "develop APIs"
  ],
  "Medical & Health": [
    "interpret ECG waveforms", "assess patient vital signs", "perform clinical screenings",
    "analyze medical imaging", "evaluate rehabilitation progress"
  ],
  "Engineering": [
    "apply thermodynamics principles", "analyze structural loads",
    "simulate mechanical systems", "perform quality testing"
  ],
  "Social Sciences": [
    "evaluate community case studies", "analyze social policy impact",
    "interpret behavioral data", "conduct needs assessments"
  ],
  "Education": [
    "design learning activities", "evaluate student performance",
    "develop curriculum materials", "apply instructional strategies"
  ],
  "Business": [
    "analyze market trends", "evaluate financial reports",
    "develop business strategies", "conduct SWOT analysis"
  ],
  "Arts & Humanities": [
    "interpret visual artworks", "analyze literary texts",
    "evaluate cultural narratives", "produce creative concepts"
  ]
}


# ----------------------------------------
# ROUTES: UI + APIs
# ----------------------------------------
@app.route("/")
def index():
    # Render your existing generator.html from templates
    return render_template("generator.html")


@app.route("/api/mapping")
def api_mapping():
    # Return the frontend JSON mapping (MAP)
    return jsonify(MAP)


@app.route("/api/get_peos/<ieg>")
def api_get_peos(ieg):
    return jsonify(MAP.get("IEGtoPEO", {}).get(ieg, []))


@app.route("/api/get_plos/<peo>")
def api_get_plos(peo):
    return jsonify(MAP.get("PEOtoPLO", {}).get(peo, []))


@app.route("/api/get_blooms/<plo>")
def api_get_blooms(plo):
    profile = request.args.get("profile", "sc").lower()
    details = get_plo_details(plo, profile)
    if not details:
        return jsonify([])
    domain = (details.get("Domain") or "").lower()
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


@app.route("/api/get_verbs/<plo>/<bloom>")
def api_get_verbs(plo, bloom):
    profile = request.args.get("profile", "sc").lower()
    details = get_plo_details(plo, profile)
    if not details:
        return jsonify([])
    domain = (details.get("Domain") or "").lower()
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
    # assume verbs are in second column as comma-separated
    verbs_cell = df[mask].iloc[0, 1]
    if pd.isna(verbs_cell):
        return jsonify([])
    verbs = [v.strip() for v in str(verbs_cell).split(",") if v.strip()]
    return jsonify(verbs)


@app.route("/api/get_meta/<plo>/<bloom>")
def api_get_meta(plo, bloom):
    profile = request.args.get("profile", "sc").lower()
    return jsonify(get_meta_data(plo, bloom, profile))


@app.route("/api/get_statement/<level>/<stype>/<code>")
def api_get_statement(level, stype, code):
    # level: Diploma/Degree/Master/PhD ; stype: PEO or PLO ; code: e.g., PLO1
    stype = (stype or "").upper()
    level = level if level in MAP.get("PLOstatements", {}) else "Degree"
    if stype == "PEO":
        return jsonify(MAP.get("PEOstatements", {}).get(level, {}).get(code, ""))
    if stype == "PLO":
        return jsonify(MAP.get("PLOstatements", {}).get(level, {}).get(code, ""))
    return jsonify("")


@app.route("/api/content_suggestions/<field>")
def api_content_suggestions(field):
    # return suggestions for frontend content input
    return jsonify(CONTENT_SUGGESTIONS.get(field, []))


# ----------------------------------------
# GENERATE CLO
# ----------------------------------------
# We'll keep a simple in-memory storage for the last generated CLO to support downloads
LAST_CLO_DATA = {}

@app.route("/generate", methods=["POST"])
def generate():
    profile = (request.form.get("profile") or "sc").lower()
    plo = (request.form.get("plo") or "").strip()
    bloom = (request.form.get("bloom") or "").strip()
    verb = (request.form.get("verb") or "").strip()
    content = (request.form.get("content") or "").strip()
    level = (request.form.get("level") or "Degree").strip()

    if not plo or not bloom or not verb or not content:
        return jsonify({"error": "Please provide plo, bloom, verb and content"}), 400

    details = get_plo_details(plo, profile)
    if not details:
        return jsonify({"error": f"PLO '{plo}' not found for profile '{profile}'"}), 400

    sc_desc = details.get("SC_Desc", "")
    vbe = details.get("VBE", "")
    domain = (details.get("Domain") or "").lower()

    # meta
    meta_res = get_meta_data(plo, bloom, profile) or {}
    raw_condition = meta_res.get("condition", "")
    condition_core = raw_condition.replace("when ", "").replace("by ", "").strip()
    criterion = meta_res.get("criterion", "")

    connector = "by" if domain == "psychomotor" else "when"

    # build CLO sentence (simple, robust)
    clo = (
        f"{verb.lower()} {content} using {sc_desc.lower()} "
        f"{connector} {condition_core} guided by {vbe.lower()}."
    ).capitalize()

    # Generate variants
    variants = {
        "Standard": clo,
        "Critical Thinking": clo.replace("using", "critically using"),
        "Problem-Solving": clo.replace("using", "by applying structured problem-solving approaches to"),
        "Action-Oriented": clo.replace("when", "while"),
        "Professional Practice": clo.replace("guided by", "in accordance with"),
    }

    # find PEO & IEG from MAP
    peo = None
    ieg = None
    for p, plos in MAP.get("PEOtoPLO", {}).items():
        if plo in plos:
            peo = p
            break
    for i, peos in MAP.get("IEGtoPEO", {}).items():
        if peo and peo in peos:
            ieg = i
            break

    # statements
    plo_statement = MAP.get("PLOstatements", {}).get(level, {}).get(plo, "")
    peo_statement = MAP.get("PEOstatements", {}).get(level, {}).get(peo, "")

    # Assessment and evidence
    assessments = get_assessment(plo, bloom, domain) or []
    evidence_accum = []
    for a in assessments:
        ev = get_evidence(a) or []
        for e in ev:
            if e not in evidence_accum:
                evidence_accum.append(e)

    # Rubric (basic auto-gen)
    rubric = {
        "indicator": f"Ability to {verb.lower()} {sc_desc.lower()} { 'when ' + condition_core if connector=='when' else 'by ' + condition_core } in accordance with {vbe.lower()}",
        "excellent": f"Consistently demonstrates {vbe.lower()} and applies {sc_desc.lower()} {connector} {condition_core} with high accuracy and clarity.",
        "good": f"Generally demonstrates {vbe.lower()} and applies {sc_desc.lower()} {connector} {condition_core} with minor gaps.",
        "satisfactory": f"Partially demonstrates {vbe.lower()}; applies {sc_desc.lower()} {connector} {condition_core} inconsistently.",
        "poor": f"Does not demonstrate {vbe.lower()}; unable to apply {sc_desc.lower()} {connector} {condition_core} effectively."
    }

    # Save last generated data for downloads
    global LAST_CLO_DATA
    LAST_CLO_DATA = {
        "generated_at": datetime.now().isoformat(timespec="minutes"),
        "clo": clo,
        "clo_options": variants,
        "plo": plo,
        "peo": peo,
        "ieg": ieg,
        "plo_statement": plo_statement,
        "peo_statement": peo_statement,
        "sc_code": details.get("SC_Code", ""),
        "sc_desc": sc_desc,
        "vbe": vbe,
        "domain": domain,
        "criterion": criterion,
        "condition": condition_core,
        "assessment": assessments,
        "evidence": evidence_accum,
        "rubric": rubric
    }

    return jsonify({
        "clo": clo,
        "clo_options": variants,
        "sc_code": details.get("SC_Code", ""),
        "sc_desc": sc_desc,
        "vbe": vbe,
        "domain": domain,
        "criterion": criterion,
        "condition": condition_core,
        "ieg": ieg,
        "peo": peo,
        "plo_statement": plo_statement,
        "peo_statement": peo_statement,
        "assessment": assessments,
        "evidence": evidence_accum,
        "rubric": rubric
    })


# ----------------------------------------
# Download endpoints (use LAST_CLO_DATA)
# ----------------------------------------
@app.route("/download")
def download_clo():
    global LAST_CLO_DATA
    if not LAST_CLO_DATA:
        return "No CLO available. Generate a CLO first.", 400

    data = LAST_CLO_DATA

    wb = Workbook()
    ws = wb.active
    ws.title = "CLO"

    ws.append(["Field", "Value"])
    ws.append(["Generated At", data.get("generated_at", "")])
    ws.append(["CLO", data.get("clo", "")])
    ws.append(["PLO", data.get("plo", "")])
    ws.append(["PLO Statement", data.get("plo_statement", "")])
    ws.append(["PEO", data.get("peo", "")])
    ws.append(["PEO Statement", data.get("peo_statement", "")])
    ws.append(["IEG", data.get("ieg", "")])
    ws.append(["SC Code", data.get("sc_code", "")])
    ws.append(["SC Description", data.get("sc_desc", "")])
    ws.append(["VBE", data.get("vbe", "")])
    ws.append(["Domain", data.get("domain", "")])
    ws.append(["Criterion", data.get("criterion", "")])
    ws.append(["Condition", data.get("condition", "")])

    ws.append([])
    ws.append(["Assessment Methods"])
    for a in data.get("assessment", []):
        ws.append([a])
    ws.append([])
    ws.append(["Evidence (measures)"])
    for e in data.get("evidence", []):
        ws.append([e])

    ws.append([])
    ws.append(["Rubric Indicator", data["rubric"].get("indicator", "")])
    ws.append(["Excellent", data["rubric"].get("excellent", "")])
    ws.append(["Good", data["rubric"].get("good", "")])
    ws.append(["Satisfactory", data["rubric"].get("satisfactory", "")])
    ws.append(["Poor", data["rubric"].get("poor", "")])

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"CLO_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.route("/download_rubric")
def download_rubric():
    global LAST_CLO_DATA
    if not LAST_CLO_DATA:
        return "No rubric available. Generate a CLO first.", 400

    data = LAST_CLO_DATA
    wb = Workbook()
    ws = wb.active
    ws.title = "Rubric"

    ws.append(["Rubric Component", "Description"])
    ws.append(["Indicator", data["rubric"].get("indicator", "")])
    ws.append(["Excellent", data["rubric"].get("excellent", "")])
    ws.append(["Good", data["rubric"].get("good", "")])
    ws.append(["Satisfactory", data["rubric"].get("satisfactory", "")])
    ws.append(["Poor", data["rubric"].get("poor", "")])

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"Rubric_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# ----------------------------------------
# Run
# ----------------------------------------
if __name__ == "__main__":
    # For local debug
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
