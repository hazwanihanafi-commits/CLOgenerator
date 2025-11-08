from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
import pandas as pd
import os
from datetime import datetime
from openpyxl import load_workbook
from io import BytesIO

# ------------------------------------------------------------
# ONE-WORD META for CLO auto-polish (Domain × Bloom)
# ------------------------------------------------------------
ONEWORD_META = {
    "cognitive": {
        "Remember":   {"criterion": "accurately",     "condition": "recalling information"},
        "Understand": {"criterion": "coherently",     "condition": "explaining concepts"},
        "Apply":      {"criterion": "effectively",    "condition": "applying methods"},
        "Analyze":    {"criterion": "critically",     "condition": "evaluating information"},
        "Evaluate":   {"criterion": "independently",  "condition": "making judgments"},
        "Create":     {"criterion": "innovatively",   "condition": "generating ideas"}
    },
    "affective": {
        "Receive":         {"criterion": "openly",        "condition": "engaging respectfully"},
        "Respond":         {"criterion": "responsibly",   "condition": "participating actively"},
        "Value":           {"criterion": "sincerely",     "condition": "demonstrating values"},
        "Organization":    {"criterion": "constructively","condition": "balancing perspectives"},
        "Characterization":{"criterion": "ethically",     "condition": "behaving professionally"}
    },
    "psychomotor": {
        "Perception":              {"criterion": "accurately",        "condition": "identifying cues"},
        "Set":                     {"criterion": "precisely",         "condition": "preparing procedures"},
        "Guided Response":         {"criterion": "under supervision", "condition": "practising skills"},
        "Mechanism":               {"criterion": "competently",       "condition": "performing techniques"},
        "Complex Overt Response":  {"criterion": "efficiently",       "condition": "executing tasks"},
        "Adaptation":              {"criterion": "safely",            "condition": "adjusting actions"},
        "Origination":             {"criterion": "creatively",        "condition": "developing procedures"}
    }
}

app = Flask(__name__, template_folder="templates")
WORKBOOK_PATH = os.path.join(os.getcwd(), "SCLOG.xlsx")

# ------------------------------------------------------------
# DISCIPLINE → SHEET MAP
# ------------------------------------------------------------
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

# ------------------------------------------------------------
# LOAD SHEET
# ------------------------------------------------------------
def load_sheet_df(sheet_name: str) -> pd.DataFrame:
    try:
        return pd.read_excel(WORKBOOK_PATH, sheet_name=sheet_name, engine="openpyxl")
    except Exception:
        return pd.DataFrame()

# ------------------------------------------------------------
# GET MAPPING TABLE
# ------------------------------------------------------------
def get_mapping_dict(profile=None) -> pd.DataFrame:
    profile = (profile or "").strip().lower()
    sheet = PROFILE_SHEET_MAP.get(profile, "Mapping")
    df = load_sheet_df(sheet)
    if df.empty:
        return pd.DataFrame()
    df.columns = [str(c).strip() for c in df.columns]
    return df

# ------------------------------------------------------------
# ✅ BULLETPROOF PLO LOOKUP
# ------------------------------------------------------------
def get_plo_details(plo, profile=None):
    df = get_mapping_dict(profile)
    if df.empty:
        return None

    colmap = {c.strip().lower().replace(" ", ""): c for c in df.columns}
    col_plo = list(df.columns)[0]          # Assume first column is always PLO
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

# ------------------------------------------------------------
# CRITERION / CONDITION
# ------------------------------------------------------------
def get_criterion_phrase(domain, bloom):
    df = load_sheet_df("Criterion")
    if df.empty:
        return "", ""
    df.columns = [c.strip() for c in df.columns]
    dom_col, bloom_col, crit_col, cond_col = df.columns[:4]
    mask = (df[dom_col].astype(str).str.lower() == str(domain).lower()) & \
           (df[bloom_col].astype(str).str.lower() == str(bloom).lower())
    if not mask.any():
        return "", ""
    row = df[mask].iloc[0]
    return str(row[crit_col]).strip(), str(row[cond_col]).strip()

def get_default_condition(domain):
    mapping = {
        "cognitive": "in clinical or case-based contexts",
        "affective": "during group, community, or clinical interactions",
        "psychomotor": "under supervised practical or laboratory conditions"
    }
    return mapping.get(str(domain).lower(), "")

