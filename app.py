# app.py - cleaned & integrated (paste into your project)
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

print("STATIC =", app.static_folder)
print("TEMPLATES =", app.template_folder)

WORKBOOK_PATH = os.path.join(os.getcwd(), "SCLOG.xlsx")
JSON_PATH = os.path.join(app.static_folder, "data", "peo_plo_ieg.json")

# Load IEG–PEO–PLO JSON mapping if present
if os.path.exists(JSON_PATH):
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        IEP = json.load(f)
else:
    IEP = {
        "IEGs": [], "PEOs": [], "PLOs": [],
        "IEGtoPEO": {}, "PEOtoPLO": {},
        "PLOstatements": {}, "PEOstatements": {},
        "PLOtoVBE": {}, "PLOIndicators": {}, "SCmapping": {}
    }

# ----------------------
# ONE-WORD META & MAPPINGS
# ----------------------
ONEWORD_META = {
    "cognitive": {
        "Remember":   {"criterion": "accurately",     "condition": "recalling information"},
        "Understand": {"criterion": "coherently",     "condition": "explaining concepts"},
        "Apply":      {"criterion": "effectively",    "condition": "applying methods"},
        "Analyze":    {"criterion": "critically",     "condition": "analyzing task requirements"},
        "Evaluate":   {"criterion": "independently",  "condition": "making judgments"},
        "Create":     {"criterion": "innovatively",   "condition": "generating ideas"}
    },
    "affective": {
        "Receive":          {"criterion": "openly",          "condition": "engaging respectfully"},
        "Respond":          {"criterion": "responsibly",     "condition": "participating actively"},
        "Value":            {"criterion": "sincerely",       "condition": "demonstrating values"},
        "Organization":     {"criterion": "constructively",  "condition": "balancing perspectives"},
        "Characterization": {"criterion": "ethically",       "condition": "behaving professionally"}
    },
    "psychomotor": {
        "Perception":             {"criterion": "accurately",    "condition": "identifying task cues"},
        "Set":                    {"criterion": "precisely",     "condition": "preparing required actions"},
        "Guided Response":        {"criterion": "under guidance","condition": "practising foundational skills"},
        "Mechanism":              {"criterion": "competently",   "condition": "performing routine skills"},
        "Complex Overt Response": {"criterion": "efficiently",   "condition": "executing complex tasks"},
        "Adaptation":             {"criterion": "safely",        "condition": "adjusting performance to context"},
        "Origination":            {"criterion": "creatively",    "condition": "developing new techniques"}
    }
}

PROFILE_SHEET_MAP = {
    "health": "Mapping_health",
    "sc": "Mapping_sc",
    "eng": "Mapping_eng",
    "socs": "Mapping_socs",
    "edu": "Mapping_edu",
    "bus": "Mapping_bus",
    "arts": "Mapping_arts"
}

VBE_CRITERION = {
    "Ethics and Professionalism": "Guided by ethics and professionalism",
    "Professional practice standards": "Aligned with professional practice standards",
    "Integrity": "Demonstrating integrity in judgement",
    "Ethics and Etiquette": "Guided by ethical and professional etiquette",
    "Professionalism and Teamwork": "Demonstrating professionalism and effective teamwork",
    "Professionalism and Well-being": "Upholding professionalism and personal well-being",
    "Honesty and Integrity": "Guided by honesty and integrity",
    "Professional conduct": "Demonstrating responsible and professional conduct"
}

SC_FULLNAME = {
    "SC1": "Apply ethics professionally",
    "SC2": "Work collaboratively in teams",
    "SC3": "Communicate effectively",
    "SC4": "Critical and analytical thinking",
    "SC5": "Problem-solving and decision-making",
    "SC6": "Digital and information literacy",
    "SC7": "Leadership and responsibility",
    "SC8": "Lifelong learning capability"
}

VBE_FULLNAME = {
    "Ethics and Etiquette": "Ethical and professional conduct",
    "Integrity": "Integrity and trustworthiness",
    "Respect": "Mutual respect and inclusivity",
    "Professionalism": "Professional behaviour and accountability"
}

# ============================================================
# EXCEL HELPERS (safe)
# ============================================================
def load_sheet_df(sheet_name: str):
    try:
        return pd.read_excel(WORKBOOK_PATH, sheet_name=sheet_name, engine="openpyxl")
    except Exception:
        return pd.DataFrame()

def read_clo_table():
    try:
        return pd.read_excel(WORKBOOK_PATH, sheet_name="CLO_Table", engine="openpyxl")
    except Exception:
        return pd.DataFrame()

