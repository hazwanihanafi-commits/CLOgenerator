from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
import pandas as pd
import os
from datetime import datetime
from openpyxl import load_workbook
from io import BytesIO

app = Flask(__name__, template_folder="templates")

WORKBOOK_PATH = os.path.join(os.getcwd(), "SCLOG.xlsx")

# ============================================================
# ONE-WORD META (Overrides Criterion + Condition)
# ============================================================
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
    "": "Mapping",
    "health": "Mapping_health",
    "sc": "Mapping_sc",
    "eng": "Mapping_eng",
    "socs": "Mapping_socs",
    "edu": "Mapping_edu",
    "bus": "Mapping_bus",
    "arts": "Mapping_arts"
}
# ============================================================
# VBE → CRITERION MAP (Overrides Bloom Criterion)
# ============================================================
VBE_CRITERION = {
    "Ethics & Professionalism": "Guided by ethics and professionalism",
    "Professional practice standards": "Aligned with professional practice standards",
    "Integrity": "Demonstrating integrity in judgement",
    "Ethics & Etiquette": "Guided by ethical and professional etiquette",
    "Professionalism & Teamwork": "Demonstrating professionalism and effective teamwork",
    "Professionalism & Well-being": "Upholding professionalism and personal well-being",
    "Honesty & Integrity": "Guided by honesty and integrity",
    "Professional conduct": "Demonstrating responsible and professional conduct"
}

# ============================================================
# FULL NAME MAPPINGS FOR SC + VBE
# ============================================================
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
    "Ethics & Etiquette": "Ethical and professional conduct",
    "Integrity": "Integrity and trustworthiness",
    "Respect": "Mutual respect and inclusivity",
    "Professionalism": "Professional behaviour and accountability"
}

# ============================================================
# EXCEL HELPERS
# ============================================================
def load_sheet_df(sheet_name: str):
    try:
        return pd.read_excel(WORKBOOK_PATH, sheet_name=sheet_name, engine="openpyxl")
    except:
        return pd.DataFrame()

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
# CRITERION + CONDITION
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

# ============================================================
# ASSESSMENT & EVIDENCE
# ============================================================
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
# CLO CONSTRUCTION
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
    verb = verb.lower().strip()
    content = content.strip()
    criterion = criterion.strip().rstrip(".")
    condition_core = condition_core.strip()

    for lead in ("when ","by "):
        if condition_core.lower().startswith(lead):
            condition_core = condition_core[len(lead):].strip()
            break

    condition = f"{decide_connector(domain)} {condition_core}" if condition_core else ""

    parts = [
        f"{verb} {content}",
        sc_snippet(sc_desc),
        condition,
        criterion,
        vbe_phrase(vbe, vbe_style)
    ]
    s = " ".join([p for p in parts if p]).strip()
    if not s.endswith("."):
        s += "."
    return s.capitalize()

# ============================================================
# RUBRIC
# ============================================================
def rubric_generator(clo, verb, criterion, condition_core, sc_desc, vbe):
    connector = "by" if "perform" in clo.lower() else "when"

    if condition_core.lower().startswith(("when ","by ")):
        cond = condition_core
    else:
        cond = f"{connector} {condition_core}"

    # --------------------------------------------------------
    #  NEW VBE-DRIVEN RUBRIC (Replace old rubric fully)
    # --------------------------------------------------------
    indicator = (
        f"Ability to {verb.lower()} {sc_desc.lower()} {cond} "
        f"in accordance with {vbe.lower()}."
    )

    return {
        "indicator": indicator,
        "excellent": f"Consistently demonstrates {vbe.lower()} and applies {sc_desc.lower()} {cond} effectively.",
        "good": f"Generally demonstrates {vbe.lower()} and applies {sc_desc.lower()} {cond} with minor gaps.",
        "satisfactory": f"Partially demonstrates {vbe.lower()}; applies {sc_desc.lower()} {cond} inconsistently.",
        "poor": f"Does not demonstrate {vbe.lower()}; unable to apply {sc_desc.lower()} {cond} effectively."
    }