# ------------------------------------------------------------
# ASSESSMENT & EVIDENCE
# ------------------------------------------------------------
def get_assessment_and_evidence(bloom, domain):
    domain = str(domain).lower()
    sheet = "Assess_Affective_Psychomotor" if domain in ("affective", "psychomotor") else "Bloom_Assessments"
    df = load_sheet_df(sheet)
    if df.empty:
        return "", ""
    df.columns = [c.strip() for c in df.columns]
    bloom_col, assess_col, evid_col = df.columns[:3]
    mask = df[bloom_col].astype(str).str.lower() == str(bloom).lower()
    if not mask.any():
        return "", ""
    row = df[mask].iloc[0]
    return str(row[assess_col]).strip(), str(row[evid_col]).strip()

# ------------------------------------------------------------
# POLISH HELPERS
# ------------------------------------------------------------
def choose_prefix(domain: str) -> str:
    return "by" if (domain or "").lower() == "psychomotor" else "when"

def polish_condition(condition: str, domain: str = "", remove_condition: bool = False) -> str:
    if remove_condition:
        return ""
    c = (condition or "").strip()
    if not c:
        return ""
    # strip accidental leading 'when/by'
    lc = c.lower()
    if lc.startswith("when "):
        c = c[5:].strip()
    elif lc.startswith("by "):
        c = c[3:].strip()
    return f"{choose_prefix(domain)} {c}"

def vbe_phrase(vbe: str, style: str = "guided") -> str:
    vbe = (vbe or "").strip()
    if not vbe:
        return ""
    s = (style or "guided").lower()
    if s == "accordance":
        return f"in accordance with {vbe.lower()}"
    if s == "aligned":
        return f"aligned with {vbe.lower()}"
    return f"guided by {vbe.lower()}"

def sc_snippet(sc_desc: str) -> str:
    s = (sc_desc or "").strip().lower()
    if not s:
        return ""
    return s if s.startswith("using ") else f"using {s}"

# ------------------------------------------------------------
# CLO SENTENCE + VARIANTS
# ------------------------------------------------------------
def construct_clo_sentence(verb, content, sc_desc, condition, criterion, vbe_text, vbe_style="guided", domain: str = ""):
    parts = []

    base = f"{str(verb).strip().lower()} {str(content).strip()}"
    parts.append(base)

    sc_part = sc_snippet(sc_desc)
    if sc_part:
        parts.append(sc_part)

    # criterion standardization (prefix with 'to ' if it's an adverb/standard)
    crit = (criterion or "").strip().rstrip(".")
    if crit and not crit.lower().startswith(("by ", "to ", "with ", "at ", "in ", "according ")):
        crit = "to " + crit
    if crit:
        parts.append(crit)

    # polished condition
    if condition:
        parts.append(polish_condition(condition, domain=domain, remove_condition=False))

    vbe_part = vbe_phrase(vbe_text, vbe_style)
    if vbe_part:
        parts.append(vbe_part)

    sentence = " ".join([p for p in parts if p]).strip()
    if sentence:
        sentence = sentence[0].upper() + sentence[1:]
        if not sentence.endswith("."):
            sentence += "."
    return sentence

def make_clo_variants(verb, content, sc_desc, condition_word, criterion, domain, vbe_text, vbe_style="guided"):
    # ensure raw condition word (without when/by) goes through polish per variant
    cond_when = polish_condition(condition_word, domain="cognitive" if domain != "psychomotor" else "", remove_condition=False)
    if cond_when.startswith("by "):  # ensure a 'when' version as well
        cond_when = "when " + cond_when.split(" ", 1)[1]
    cond_by = polish_condition(condition_word, domain="psychomotor", remove_condition=False)

    vbe_part = vbe_phrase(vbe_text, vbe_style)

    A = construct_clo_sentence(verb, content, sc_desc, cond_by,   criterion, vbe_text, vbe_style, domain)
    B = construct_clo_sentence(verb, content, sc_desc, cond_when, criterion, vbe_text, vbe_style, domain)
    # Hybrid: auto-choose by domain
    hybrid_cond = polish_condition(condition_word, domain=domain, remove_condition=False)
    C = construct_clo_sentence(verb, content, sc_desc, hybrid_cond, criterion, vbe_text, vbe_style, domain)

    return A, B, C

