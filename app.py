# app.py — Excel-first, cleaned & integrated
import os
import json
from datetime import datetime
from io import BytesIO

import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file
from openpyxl import load_workbook

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, "static"),
    template_folder=os.path.join(BASE_DIR, "templates")
)

print("STATIC =", app.static_folder)
print("TEMPLATES =", app.template_folder)

# Path to the primary workbook and optional exported JSON (generated)
WORKBOOK_PATH = os.path.join(os.getcwd(), "SCLOG.xlsx")
FRONT_JSON_PATH = os.path.join(app.static_folder, "data", "SCLOG_front.json")

# -----------------------
# Constants & mappings
# -----------------------
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

VBE_FULLNAME = {
    "Ethics and Etiquette": "Ethical and professional conduct",
    "Integrity": "Integrity and trustworthiness",
    "Respect": "Mutual respect and inclusivity",
    "Professionalism": "Professional behaviour and accountability"
}

# -----------------------
# Excel helpers (safe)
# -----------------------
def load_sheet_df(sheet_name: str):
    """Load a sheet from the main workbook; return empty DataFrame if missing."""
    try:
        return pd.read_excel(WORKBOOK_PATH, sheet_name=sheet_name, engine="openpyxl")
    except Exception:
        return pd.DataFrame()

def read_clo_table():
    """Read CLO_Table sheet (history)."""
    try:
        return pd.read_excel(WORKBOOK_PATH, sheet_name="CLO_Table", engine="openpyxl")
    except Exception:
        return pd.DataFrame()

def write_clo_table(df):
    """Write/replace CLO_Table in the workbook safely."""
    # If workbook missing, create it
    if not os.path.exists(WORKBOOK_PATH):
        with pd.ExcelWriter(WORKBOOK_PATH, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name="CLO_Table")
        return

    # Replace CLO_Table if present
    try:
        book = load_workbook(WORKBOOK_PATH)
        if "CLO_Table" in book.sheetnames:
            del book["CLO_Table"]
        with pd.ExcelWriter(WORKBOOK_PATH, mode="a", engine="openpyxl") as writer:
            writer._book = book
            df.to_excel(writer, index=False, sheet_name="CLO_Table")
    except Exception:
        # fallback: overwrite whole file with only CLO_Table (rare)
        with pd.ExcelWriter(WORKBOOK_PATH, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name="CLO_Table")