def write_clo_table(df):
    # Create workbook if not exists
    if not os.path.exists(WORKBOOK_PATH):
        with pd.ExcelWriter(WORKBOOK_PATH, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name="CLO_Table")
        return

    # Try to replace CLO_Table sheet safely
    try:
        book = load_workbook(WORKBOOK_PATH)
        if "CLO_Table" in book.sheetnames:
            del book["CLO_Table"]
        with pd.ExcelWriter(WORKBOOK_PATH, mode="a", engine="openpyxl") as w:
            w._book = book
            df.to_excel(w, index=False, sheet_name="CLO_Table")
    except Exception:
        # fallback: overwrite whole file
        with pd.ExcelWriter(WORKBOOK_PATH, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name="CLO_Table")

# ============================================================
# MAPPING HELPERS
# ============================================================
def get_mapping_dict(profile):
    sheet = PROFILE_SHEET_MAP.get(profile, "Mapping")
    df = load_sheet_df(sheet)
    if df.empty:
        return pd.DataFrame()
    df.columns = [str(c).strip() for c in df.columns]
    return df

def get_plo_details(plo, profile):
    df = get_mapping_dict(profile)
    if df.empty:
        return None

    colmap = {c.strip().lower().replace(" ", ""): c for c in df.columns}
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
        "SC_Code": row.get(col_sc, ""),
        "SC_Desc": row.get(col_desc, ""),
        "VBE": row.get(col_vbe, ""),
        "Domain": row.get(col_domain, "")
    }

# ============================================================
# CRITERION + CONDITION, ASSESSMENT
# ============================================================
def get_criterion_phrase(domain, bloom):
    df = load_sheet_df("Criterion")
    if df.empty:
        return "", ""
    df.columns = [c.strip() for c in df.columns]
    dom_col, bloom_col, crit_col, cond_col = df.columns[:4]
    mask = (
        (df[dom_col].astype(str).str.lower() == domain.lower()) &
        (df[bloom_col].astype(str).str.lower() == bloom.lower())
    )
    if not mask.any():
        return "", ""
    row = df[mask].iloc[0]
    return str(row[crit_col]).strip(), str(row[cond_col]).strip()

def get_default_condition(domain):
    return {
        "cognitive": "interpreting case tasks",
        "affective": "engaging with peers or stakeholders",
        "psychomotor": "executing practical procedures"
    }.get(domain, "")

def get_assessment_and_evidence(bloom, domain):
    sheet = "Assess_Affective_Psychomotor" if domain in ("affective","psychomotor") else "Bloom_Assessments"
    df = load_sheet_df(sheet)
    if df.empty:
        return "", ""
    df.columns = [c.strip() for c in df.columns]
    bloom_col, assess_col, evid_col = df.columns[:3]
    mask = df[bloom_col].astype(str).str.lower() == bloom.lower()
    if not mask.any():
        return "", ""
    row = df[mask].iloc[0]
    return row[assess_col], row[evid_col]

# ============================================================
# CLO CONSTRUCTION & RUBRIC
# ============================================================
def decide_connector(domain):
    return "by" if domain == "psychomotor" else "when"

def sc_snippet(sc_desc):
    if not sc_desc:
        return ""
    desc = sc_desc.lower().strip()
    return desc if desc.startswith("using ") else f"using {desc}"

def vbe_phrase(vbe, style):
    if not vbe:
        return ""
    vbe = vbe.lower()
    style = style.lower()
    if style == "accordance":
        return f"in accordance with {vbe}"
    if style == "aligned":
        return f"aligned with {vbe}"
    return f"guided by {vbe}"

def construct_clo_sentence(verb, content, sc_desc, condition_core, criterion, vbe, domain, vbe_style="guided"):
    verb = (verb or "").lower().strip()
    content = (content or "").strip()
    condition_core = (condition_core or "").strip()
    criterion_clean = (criterion or "").lower().strip()

    # remove leading "when/by"
    for lead in ("when ", "by "):
        if condition_core.lower().startswith(lead):
            condition_core = condition_core[len(lead):].strip()
            break

    condition = f"{decide_connector(domain)} {condition_core}" if condition_core else ""

    has_vbe_in_criterion = criterion_clean.startswith((
        "guided by",
        "aligned with",
        "in accordance with",
        "grounded in"
    ))

    if has_vbe_in_criterion:
        parts = [
            f"{verb} {content}",
            sc_snippet(sc_desc),
            condition,
            criterion
        ]
    else:
        parts = [
            f"{verb} {content}",
            sc_snippet(sc_desc),
            condition,
            criterion,
            vbe_phrase(vbe, vbe_style)
        ]

    s = " ".join(p for p in parts if p).strip()
    if not s.endswith("."):
        s += "."
    return s.capitalize()