# ------------------------------------------------------------
# RUBRIC GENERATOR
# ------------------------------------------------------------
def rubric_generator(clo, verb, criterion, condition, sc_desc, vbe):
    verb = (verb or "").strip().lower()
    criterion = (criterion or "").strip()
    condition = polish_condition(condition or "", domain="", remove_condition=False)
    sc_desc = (sc_desc or "").strip().lower()
    vbe = (vbe or "").strip().lower()

    indicator = f"Ability to {verb} {sc_desc} {condition} {criterion} while demonstrating {vbe}.".strip()

    rubric = {
        "indicator": indicator,
        "excellent": f"Consistently {criterion} and highly proficient in applying {sc_desc} {condition}; clear adherence to {vbe}.",
        "good": f"Generally {criterion} and competent in applying {sc_desc} {condition}; minor gaps in demonstrating {vbe}.",
        "satisfactory": f"Partially meets {criterion}; applies {sc_desc} {condition} with inconsistencies; moderate demonstration of {vbe}.",
        "poor": f"Does not meet {criterion}; unable to apply {sc_desc} {condition}; weak demonstration of {vbe}."
    }
    return rubric

# ------------------------------------------------------------
# CLO TABLE I/O
# ------------------------------------------------------------
def read_clo_table():
    try:
        return pd.read_excel(WORKBOOK_PATH, sheet_name="CLO_Table", engine="openpyxl")
    except Exception:
        return pd.DataFrame()

def write_clo_table(df: pd.DataFrame):
    book = load_workbook(WORKBOOK_PATH)
    if "CLO_Table" in book.sheetnames:
        del book["CLO_Table"]
    with pd.ExcelWriter(WORKBOOK_PATH, engine="openpyxl", mode="a") as writer:
        writer._book = book  # type: ignore
        df.to_excel(writer, sheet_name="CLO_Table", index=False)

# ------------------------------------------------------------
# ROUTES
# ------------------------------------------------------------
@app.route("/")
def index():
    profile = request.args.get("profile", "").strip().lower()
    df_map = get_mapping_dict(profile)
    plos = df_map[df_map.columns[0]].dropna().astype(str).tolist() if not df_map.empty else []
    df_ct = read_clo_table()
    table_html = df_ct.to_html(classes="table table-striped table-sm", index=False) if not df_ct.empty else "<p>No CLO records yet.</p>"
    return render_template("generator.html", plos=plos, table_html=table_html, profile=profile)

@app.route("/api/get_meta/<plo>/<bloom>")
def api_get_meta(plo, bloom):
    """Auto-fill mapping + short condition/criterion + assessment/evidence."""
    profile = request.args.get("profile", "").strip().lower()
    details = get_plo_details(plo, profile) or {}

    domain = (details.get("Domain", "") or "").strip().lower()
    bk = (bloom or "").strip()

    if domain in ONEWORD_META and bk in ONEWORD_META[domain]:
        meta = ONEWORD_META[domain][bk]
        crit = meta["criterion"]
        cond = f"{choose_prefix(domain)} {meta['condition']}"
    else:
        crit, cond_phrase = get_criterion_phrase(domain, bk)
        cond = cond_phrase or get_default_condition(domain)

    assessment, evidence = get_assessment_and_evidence(bk, domain)

    return jsonify({
        "sc_code": details.get("SC_Code", ""),
        "sc_desc": details.get("SC_Desc", ""),
        "vbe": details.get("VBE", ""),
        "domain": domain,
        "criterion": crit,
        "condition": cond,
        "assessment": assessment,
        "evidence": evidence
    })