# -----------------------
# Mapping builder
# -----------------------
def build_mapping_from_excel():
    """
    Build consolidated mapping dict from the workbook.
    It expects sheets named (case-insensitive):
      - IEGtoPEO (IEG, PEO)
      - PEOtoPLO (PEO, PLO)
      - PEOstatements (Level, PEO, Statement)
      - PLOstatements (Level, PLO, Statement)
      - PLOIndicators (PLO, Indicator)
      - PLOtoVBE (PLO, VBE)
      - SCmapping (PLO, SC)
    Non-present sheets are tolerated.
    """
    mapping = {
        "IEGs": [], "PEOs": [], "PLOs": [],
        "IEGtoPEO": {}, "PEOtoPLO": {},
        "PEOstatements": {}, "PLOstatements": {},
        "PLOtoVBE": {}, "PLOIndicators": {}, "SCmapping": {}
    }

    # helper to find sheet by tolerant name
    try:
        xls = pd.ExcelFile(WORKBOOK_PATH, engine="openpyxl")
    except Exception:
        return mapping

    def get_sheet_by_candidates(cands):
        for name in xls.sheet_names:
            if name.strip().lower() in [c.strip().lower() for c in cands]:
                return xls.parse(name)
        return pd.DataFrame()

    # IEGtoPEO
    iegtopeo_df = get_sheet_by_candidates(["IEGtoPEO", "IEG to PEO", "IEG_to_PEO"])
    if not iegtopeo_df.empty:
        cols = [str(c).strip() for c in iegtopeo_df.columns]
        if len(cols) >= 2:
            for _, r in iegtopeo_df.iterrows():
                ieg = str(r[cols[0]]).strip()
                peo = str(r[cols[1]]).strip()
                if ieg and peo and ieg.lower() != "nan" and peo.lower() != "nan":
                    mapping["IEGtoPEO"].setdefault(ieg, []).append(peo)
            mapping["IEGs"] = sorted(mapping["IEGtoPEO"].keys())

    # PEOtoPLO
    peotoplo_df = get_sheet_by_candidates(["PEOtoPLO", "PEO to PLO", "PEO_to_PLO"])
    if not peotoplo_df.empty:
        cols = [str(c).strip() for c in peotoplo_df.columns]
        if len(cols) >= 2:
            for _, r in peotoplo_df.iterrows():
                peo = str(r[cols[0]]).strip()
                plo = str(r[cols[1]]).strip()
                if peo and plo and peo.lower() != "nan" and plo.lower() != "nan":
                    mapping["PEOtoPLO"].setdefault(peo, []).append(plo)
            mapping["PEOs"] = sorted(mapping["PEOtoPLO"].keys())
            # derive PLOs
            plos = set()
            for vals in mapping["PEOtoPLO"].values():
                plos.update(vals)
            mapping["PLOs"] = sorted(plos)

    # PEOstatements (Level, PEO, Statement)
    peostat_df = get_sheet_by_candidates(["PEOstatements", "PEO statements", "PEO_Statements"])
    if not peostat_df.empty:
        cols = [str(c).strip() for c in peostat_df.columns]
        if len(cols) >= 3:
            for _, r in peostat_df.iterrows():
                lvl = str(r[cols[0]]).strip()
                peo = str(r[cols[1]]).strip()
                stmt = str(r[cols[2]]).strip()
                if lvl and peo:
                    mapping["PEOstatements"].setdefault(lvl, {})[peo] = stmt

    # PLOstatements (Level, PLO, Statement)
    plostat_df = get_sheet_by_candidates(["PLOstatements", "PLO statements", "PLO_Statements"])
    if not plostat_df.empty:
        cols = [str(c).strip() for c in plostat_df.columns]
        if len(cols) >= 3:
            for _, r in plostat_df.iterrows():
                lvl = str(r[cols[0]]).strip()
                plo = str(r[cols[1]]).strip()
                stmt = str(r[cols[2]]).strip()
                if lvl and plo:
                    mapping["PLOstatements"].setdefault(lvl, {})[plo] = stmt

    # PLOIndicators (PLO, Indicator)
    ploindi_df = get_sheet_by_candidates(["PLOIndicators", "PLO Indicators", "PLO_Indicators"])
    if not ploindi_df.empty:
        cols = [str(c).strip() for c in ploindi_df.columns]
        if len(cols) >= 2:
            for _, r in ploindi_df.iterrows():
                plo = str(r[cols[0]]).strip()
                ind = str(r[cols[1]]).strip()
                if plo:
                    mapping["PLOIndicators"][plo] = ind

    # PLOtoVBE (PLO, VBE)
    plotovbe_df = get_sheet_by_candidates(["PLOtoVBE", "PLO to VBE", "PLO_VBE", "PLOtoVBE "])
    if not plotovbe_df.empty:
        cols = [str(c).strip() for c in plotovbe_df.columns]
        if len(cols) >= 2:
            for _, r in plotovbe_df.iterrows():
                plo = str(r[cols[0]]).strip()
                vbe = str(r[cols[1]]).strip()
                if plo:
                    mapping["PLOtoVBE"][plo] = vbe

    # SCmapping (PLO, SC)
    scmap_df = get_sheet_by_candidates(["SCmapping", "SC mapping", "SCmapping "])
    if not scmap_df.empty:
        cols = [str(c).strip() for c in scmap_df.columns]
        if len(cols) >= 2:
            for _, r in scmap_df.iterrows():
                plo = str(r[cols[0]]).strip()
                sc = str(r[cols[1]]).strip()
                if plo:
                    mapping["SCmapping"][plo] = sc

    return mapping

