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
        "Analyze":    {"criterion": "critically",     "condition": "evaluating case information"},
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
        "Perception":             {"criterion": "accurately",    "condition": "identifying cues"},
        "Set":                    {"criterion": "precisely",     "condition": "preparing procedures"},
        "Guided Response":        {"criterion": "under guidance","condition": "practising skills"},
        "Mechanism":              {"criterion": "competently",   "condition": "performing techniques"},
        "Complex Overt Response": {"criterion": "efficiently",   "condition": "executing tasks"},
        "Adaptation":             {"criterion": "safely",        "condition": "adjusting actions"},
        "Origination":            {"criterion": "creatively",    "condition": "developing procedures"}
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

    indicator = f"Ability to {verb.lower()} {sc_desc.lower()} {cond} {criterion.lower()} while demonstrating {vbe.lower()}."

    return {
        "indicator": indicator,
        "excellent": f"Consistently {criterion.lower()} and applies {sc_desc.lower()} {cond} with clear adherence to {vbe.lower()}.",
        "good": f"Generally {criterion.lower()} and applies {sc_desc.lower()} {cond} with minor gaps in {vbe.lower()}.",
        "satisfactory": f"Partially {criterion.lower()}; applies {sc_desc.lower()} {cond} but inconsistently demonstrates {vbe.lower()}.",
        "poor": f"Does not {criterion.lower()}; unable to apply {sc_desc.lower()} {cond}; lacks adherence to {vbe.lower()}."
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

    df_ct = read_clo_table()
    table_html = df_ct.to_html(classes="table table-sm table-striped", index=False) if not df_ct.empty else "<p>No CLO records yet.</p>"

    return render_template("generator.html", plos=plos, table_html=table_html, profile=profile)

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
    if not details:
        return jsonify({"error":"PLO not found"}), 400

    domain = details["Domain"].lower()

    criterion, condition_raw = get_criterion_phrase(domain, bloom)
    if not condition_raw:
        condition_raw = get_default_condition(domain)

    if domain in ONEWORD_META and bloom in ONEWORD_META[domain]:
        criterion = ONEWORD_META[domain][bloom]["criterion"]
        condition_core = ONEWORD_META[domain][bloom]["condition"]
    else:
        condition_core = condition_raw

    clo = construct_clo_sentence(
        verb, content, details["SC_Desc"], condition_core,
        criterion, details["VBE"], domain, vbe_style
    )

    pure_condition = condition_core.lower().strip()
    for lead in ("when ","by "):
        if pure_condition.startswith(lead):
            pure_condition = pure_condition[len(lead):].strip()
            break

    clo_a = construct_clo_sentence(verb, content, details["SC_Desc"], pure_condition, criterion, details["VBE"], "cognitive", vbe_style)
    clo_b = construct_clo_sentence(verb, content, details["SC_Desc"], pure_condition, criterion, details["VBE"], "psychomotor", vbe_style)
    clo_c = construct_clo_sentence(verb, content, details["SC_Desc"], pure_condition, criterion, details["VBE"], domain, vbe_style)

    assessment, evidence = get_assessment_and_evidence(bloom, domain)

    rubric = rubric_generator(clo, verb, criterion, condition_core, details["SC_Desc"], details["VBE"])

    mapping_full = (
        f"SC Code: {details['SC_Code']} — SC Description: {details['SC_Desc']} | "
        f"VBE: {details['VBE']}"
    )

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

    return jsonify({
        "clo": clo,
        "clo_options": {"A": clo_a, "B": clo_b, "C": clo_c},
        "assessment": assessment,
        "evidence": evidence,
        "rubric": rubric,
        "sc_code": details["SC_Code"],
        "sc_desc": details["SC_Desc"],
        "vbe": details["VBE"],
        "domain": domain
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