@app.route("/generate", methods=["POST"])
def generate():
    profile = request.args.get("profile", "").strip().lower()
    plo = request.form.get("plo")
    bloom = request.form.get("bloom")
    verb = request.form.get("verb")
    content = request.form.get("content")
    course = request.form.get("course")
    cw = request.form.get("cw")
    include_condition_flag = bool(request.form.get("include_condition"))
    vbe_style = request.form.get("vbe_style") or "guided"

    details = get_plo_details(plo, profile)
    if not details:
        return jsonify({"error": "PLO not found"}), 400

    domain = (details["Domain"] or "").lower()

    # Criterion & condition (excel/default)
    criterion, condition_raw = get_criterion_phrase(domain, bloom)
    if not condition_raw:
        condition_raw = get_default_condition(domain)

    # ONEWORD override
    if domain in ONEWORD_META and bloom in ONEWORD_META[domain]:
        criterion = ONEWORD_META[domain][bloom]["criterion"]
        condition_word = ONEWORD_META[domain][bloom]["condition"]
    else:
        # fallback: take the phrase without when/by prefix
        cw_l = (condition_raw or "").strip().lower()
        if cw_l.startswith(("when ", "by ")):
            condition_word = condition_raw.split(" ", 1)[1].strip()
        else:
            condition_word = condition_raw

    # optionally remove condition
    condition_for_sentence = "" if not include_condition_flag else condition_word

    # Build main CLO
    clo = construct_clo_sentence(
        verb=verb,
        content=content,
        sc_desc=details["SC_Desc"],
        condition=condition_for_sentence,
        criterion=criterion,
        vbe_text=details["VBE"],
        vbe_style=vbe_style,
        domain=domain
    )

    # Build variants A/B/C
    clo_a, clo_b, clo_c = make_clo_variants(
        verb=verb,
        content=content,
        sc_desc=details["SC_Desc"],
        condition_word=condition_word,
        criterion=criterion,
        domain=domain,
        vbe_text=details["VBE"],
        vbe_style=vbe_style
    )
    clo_options = {"A": clo_a, "B": clo_b, "C": clo_c}

    # Assessment + evidence
    assessment, evidence = get_assessment_and_evidence(bloom, domain)

    # Rubric JSON
    rubric = rubric_generator(
        clo=clo,
        verb=verb,
        criterion=criterion,
        condition=condition_word if include_condition_flag else "",
        sc_desc=details["SC_Desc"],
        vbe=details["VBE"]
    )

    # Save to table
    df = read_clo_table()
    new_row = {
        "ID": len(df) + 1 if not df.empty else 1,
        "Time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "Course": course,
        "PLO": plo,
        "Bloom": bloom,
        "FullCLO": clo,
        "Mapping (SC + VBE)": f"{details['SC_Code']} — {details['VBE']}",
        "Assessment Methods": assessment,
        "Evidence of Assessment": evidence,
        "Coursework Assessment Percentage (%)": cw,
        "Profile": profile
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    write_clo_table(df)

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
    df = load_sheet_df(sheetmap.get(domain))
    if df.empty:
        return jsonify([])
    return jsonify(df.iloc[:, 0].dropna().astype(str).tolist())

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
    df = load_sheet_df(sheetmap.get(domain))
    if df.empty:
        return jsonify([])
    mask = df.iloc[:, 0].astype(str).str.lower() == str(bloom).lower()
    if not mask.any():
        return jsonify([])
    return jsonify([v.strip() for v in str(df[mask].iloc[0, 1]).split(",")])

@app.route("/api/debug_plo/<plo>")
def api_debug_plo(plo):
    profile = request.args.get("profile", "")
    return jsonify({
        "plo": plo,
        "details": get_plo_details(plo, profile) or {},
        "exists": bool(get_plo_details(plo, profile))
    })

@app.route("/reset_table")
def reset_table():
    df = pd.DataFrame(columns=[
        "ID","Time","Course","PLO","Bloom","FullCLO",
        "Mapping (SC + VBE)","Assessment Methods","Evidence of Assessment",
        "Coursework Assessment Percentage (%)","Profile"
    ])
    book = load_workbook(WORKBOOK_PATH)
    if "CLO_Table" in book.sheetnames:
        del book["CLO_Table"]
    with pd.ExcelWriter(WORKBOOK_PATH, engine="openpyxl", mode="a") as writer:
        writer._book = book  # type: ignore
        df.to_excel(writer, sheet_name="CLO_Table", index=False)
    return redirect(url_for("index"))

@app.route("/download")
def download():
    df = read_clo_table()
    if df.empty:
        return "<p>No CLO table to download.</p>"
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="CLO_Table")
    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name="CLO_Table.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.route("/download_rubric")
def download_rubric():
    # Build a rubric workbook from current CLO_Table
    df = read_clo_table()
    if df.empty:
        return "<p>No CLO table available.</p>"

    rows = []
    for _, r in df.iterrows():
        clo = r.get("FullCLO", "")
        plo = r.get("PLO", "")
        profile = r.get("Profile", "")
        bloom = r.get("Bloom", "")
        det = get_plo_details(plo, profile) or {}
        domain = (det.get("Domain", "") or "").lower()

        crit, cond = get_criterion_phrase(domain, bloom)
        if domain in ONEWORD_META and bloom in ONEWORD_META[domain]:
            crit = ONEWORD_META[domain][bloom]["criterion"]
            cond = ONEWORD_META[domain][bloom]["condition"]

        rub = rubric_generator(
            clo=clo,
            verb="perform",
            criterion=crit,
            condition=cond,
            sc_desc=det.get("SC_Desc", ""),
            vbe=det.get("VBE", "")
        )
        rows.append({
            "CLO": clo,
            "Performance Indicator": rub["indicator"],
            "Excellent": rub["excellent"],
            "Good": rub["good"],
            "Satisfactory": rub["satisfactory"],
            "Poor": rub["poor"]
        })

    rubdf = pd.DataFrame(rows)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        rubdf.to_excel(writer, sheet_name="Rubric", index=False)
    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name="Rubric.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

if __name__ == "__main__":
    app.run(debug=True)