def rubric_generator(clo, verb, criterion, condition_core, sc_desc, vbe):
    verb_l = (verb or "").lower().strip()
    sc_l = sc_desc.lower().strip() if sc_desc else ""
    vbe_l = (vbe or "").lower().strip()
    cond = (condition_core or "").strip()

    if not cond.startswith(("when ", "by ")):
        connector = "by" if "perform" in (clo or "").lower() else "when"
        cond = f"{connector} {cond}"

    indicator = (
        f"Ability to {verb_l} {sc_l} {cond} in accordance with {vbe_l}."
    )

    excellent = (
        f"Consistently demonstrates {vbe_l} and applies {sc_l} {cond} with high accuracy and clarity."
    )
    good = (
        f"Generally demonstrates {vbe_l} and applies {sc_l} {cond} with minor gaps in clarity or consistency."
    )
    satisfactory = (
        f"Partially demonstrates {vbe_l}; applies {sc_l} {cond} inconsistently."
    )
    poor = (
        f"Does not demonstrate {vbe_l}; unable to apply {sc_l} {cond} effectively."
    )

    return {
        "indicator": indicator,
        "excellent": excellent,
        "good": good,
        "satisfactory": satisfactory,
        "poor": poor
    }

# ============================================================
# ROUTES - UI & APIs
# ============================================================
@app.route("/")
def index():
    profile = request.args.get("profile", "health")
    # load PLO list from JSON if available
    plos = IEP.get("PLOs", [])
    return render_template("generator.html", plos=plos, profile=profile)

# API: blooms (unchanged)
@app.route("/api/get_blooms/<plo>")
def api_get_blooms(plo):
    profile = request.args.get("profile", "").strip().lower()
    details = get_plo_details(plo, profile)
    if not details:
        return jsonify([])
    domain = (details["Domain"] or "").lower()
    sheetmap = {
        "cognitive": "Bloom_Cognitive",
        "affective": "Bloom_Affective",
        "psychomotor": "Bloom_Psychomotor"
    }
    df = load_sheet_df(sheetmap.get(domain, "Bloom_Cognitive"))
    if df.empty:
        return jsonify([])
    blooms = df.iloc[:, 0].dropna().astype(str).tolist()
    return jsonify(blooms)

# API: verbs (unchanged)
@app.route("/api/get_verbs/<plo>/<bloom>")
def api_get_verbs(plo, bloom):
    profile = request.args.get("profile", "").strip().lower()
    details = get_plo_details(plo, profile)
    if not details:
        return jsonify([])
    domain = (details["Domain"] or "").lower()
    sheetmap = {
        "cognitive": "Bloom_Cognitive",
        "affective": "Bloom_Affective",
        "psychomotor": "Bloom_Psychomotor"
    }
    df = load_sheet_df(sheetmap.get(domain, "Bloom_Cognitive"))
    if df.empty:
        return jsonify([])
    mask = df.iloc[:, 0].astype(str).str.lower() == bloom.lower()
    if not mask.any():
        return jsonify([])
    verbs = [v.strip() for v in str(df[mask].iloc[0, 1]).split(",") if v.strip()]
    return jsonify(verbs)

# API: meta (unchanged but returns assessments)
@app.route("/api/get_meta/<plo>/<bloom>")
def api_get_meta(plo, bloom):
    profile = request.args.get("profile", "").strip().lower()
    details = get_plo_details(plo, profile) or {}
    domain = (details.get("Domain", "") or "").lower()
    if domain in ONEWORD_META and bloom in ONEWORD_META[domain]:
        criterion = ONEWORD_META[domain][bloom]["criterion"]
        condition_core = ONEWORD_META[domain][bloom]["condition"]
    else:
        crit, cond = get_criterion_phrase(domain, bloom)
        criterion = crit or ""
        condition_core = cond or get_default_condition(domain)
    vbe_value = details.get("VBE", "")
    if vbe_value in VBE_CRITERION:
        criterion = VBE_CRITERION[vbe_value]
    connector = "by" if domain == "psychomotor" else "when"
    condition = f"{connector} {condition_core}"
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

# IEG -> PEO -> PLO APIs
@app.route("/api/get_peos/<ieg>")
def api_get_peos(ieg):
    peos = IEP.get("IEGtoPEO", {}).get(ieg, [])
    return jsonify(peos)