# ============================================================
# CLO TABLE (Excel)
# ============================================================
def read_clo_table():
    try:
        return pd.read_excel(WORKBOOK_PATH, sheet_name="CLO_Table", engine="openpyxl")
    except:
        return pd.DataFrame()

def write_clo_table(df):
    book = load_workbook(WORKBOOK_PATH)
    if "CLO_Table" in book.sheetnames:
        del book["CLO_Table"]

    with pd.ExcelWriter(WORKBOOK_PATH, mode="a", engine="openpyxl") as w:
        w._book = book
        df.to_excel(w, index=False, sheet_name="CLO_Table")

# ============================================================
# ROUTES
# ============================================================
@app.route("/")
def index():
    profile = request.args.get("profile","").lower()
    df_map = get_mapping_dict(profile)

    plos = df_map[df_map.columns[0]].dropna().astype(str).tolist() if not df_map.empty else []

    return render_template("generator.html", plos=plos, profile=profile)

# ============================================================
# GENERATE CLO
# ============================================================
@app.route("/generate", methods=["POST"])
def generate():
    profile = request.args.get("profile", "").strip().lower()

    plo = request.form.get("plo")
    bloom = request.form.get("bloom")
    verb = request.form.get("verb")
    content = request.form.get("content")
    course = request.form.get("course")
    cw = request.form.get("cw")
    vbe_style = request.form.get("vbe_style", "guided")

    details = get_plo_details(plo, profile)
    sc_code = details["SC_Code"]
    sc_desc = details["SC_Desc"]
    vbe_raw = details["VBE"]

    # lookup full names
    sc_full = SC_FULLNAME.get(sc_code, sc_desc)
    vbe_full = VBE_FULLNAME.get(vbe_raw, vbe_raw)

    if not details:
        return jsonify({"error": "PLO not found"}), 400

    domain = details["Domain"].lower()

       # ------------------------------
    # Criterion + Condition
    # ------------------------------
    criterion, condition_raw = get_criterion_phrase(domain, bloom)
    if not condition_raw:
        condition_raw = get_default_condition(domain)

    if domain in ONEWORD_META and bloom in ONEWORD_META[domain]:
        criterion = ONEWORD_META[domain][bloom]["criterion"]
        condition_core = ONEWORD_META[domain][bloom]["condition"]
    else:
        condition_core = condition_raw

    # --- VBE overrides Bloom criterion ---
    vbe_value = details.get("VBE", "")
    if vbe_value in VBE_CRITERION:
        criterion = VBE_CRITERION[vbe_value]

    # ------------------------------
    # MAIN CLO
    # ------------------------------
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

    # ------------------------------------------------------------
    # 1. Standard (Baseline CLO)
    # ------------------------------------------------------------
    variants["Standard"] = (
        f"{verb_l} {content_l} using {sc_snip} when {cond_clean} "
        f"guided by {vbe_snip}."
    ).capitalize()

    # ------------------------------------------------------------
    # 2. Critical Thinking Variant
    # ------------------------------------------------------------
    variants["Critical Thinking"] = (
        f"{verb_l} {content_l} using {sc_snip} when critically evaluating {cond_clean} "
        f"guided by {vbe_snip}."
    ).capitalize()

    # ------------------------------------------------------------
    # 3. Problem-Solving Variant
    # ------------------------------------------------------------
    variants["Problem-Solving"] = (
        f"{verb_l} {content_l} using {sc_snip} by applying structured problem-solving approaches "
        f"to address {cond_clean}, guided by {vbe_snip}."
    ).capitalize()

    # ------------------------------------------------------------
    # 4. Action-Oriented Variant
    # ------------------------------------------------------------
    variants["Action-Oriented"] = (
        f"{verb_l} {content_l} using {sc_snip} by performing tasks related to {cond_clean} "
        f"effectively and guided by {vbe_snip}."
    ).capitalize()

    # ------------------------------------------------------------
    # 5. Professional Practice Variant
    # ------------------------------------------------------------
    variants["Professional Practice"] = (
        f"{verb_l} {content_l} using {sc_snip} when applying professional practice standards to {cond_clean}, "
        f"guided by {vbe_snip}."
    ).capitalize()

    # ------------------------------------------------------------
    # 6. Ethical Emphasis Variant
    # ------------------------------------------------------------
    variants["Ethical Emphasis"] = (
        f"{verb_l} {content_l} using {sc_snip} when making ethically sound decisions related to {cond_clean}, "
        f"grounded in {vbe_snip}."
    ).capitalize()

    # ✅ Assign to CLO options for frontend
    clo_options = variants

    # ------------------------------
    # Assessment + Rubric
    # ------------------------------
    assessment, evidence = get_assessment_and_evidence(bloom, domain)

    rubric = rubric_generator(
        clo, verb, criterion, condition_core, sc_desc, vbe_full
    )

    mapping_full = (
        f"SC Code: {sc_code} — SC Description: {sc_desc} | "
        f"VBE: {vbe_full}"
    )

    # ------------------------------
    # Save to History Excel
    # ------------------------------
    df = read_clo_table()
    new_row = {
        "ID": len(df)+1 if not df.empty else 1,
        "Time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "Course": course,
        "PLO": plo,
        "Bloom": bloom,
        "FullCLO": clo,
        "Mapping (SC + VBE)": mapping_full,
        "Assessment Methods": assessment,
        "Evidence of Assessment": evidence,
        "Coursework Assessment Percentage (%)": cw,
        "Profile": profile
    }

    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    write_clo_table(df)

    # ------------------------------
    # Final API Output
    # ------------------------------
    return jsonify({
        "clo": clo,
        "clo_options": clo_options,
        "assessment": assessment,
        "evidence": evidence,
        "rubric": rubric,
        "sc_code": details["SC_Code"],
        "sc_desc": details["SC_Desc"],
        "vbe": details["VBE"],
        "domain": domain
    })

