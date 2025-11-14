import pandas as pd
import os
import json
from flask import Flask, render_template, request, jsonify, send_file
from openpyxl import Workbook, load_workbook
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
        print("WARN: JSON file not found:", path)
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("JSON LOAD ERROR:", e)
        return {}

# Load mapping JSON (front-end friendly)
MAP = safe_load_json(FRONT_JSON)
DEFAULT_KEYS = {
    "IEGs": [], "PEOs": [], "PLOs": [],
    "IEGtoPEO": {}, "PEOtoPLO": {},
    "PLOstatements": {}, "PEOstatements": {},
    "PLOtoVBE": {}, "PLOIndicators": {}, "SCmapping": {}
}
for k, v in DEFAULT_KEYS.items():
    if k not in MAP:
        MAP[k] = v

print("BOOT: mapping counts -> IEGs:", len(MAP.get("IEGs", [])),
      "PEOs:", len(MAP.get("PEOs", [])),
      "PLOs:", len(MAP.get("PLOs", [])))

# ----------------------------------------
# SIMPLE CONTENT SUGGESTIONS (frontend keeps same list)
# ----------------------------------------
FIELD_CONTENT_MAP = {
    "Computer Science": [
        "debug algorithms", "design software modules",
        "analyze data structures", "implement machine learning models",
        "develop RESTful APIs"
    ],
    "Medical & Health": [
        "interpret ECG waveforms", "assess patient vital signs",
        "perform clinical screenings", "analyze medical imaging",
        "evaluate rehabilitation progress"
    ],
    "Engineering": [
        "apply thermodynamics principles", "analyze structural loads",
        "simulate mechanical systems", "perform quality testing",
        "design basic prototypes"
    ],
    "Social Sciences": [
        "evaluate community case studies", "analyze social policy impact",
        "interpret behavioral data", "conduct needs assessments",
        "design surveys"
    ],
    "Education": [
        "design learning activities", "evaluate student performance",
        "develop curriculum materials", "apply instructional strategies",
        "design assessment rubrics"
    ],
    "Business": [
        "analyze market trends", "evaluate financial reports",
        "develop business strategies", "conduct SWOT analysis",
        "build simple financial models"
    ],
    "Arts & Humanities": [
        "interpret visual artworks", "analyze literary texts",
        "evaluate cultural narratives", "produce creative concepts",
        "write reflective critiques"
    ]
}

# ----------------------------------------
# EXCEL SAFE LOADER
# ----------------------------------------
def load_df(sheet_name: str):
    if not os.path.exists(WORKBOOK_PATH):
        # silent fallback if workbook not present in deployment
        return pd.DataFrame()
    try:
        return pd.read_excel(WORKBOOK_PATH, sheet_name=sheet_name, engine="openpyxl")
    except Exception:
        return pd.DataFrame()

# ----------------------------------------
# PROFILE → MAPPING sheet names
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

def get_plo_details(plo, profile="sc"):
    df = get_mapping_sheet(profile)
    if df.empty:
        return None
    df.columns = [str(c).strip() for c in df.columns]
    col_plo = df.columns[0]
    row = df[df[col_plo].astype(str).str.upper() == str(plo).upper()]
    if row.empty:
        return None
    r = row.iloc[0]
    return {
        "SC_Code": r.get("SC Code", "") or r.get("SCCode", ""),
        "SC_Desc": r.get("SC Description", "") or r.get("SC Description".strip(), ""),
        "VBE": r.get("VBE", ""),
        "Domain": r.get("Domain", "")
    }