@app.route("/api/get_plos/<peo>")
def api_get_plos(peo):
    plos = IEP.get("PEOtoPLO", {}).get(peo, [])
    return jsonify(plos)

@app.route("/api/get_statement/<level>/<stype>/<code>")
def api_get_statement(level, stype, code):
    level = level if level in IEP.get("PLOstatements", {}) else "Degree"
    stype = stype.upper()
    if stype == "PEO":
        return jsonify(IEP.get("PEOstatements", {}).get(level, {}).get(code, ""))
    if stype == "PLO":
        return jsonify(IEP.get("PLOstatements", {}).get(level, {}).get(code, ""))
    return jsonify("")

# ============================================================
# GENERATE CLO
# ============================================================
@app.route("/generate", methods=["POST"])
def generate():
    # accept profile via query or form
    profile = (
        request.args.get("profile", "").strip().lower() or
        request.form.get("profile", "").strip().lower()
    )

    plo = (request.form.get("plo") or "").strip()
    bloom = (request.form.get("bloom") or "").strip()
    verb = (request.form.get("verb") or "").strip()
    content = (request.form.get("content") or "").strip()
    course = (request.form.get("course") or "").strip()
    cw = (request.form.get("cw") or "").strip()
    vbe_style = (request.form.get("vbe_style") or "guided").strip()
    level = (request.form.get("level") or "Degree").strip()   # default Degree, can be overridden by frontend

    # basic validation
    if not plo or not bloom or not verb or not content:
        return jsonify({"error": "Missing required fields (plo, bloom, verb, content)"}), 400

    details = get_plo_details(plo, profile)
    if not details:
        return jsonify({"error": f"PLO '{plo}' not found for profile '{profile}'"}), 400

    sc_code = details.get("SC_Code", "")
    sc_desc = details.get("SC_Desc", "")
    vbe_raw = details.get("VBE", "")
    vbe_full = VBE_FULLNAME.get(vbe_raw, vbe_raw)
    domain = (details.get("Domain") or "").lower().strip()

    # Criterion + Condition
    criterion, cond_raw = get_criterion_phrase(domain, bloom)
    if not cond_raw:
        cond_raw = get_default_condition(domain)

    if domain in ONEWORD_META and bloom in ONEWORD_META[domain]:
        criterion = ONEWORD_META[domain][bloom]["criterion"]
        condition_core = ONEWORD_META[domain][bloom]["condition"]
    else:
        condition_core = cond_raw

    if vbe_raw in VBE_CRITERION:
        criterion = VBE_CRITERION[vbe_raw]

    # Build main CLO
    clo = construct_clo_sentence(
        verb, content, sc_desc, condition_core,
        criterion, vbe_full, domain, vbe_style
    )

    # ============================================================
    #  UNIVERSAL AUTO-GENERATED VARIANTS (ALL CLO TYPES)
    # ============================================================

    verb_l = verb.lower().strip()
    content_l = content.strip()
    sc_snip = sc_desc.lower().strip() if sc_desc else ""
    vbe_snip = vbe_full.lower().strip()
    cond_clean = condition_core.strip()

    # Remove leading "when/by"
    for lead in ("when ", "by "):
        if cond_clean.lower().startswith(lead):
            cond_clean = cond_clean[len(lead):].strip()
            break

    variants = {}
    variants["Standard"] = (
        f"{verb_l} {content_l} using {sc_snip} when {cond_clean} guided by {vbe_snip}."
    ).capitalize()
    variants["Critical Thinking"] = (
        f"{verb_l} {content_l} using {sc_snip} when critically evaluating {cond_clean} guided by {vbe_snip}."
    ).capitalize()
    variants["Problem-Solving"] = (
        f"{verb_l} {content_l} using {sc_snip} by applying structured problem-solving approaches to address {cond_clean}, guided by {vbe_snip}."
    ).capitalize()
    variants["Action-Oriented"] = (
        f"{verb_l} {content_l} using {sc_snip} by performing tasks related to {cond_clean} effectively and guided by {vbe_snip}."
    ).capitalize()
    variants["Professional Practice"] = (
        f"{verb_l} {content_l} using {sc_snip} when applying professional practice standards to {cond_clean}, guided by {vbe_snip}."
    ).capitalize()
    variants["Ethical Emphasis"] = (
        f"{verb_l} {content_l} using {sc_snip} when making ethically sound decisions related to {cond_clean}, grounded in {vbe_snip}."
    ).capitalize()

    clo_options = variants

    # ============================================================
    # IEG -> PEO -> PLO chain extraction (auto)
    # ============================================================
    selected_plo = plo
    selected_peo = None
    selected_ieg = None

    for peo, plolist in IEP.get("PEOtoPLO", {}).items():
        if selected_plo in plolist:
            selected_peo = peo
            break

    if selected_peo:
        for ieg, peolist in IEP.get("IEGtoPEO", {}).items():
            if selected_peo in peolist:
                selected_ieg = ieg
                break

    # statements
    plo_statement = IEP.get("PLOstatements", {}).get(level, {}).get(selected_plo, "")
    peo_statement = IEP.get("PEOstatements", {}).get(level, {}).get(selected_peo, "")
    ieg_statement = ""
    if selected_ieg:
        # I don't have separate IEG statements in your JSON; if you add them later, adapt here
        ieg_statement = f"{selected_ieg}"

    # Assessment + Rubric
    assessment, evidence = get_assessment_and_evidence(bloom, domain)
    rubric = rubric_generator(clo, verb, criterion, condition_core, sc_desc, vbe_full)

    # Save to Excel (include IEG/PEO/PLO statements)
    df = read_clo_table()
    try:
        new_row = {
            "ID": len(df)+1 if not df.empty else 1,
            "Time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "Course": course,
            "PLO": plo,
            "Bloom": bloom,
            "FullCLO": clo,
            "Mapping (SC + VBE)": f"SC Code: {sc_code} — SC Description: {sc_desc} | VBE: {vbe_full}",
            "Assessment Methods": assessment,
            "Evidence of Assessment": evidence,
            "Coursework Assessment Percentage (%)": cw,
            "Profile": profile,
            "IEG": selected_ieg,
            "PEO": selected_peo,
            "PLO Statement": plo_statement,
            "PEO Statement": peo_statement
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        write_clo_table(df)
    except Exception as e:
        return jsonify({"error": f"CLO generated but failed to save: {str(e)}"}), 500

    # Final response
    return jsonify({
        "clo": clo,
        "clo_options": clo_options,
        "assessment": assessment,
        "evidence": evidence,
        "rubric": rubric,
        "sc_code": sc_code,
        "sc_desc": sc_desc,
        "vbe": vbe_raw,
        "domain": domain,
        "ieg": selected_ieg,
        "peo": selected_peo,
        "plo_statement": plo_statement,
        "peo_statement": peo_statement,
        "ieg_statement": ieg_statement
    })

# ============================================================
# DOWNLOADS (CLO table + Rubric)
# ============================================================
@app.route("/download")
def download():
    df = read_clo_table()
    if df.empty:
        return "<p>No CLO table available.</p>"
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="CLO_Table")
    out.seek(0)
    return send_file(out, as_attachment=True, download_name="CLO_Table.xlsx")