# ============================================================
# API ROUTES (BLOOMS, VERBS, META)
# ============================================================

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

@app.route("/api/get_meta/<plo>/<bloom>")
def api_get_meta(plo, bloom):
    profile = request.args.get("profile", "").strip().lower()
    details = get_plo_details(plo, profile) or {}
    domain = (details.get("Domain", "") or "").lower()

    # ---------------------------
    # 1) Get Bloom criterion + condition
    # ---------------------------
    if domain in ONEWORD_META and bloom in ONEWORD_META[domain]:
        criterion = ONEWORD_META[domain][bloom]["criterion"]
        condition_core = ONEWORD_META[domain][bloom]["condition"]
    else:
        crit, cond = get_criterion_phrase(domain, bloom)
        criterion = crit or ""
        condition_core = cond or get_default_condition(domain)

    # ---------------------------
    # 2) Override Criterion USING VBE_CRITERION if VBE exists
    # ---------------------------
    vbe_value = details.get("VBE", "")
    if vbe_value in VBE_CRITERION:
        criterion = VBE_CRITERION[vbe_value]

    # ---------------------------
    # 3) Build condition phrase
    # ---------------------------
    connector = "by" if domain == "psychomotor" else "when"
    condition = f"{connector} {condition_core}"

    # ---------------------------
    # 4) Assessment + Evidence
    # ---------------------------
    assessment, evidence = get_assessment_and_evidence(bloom, domain)

    # ---------------------------
    # 5) Final return
    # ---------------------------
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

# ============================================================
# DOWNLOAD CLO TABLE
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

# ============================================================
# DOWNLOAD RUBRIC TABLE
# ============================================================
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
        domain = details.get("Domain","").lower()
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