# -----------------------
# Load mapping (attempt JSON first, else build from Excel)
# -----------------------
def load_front_mapping():
    # prefer exported JSON copy if present in static/data
    if os.path.exists(FRONT_JSON_PATH):
        try:
            with open(FRONT_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # else build from Excel
    return build_mapping_from_excel()

# -----------------------
# Criterion / Assessment helpers (unchanged)
# -----------------------
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

# -----------------------
# CLO construction & rubric (unchanged functions, kept for clarity)
# -----------------------
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
    indicator = f"Ability to {verb_l} {sc_l} {cond} in accordance with {vbe_l}."
    excellent = f"Consistently demonstrates {vbe_l} and applies {sc_l} {cond} with high accuracy and clarity."
    good = f"Generally demonstrates {vbe_l} and applies {sc_l} {cond} with minor gaps in clarity or consistency."
    satisfactory = f"Partially demonstrates {vbe_l}; applies {sc_l} {cond} inconsistently."
    poor = f"Does not demonstrate {vbe_l}; unable to apply {sc_l} {cond} effectively."
    return {"indicator": indicator, "excellent": excellent, "good": good, "satisfactory": satisfactory, "poor": poor}

# -----------------------
# ROUTES
# -----------------------
@app.route("/")
def index():
    profile = request.args.get("profile", "health")
    # plos passed for backwards compatibility (not required when frontend uses /api/mapping)
    mapping = load_front_mapping()
    plos = mapping.get("PLOs", [])
    return render_template("generator.html", plos=plos, profile=profile)

@app.route("/api/mapping")
def api_mapping():
    """Return consolidated mapping JSON (Excel-built or pre-exported JSON)."""
    mapping = load_front_mapping()
    return jsonify(mapping)

# Keep bloom/verbs/meta endpoints (frontend needs them)
@app.route("/api/get_blooms/<plo>")
def api_get_blooms(plo):
    profile = request.args.get("profile", "").strip().lower()
    details = None
    # attempt to infer details from SCmapping or fallback to mapping file
    mapping = load_front_mapping()
    # try to get domain from consolidated mapping (if available via SCmapping->SC description or PLOtoVBE)
    domain = ""
    # fallback to workbook mapping (existing logic)
    details = None
    try:
        details = None
        df = load_sheet_df(PROFILE_SHEET_MAP.get(profile, "Mapping"))
        if not df.empty:
            df.columns = [str(c).strip() for c in df.columns]
            col_plo = list(df.columns)[0]
            mask = df[col_plo].astype(str).str.strip().str.upper() == str(plo).strip().upper()
            if mask.any():
                row = df[mask].iloc[0]
                details = {"Domain": row.get("Domain","") if "Domain" in df.columns else row.get("domain","")}
    except Exception:
        details = None

    if not details:
        # fallback domain heuristics from mapping
        plo_vbe = mapping.get("PLOtoVBE", {}).get(plo, "")
        domain = "affective" if any(x in (plo_vbe or "").lower() for x in ["ethic","professional","integrity"]) else "cognitive"
    else:
        domain = (details.get("Domain") or details.get("domain") or "").lower()

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

@app.route("/api/get_verbs/<plo>/<bloom>")
def api_get_verbs(plo, bloom):
    profile = request.args.get("profile", "").strip().lower()
    # domain inference similar to get_blooms
    mapping = load_front_mapping()
    plo_vbe = mapping.get("PLOtoVBE", {}).get(plo, "")
    domain = "affective" if any(x in (plo_vbe or "").lower() for x in ["ethic","professional","integrity"]) else "cognitive"
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

@app.route("/api/get_meta/<plo>/<bloom>")
def api_get_meta(plo, bloom):
    profile = request.args.get("profile", "").strip().lower()
    mapping = load_front_mapping()
    # try to fetch SC/VBE/Domain from mapping
    sc_code = mapping.get("SCmapping", {}).get(plo, "")
    vbe = mapping.get("PLOtoVBE", {}).get(plo, "")
    # domain inference
    domain = (vbe or "").lower()
    if any(k in domain for k in ["ethic","professional","integrity"]):
        domain = "affective"
    else:
        domain = "cognitive"

    # criterion + condition
    if domain in ONEWORD_META and bloom in ONEWORD_META[domain]:
        criterion = ONEWORD_META[domain][bloom]["criterion"]
        condition_core = ONEWORD_META[domain][bloom]["condition"]
    else:
        crit, cond = get_criterion_phrase(domain, bloom)
        criterion = crit or ""
        condition_core = cond or get_default_condition(domain)

    # VBE overrides
    if vbe in VBE_CRITERION:
        criterion = VBE_CRITERION[vbe]

    connector = "by" if domain == "psychomotor" else "when"
    condition = f"{connector} {condition_core}"

    assessment, evidence = get_assessment_and_evidence(bloom, domain)

    return jsonify({
        "sc_code": sc_code,
        "sc_desc": "",  # if you have SC description sheet, read and fill here
        "vbe": vbe,
        "domain": domain,
        "criterion": criterion,
        "condition": condition,
        "assessment": assessment,
        "evidence": evidence
    })

# -----------------------
# Generate CLO endpoint (keeps Excel write)
# -----------------------
@app.route("/generate", methods=["POST"])
def generate():
    profile = (request.args.get("profile", "").strip().lower() or request.form.get("profile", "").strip().lower())
    plo = (request.form.get("plo") or "").strip()
    bloom = (request.form.get("bloom") or "").strip()
    verb = (request.form.get("verb") or "").strip()
    content = (request.form.get("content") or "").strip()
    course = (request.form.get("course") or "").strip()
    cw = (request.form.get("cw") or "").strip()
    vbe_style = (request.form.get("vbe_style") or "guided").strip()
    level = (request.form.get("level") or "Degree").strip()

    if not plo or not bloom or not verb or not content:
        return jsonify({"error": "Missing required fields (plo, bloom, verb, content)"}), 400

    # details via mapping (prefer consolidated mapping)
    mapping = load_front_mapping()
    sc_code = mapping.get("SCmapping", {}).get(plo, "")
    vbe_raw = mapping.get("PLOtoVBE", {}).get(plo, "")
    vbe_full = VBE_FULLNAME.get(vbe_raw, vbe_raw)
    domain = (vbe_raw or "").lower()
    if any(k in domain for k in ["ethic","professional","integrity"]):
        domain = "affective"
    else:
        domain = "cognitive"

    # criterion + condition
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

    clo = construct_clo_sentence(verb, content, "", condition_core, criterion, vbe_full, domain, vbe_style)

    # variants
    verb_l = verb.lower().strip()
    content_l = content.strip()
    vbe_snip = vbe_full.lower().strip()
    cond_clean = condition_core.strip()
    for lead in ("when ", "by "):
        if cond_clean.lower().startswith(lead):
            cond_clean = cond_clean[len(lead):].strip()
            break

    variants = {
        "Standard": (f"{verb_l} {content_l} when {cond_clean} guided by {vbe_snip}.").capitalize(),
        "Critical Thinking": (f"{verb_l} {content_l} when critically evaluating {cond_clean} guided by {vbe_snip}.").capitalize(),
        "Problem-Solving": (f"{verb_l} {content_l} by applying structured problem-solving approaches to address {cond_clean}, guided by {vbe_snip}.").capitalize()
    }

    # auto-detect chain (PEO/IEG) using mapping
    selected_peo = None
    selected_ieg = None
    for peo, plolist in mapping.get("PEOtoPLO", {}).items():
        if plo in plolist:
            selected_peo = peo
            break
    if selected_peo:
        for ieg, peos in mapping.get("IEGtoPEO", {}).items():
            if selected_peo in peos:
                selected_ieg = ieg
                break

    plo_statement = mapping.get("PLOstatements", {}).get(level, {}).get(plo, "")
    peo_statement = mapping.get("PEOstatements", {}).get(level, {}).get(selected_peo, "")
    ieg_statement = selected_ieg or ""

    assessment, evidence = get_assessment_and_evidence(bloom, domain)
    rubric = rubric_generator(clo, verb, criterion, condition_core, "", vbe_full)

    # save to CLO_Table
    df = read_clo_table()
    try:
        new_row = {
            "ID": len(df) + 1 if not df.empty else 1,
            "Time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "Course": course,
            "PLO": plo,
            "Bloom": bloom,
            "FullCLO": clo,
            "Mapping (SC + VBE)": f"SC Code: {sc_code} | VBE: {vbe_full}",
            "Assessment Methods": assessment,
            "Evidence of Assessment": evidence,
            "Coursework Assessment Percentage (%)": cw,
            "Profile": profile,
            "IEG": ieg_statement,
            "PEO": selected_peo,
            "PLO Statement": plo_statement,
            "PEO Statement": peo_statement
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        write_clo_table(df)
    except Exception as e:
        return jsonify({"error": f"CLO generated but failed to save: {str(e)}"}), 500

    return jsonify({
        "clo": clo,
        "clo_options": variants,
        "assessment": assessment,
        "evidence": evidence,
        "rubric": rubric,
        "sc_code": sc_code,
        "vbe": vbe_raw,
        "domain": domain,
        "ieg": ieg_statement,
        "peo": selected_peo,
        "plo_statement": plo_statement,
        "peo_statement": peo_statement
    })

# -----------------------
# Downloads
# -----------------------
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
        # try to use consolidated mapping for VBE/sc_desc
        mapping = load_front_mapping()
        vbe = mapping.get("PLOtoVBE", {}).get(plo, "")
        sc_desc = mapping.get("SCmapping", {}).get(plo, "")
        if (mapping.get("PLOtoVBE", {}).get(plo, "") or "").lower() in VBE_CRITERION:
            criterion = VBE_CRITERION.get(vbe, "")
            condition_core = ""
        else:
            if (vbe or "").lower() in ONEWORD_META:
                criterion = ONEWORD_META[(vbe or "").lower()].get(bloom, {}).get("criterion","")
                condition_core = ONEWORD_META[(vbe or "").lower()].get(bloom, {}).get("condition","")
            else:
                crit, cond = get_criterion_phrase((vbe or "").lower(), bloom)
                criterion = crit or ""
                condition_core = cond or get_default_condition((vbe or "").lower())
        verb = (clo_text.split(" ")[0].lower() if clo_text else "")
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

# -----------------------
# Run
# -----------------------
if __name__ == "__main__":
    app.run(debug=True)