@app.route("/download_rubric")
def download_rubric():
    df = read_clo_table()
    if df.empty:
        return "<p>No CLO table available.</p>"
    rows = []
    for _, row in df.iterrows():
        clo_text = row.get("FullCLO", "")
        plo = row.get("PLO", "")
        bloom = row.get("Bloom", "")
        profile = row.get("Profile", "")
        details = get_plo_details(str(plo), profile) or {}
        domain = (details.get("Domain","") or "").lower()
        sc_desc = details.get("SC_Desc","")
        vbe = details.get("VBE","")
        if domain in ONEWORD_META and bloom in ONEWORD_META[domain]:
            criterion = ONEWORD_META[domain][bloom]["criterion"]
            condition_core = ONEWORD_META[domain][bloom]["condition"]
        else:
            crit, cond = get_criterion_phrase(domain, bloom)
            criterion = crit or ""
            condition_core = cond or get_default_condition(domain)
        verb = clo_text.split(" ")[0].lower() if clo_text else ""
        rub = rubric_generator(clo_text, verb, criterion, condition_core, sc_desc, vbe)
        rows.append({
            "CLO": clo_text,
            "Performance Indicator": rub["indicator"],
            "Excellent": rub["excellent"],
            "Good": rub["good"],
            "Satisfactory": rub["satisfactory"],
            "Poor": rub["poor"]
        })
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        pd.DataFrame(rows).to_excel(w, index=False, sheet_name="Rubric")
    out.seek(0)
    return send_file(out, as_attachment=True, download_name="Rubric.xlsx")

# ============================================================
# RUN APP
# ============================================================
if __name__ == "__main__":
    app.run(debug=True)