# ----------------------------------------
# META retrieval (criterion + condition)
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
        left = df.iloc[:, 0].astype(str).str.lower().fillna("")
        right = df.iloc[:, 1].astype(str).str.lower().fillna("")
        mask = (left == domain) & (right == bloom.lower())
        if mask.any():
            row = df[mask].iloc[0]
            criterion = str(row.iloc[2]) if len(row) > 2 else ""
            condition = str(row.iloc[3]) if len(row) > 3 else ""
    if not condition:
        condition = {
            "cognitive": "interpreting tasks",
            "affective": "engaging with peers",
            "psychomotor": "performing practical skills"
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
# ASSESSMENT & EVIDENCE ENGINE
# ----------------------------------------
def get_assessments_and_evidence(bloom, domain):
    """
    Returns list of (assessment_method, evidence_list) appropriate for bloom/domain.
    """
    elm_assess = []
    domain = (domain or "").lower()
    bloom_k = (bloom or "").lower()

    # cognitive examples (map a few common blooms)
    cognitive_map = {
        "remember": ("MCQ / Quiz", ["Score report", "Item analysis"]),
        "understand": ("Short answer / Explanation", ["Answers", "Marker rubric"]),
        "apply": ("Case study / Problem-solving", ["Case report", "Rubric"]),
        "analyze": ("Data analysis task", ["Analysis file", "Evaluator notes"]),
        "evaluate": ("Evidence-based critique", ["Report", "Assessment rubric"]),
        "create": ("Design / Project", ["Project deliverables", "Prototype", "Rubric"])
    }

    psychomotor_map = {
        "skill": ("OSCE / Skills test", ["OSCE checklist", "Examiner score sheet"]),
        "demonstrate": ("Practical demonstration", ["Skills checklist", "Instructor feedback"])
    }

    affective_map = {
        "receive": ("Observation / Participation", ["Attendance log", "Peer feedback"]),
        "respond": ("Reflection / Group work", ["Reflection journal", "Peer review"]),
        "value": ("Portfolio / Reflection", ["Portfolio", "Supervisor notes"])
    }

    if domain == "psychomotor":
        # try lookup by bloom keywords
        if "perform" in bloom_k or "demonstr" in bloom_k or "skill" in bloom_k:
            return [psychomotor_map["skill"]]
        return [psychomotor_map["demonstrate"]]

    if domain == "affective":
        if "value" in bloom_k:
            return [affective_map["value"]]
        if "respond" in bloom_k:
            return [affective_map["respond"]]
        return [affective_map["receive"]]

    # cognitive fallback: try direct lookup
    for key in cognitive_map:
        if key in bloom_k:
            elm_assess.append(cognitive_map[key])
            break
    if not elm_assess:
        # generic
        elm_assess.append(("Assignment / Test", ["Submission file", "Grading rubric"]))
    return elm_assess

# ----------------------------------------
# API Endpoints
# ----------------------------------------
@app.route("/")
def index():
    return render_template("generator.html")

@app.route("/api/mapping")
def api_mapping():
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
    verbs = [v.strip() for v in str(df[mask].iloc[0, 1]).split(",") if v.strip()]
    return jsonify(verbs)

@app.route("/api/get_meta/<plo>/<bloom>")
def api_get_meta(plo, bloom):
    profile = request.args.get("profile", "sc").lower()
    return jsonify(get_meta_data(plo, bloom, profile))

@app.route("/api/content/<field>")
def api_content(field):
    # field URL may come as "Medical%20%26%20Health"; decode loosely by replacing '_' or '%20'
    name = field.replace("_", " ").replace("%20", " ")
    # tolerant match
    for key in FIELD_CONTENT_MAP:
        if key.lower().startswith(name.lower()) or name.lower().startswith(key.lower()):
            return jsonify(FIELD_CONTENT_MAP[key])
    # fallback empty list
    return jsonify(FIELD_CONTENT_MAP.get(name, []))

@app.route("/api/get_statement/<level>/<stype>/<code>")
def api_get_statement(level, stype, code):
    stype = stype.upper()
    if stype == "PEO":
        return jsonify(MAP.get("PEOstatements", {}).get(level, {}).get(code, ""))
    if stype == "PLO":
        return jsonify(MAP.get("PLOstatements", {}).get(level, {}).get(code, ""))
    return jsonify("")

# ----------------------------------------
# CLO GENERATION
# ----------------------------------------
LAST_CLO_DATA = {}

@app.route("/generate", methods=["POST"])
def generate():
    global LAST_CLO_DATA
    profile = (request.form.get("profile") or "sc").lower()
    plo = (request.form.get("plo") or "").strip()
    bloom = (request.form.get("bloom") or "").strip()
    verb = (request.form.get("verb") or "").strip()
    content = (request.form.get("content") or "").strip()
    field = (request.form.get("field") or "").strip()
    level = (request.form.get("level") or "Degree").strip()

    if not plo or not bloom or not verb:
        return jsonify({"error": "Missing required fields (plo, bloom, verb)"}), 400

    details = get_plo_details(plo, profile)
    if not details:
        return jsonify({"error": f"PLO '{plo}' not found for profile '{profile}'"}), 400

    domain = (details.get("Domain") or "").lower()
    sc_desc = details.get("SC_Desc") or ""
    vbe = details.get("VBE") or ""

    # If content empty, pick suggested content based on 'field' if available
    if not content:
        if field and field in FIELD_CONTENT_MAP and FIELD_CONTENT_MAP[field]:
            content = FIELD_CONTENT_MAP[field][0]
        else:
            # pick a generic suggestion from mapping or PLO text
            content = MAP.get("PLOs", [plo])[0] if plo else "task"

    # Meta (criterion + condition)
    meta = get_meta_data(plo, bloom, profile)
    condition_core = meta.get("condition", "").replace("when ", "").replace("by ", "").strip()
    criterion = meta.get("criterion", "")

    connector = "by" if domain == "psychomotor" else "when"

    # Construct CLO sentence (simple template used here)
    clo = f"{verb.lower()} {content} using {sc_desc.lower()} {connector} {condition_core} guided by {vbe.lower()}."
    if not clo.endswith("."):
        clo = clo + "."
    clo = clo.capitalize()

    # Variants
    variants = {
        "Standard": clo,
        "Critical Thinking": clo.replace("using", "critically using"),
        "Problem-Solving": clo.replace("using", "by applying structured problem-solving approaches to"),
        "Action-Oriented": clo.replace("when", "while"),
        "Professional Practice": clo + " (apply professional practice)",
        "Ethical Emphasis": clo + " (consider ethical implications)"
    }

    # auto chain: peo, ieg
    peo_selected = None
    ieg_selected = None
    for p, plos in MAP.get("PEOtoPLO", {}).items():
        if plo in plos:
            peo_selected = p
            break
    if peo_selected:
        for i, peos in MAP.get("IEGtoPEO", {}).items():
            if peo_selected in peos:
                ieg_selected = i
                break

    plo_statement = MAP.get("PLOstatements", {}).get(level, {}).get(plo, "")
    peo_statement = MAP.get("PEOstatements", {}).get(level, {}).get(peo_selected, "")

    # assessment & evidence suggestions
    assessments = get_assessments_and_evidence(bloom, domain)
    # build human friendly list
    assessment_out = []
    for a, evid in assessments:
        assessment_out.append({"assessment": a, "evidence": evid})

    # rubric (basic)
    rubric = {
        "indicator": f"Ability to {verb.lower()} {sc_desc.lower()} {connector} {condition_core}",
        "excellent": f"Consistently demonstrates {vbe.lower()} and applies {sc_desc.lower()} {connector} {condition_core} with high accuracy.",
        "good": f"Generally demonstrates {vbe.lower()} and applies {sc_desc.lower()} {connector} {condition_core} with minor gaps.",
        "satisfactory": f"Partially demonstrates {vbe.lower()}; applies {sc_desc.lower()} {connector} {condition_core} inconsistently.",
        "poor": f"Does not demonstrate {vbe.lower()}; unable to apply {sc_desc.lower()} {connector} {condition_core} effectively."
    }

    # save last generated CLO data for downloads
    LAST_CLO_DATA = {
        "clo": clo,
        "plo": plo,
        "peo": peo_selected,
        "ieg": ieg_selected,
        "plo_statement": plo_statement,
        "peo_statement": peo_statement,
        "sc_code": details.get("SC_Code", ""),
        "sc_desc": sc_desc,
        "vbe": vbe,
        "domain": domain,
        "criterion": criterion,
        "condition": condition_core,
        "assessments": assessment_out,
        "rubric": rubric,
        "generated_at": datetime.now().isoformat()
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
        "ieg": ieg_selected,
        "peo": peo_selected,
        "plo_statement": plo_statement,
        "peo_statement": peo_statement,
        "assessments": assessment_out,
        "rubric": rubric
    })

# ----------------------------------------
# DOWNLOADS
# ----------------------------------------
@app.route("/download")
def download_clo():
    global LAST_CLO_DATA
    if not LAST_CLO_DATA:
        return "No CLO available. Please generate first.", 400

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
    ws.append(["Assessments & Evidence"])
    for a in data.get("assessments", []):
        ws.append([a.get("assessment"), ", ".join(a.get("evidence", []))])
    ws.append([])
    ws.append(["Rubric Indicator", data["rubric"]["indicator"]])
    ws.append(["Excellent", data["rubric"]["excellent"]])
    ws.append(["Good", data["rubric"]["good"]])
    ws.append(["Satisfactory", data["rubric"]["satisfactory"]])
    ws.append(["Poor", data["rubric"]["poor"]])

    out = BytesIO()
    wb.save(out)
    out.seek(0)
    filename = f"CLO_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return send_file(out, as_attachment=True, download_name=filename,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.route("/download_rubric")
def download_rubric():
    global LAST_CLO_DATA
    if not LAST_CLO_DATA:
        return "No Rubric available. Please generate first.", 400
    data = LAST_CLO_DATA
    wb = Workbook()
    ws = wb.active
    ws.title = "Rubric"
    ws.append(["Rubric Component", "Description"])
    ws.append(["Indicator", data["rubric"]["indicator"]])
    ws.append(["Excellent", data["rubric"]["excellent"]])
    ws.append(["Good", data["rubric"]["good"]])
    ws.append(["Satisfactory", data["rubric"]["satisfactory"]])
    ws.append(["Poor", data["rubric"]["poor"]])
    out = BytesIO()
    wb.save(out)
    out.seek(0)
    filename = f"Rubric_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return send_file(out, as_attachment=True, download_name=filename,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ----------------------------------------
# RUN
# ----------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
