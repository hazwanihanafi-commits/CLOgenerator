from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
import pandas as pd
import os
from datetime import datetime
from openpyxl import load_workbook
from io import BytesIO

app = Flask(__name__, template_folder="templates")

# ============================================================
# Paths
# ============================================================
WORKBOOK_PATH = os.path.join(os.getcwd(), "SCLOG.xlsx")

# ============================================================
# Universal one-word meta (Domain × Bloom)
# Used to override/standardize criterion + condition
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

# ============================================================
# Discipline → sheet map
# ============================================================
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
# Helpers: Excel I/O
# ============================================================
def load_sheet_df(sheet_name: str) -> pd.DataFrame:
    try:
        return pd.read_excel(WORKBOOK_PATH, sheet_name=sheet_name, engine="openpyxl")
    except Exception:
        return pd.DataFrame()

def get_mapping_dict(profile: str | None = None) -> pd.DataFrame:
    profile = (profile or "").strip().lower()
    sheet = PROFILE_SHEET_MAP.get(profile, "Mapping")
    df = load_sheet_df(sheet)
    if df.empty:
        return pd.DataFrame()
    df.columns = [str(c).strip() for c in df.columns]
    return df

def get_plo_details(plo: str, profile: str | None = None) -> dict | None:
    df = get_mapping_dict(profile)
    if df.empty:
        return None

    # Normalize column names
    colmap = {c.strip().lower().replace(" ", ""): c for c in df.columns}
    col_plo = list(df.columns)[0]          # assume first column is PLO
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
        "SC_Code": row.get(col_sc, "") if col_sc else "",
        "SC_Desc": row.get(col_desc, "") if col_desc else "",
        "VBE": row.get(col_vbe, "") if col_vbe else "",
        "Domain": row.get(col_domain, "") if col_domain else ""
    }

# ============================================================
# Criterion / Condition sources
# ============================================================
def get_criterion_phrase(domain: str, bloom: str) -> tuple[str, str]:
    """Reads Criterion sheet: Domain | Bloom | Criterion | Condition."""
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

def get_default_condition(domain: str) -> str:
    mapping = {
        "cognitive": "interpreting case tasks",
        "affective": "engaging with peers or stakeholders",
        "psychomotor": "executing practical procedures"
    }
    return mapping.get((domain or "").lower(), "")

# ============================================================
# Assessment & Evidence
# ============================================================
def get_assessment_and_evidence(bloom: str, domain: str) -> tuple[str, str]:
    domain = (domain or "").lower()
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

# ============================================================
# Polishing / builders
# ============================================================
def decide_connector(domain: str) -> str:
    """Psychomotor uses 'by', others 'when'."""
    return "by" if (domain or "").lower() == "psychomotor" else "when"

def sc_snippet(sc_desc: str) -> str:
    sc_desc = (sc_desc or "").strip()
    if not sc_desc:
        return ""
    val = sc_desc.lower()
    return val if val.startswith("using ") else f"using {val}"

def vbe_phrase(vbe: str, style: str = "guided") -> str:
    vbe = (vbe or "").strip()
    if not vbe:
        return ""
    style = (style or "guided").lower()
    if style == "accordance": return f"in accordance with {vbe.lower()}"
    if style == "aligned":    return f"aligned with {vbe.lower()}"
    return f"guided by {vbe.lower()}"

def construct_clo_sentence(
    verb: str,
    content: str,
    sc_desc: str,
    condition_core: str,
    criterion: str,
    vbe_text: str,
    domain: str = "",
    vbe_style: str = "guided"
) -> str:
    """
    FINAL ORDER (approved):
    Verb + Content + using SC + when/by condition + criterion + guided by VBE.
    """
    verb = (verb or "").strip().lower()
    content = (content or "").strip()
    criterion = (criterion or "").strip().rstrip(".")
    condition_core = (condition_core or "").strip()

    # Ensure condition_core is bare (no leading 'when/by')
    for lead in ("when ", "by "):
        if condition_core.lower().startswith(lead):
            condition_core = condition_core[len(lead):].strip()
            break

    connector = decide_connector(domain)
    condition = f"{connector} {condition_core}" if condition_core else ""

    parts = [
        f"{verb} {content}".strip(),
        sc_snippet(sc_desc),
        condition,
        criterion,
        vbe_phrase(vbe_text, vbe_style)
    ]
    sentence = " ".join([p for p in parts if p]).strip()
    if sentence:
        sentence = sentence[0].upper() + sentence[1:]
        if not sentence.endswith("."):
            sentence += "."
    return sentence

def make_clo_variants(
    verb: str, content: str, sc_desc: str, condition_core: str,
    criterion: str, domain: str, vbe_text: str, vbe_style: str = "guided"
) -> tuple[str, str, str]:
    """
    Returns three polished variants that still follow your approved order:
    A: 'when'
    B: 'by'
    C: Auto (domain-based)
    """
    # Bare condition_core only
    for lead in ("when ", "by "):
        if condition_core.lower().startswith(lead):
            condition_core = condition_core[len(lead):].strip()
            break

    a = construct_clo_sentence(verb, content, sc_desc, condition_core, criterion, vbe_text, domain="cognitive", vbe_style=vbe_style)  # force "when"
    b = construct_clo_sentence(verb, content, sc_desc, condition_core, criterion, vbe_text, domain="psychomotor", vbe_style=vbe_style) # force "by"
    c = construct_clo_sentence(verb, content, sc_desc, condition_core, criterion, vbe_text, domain=domain, vbe_style=vbe_style)        # auto by domain
    return a, b, c

def rubric_generator(clo: str, verb: str, criterion: str, condition_core: str, sc_desc: str, vbe: str) -> dict:
    """Simple rubric block aligned to CLO components."""
    # indicator
    connector = "by" if "perform" in (clo or "").lower() else "when"
    if condition_core.lower().startswith(("when ", "by ")):
        cond_text = condition_core
    else:
        cond_text = f"{connector} {condition_core}" if condition_core else ""

    indicator = f"Ability to {verb.lower()} {sc_desc.lower()} {cond_text} {criterion} while demonstrating {vbe.lower()}.".strip()

    return {
        "indicator": indicator,
        "excellent": f"Consistently {criterion} and applies {sc_desc.lower()} {cond_text} with clear adherence to {vbe.lower()}.",
        "good":      f"Generally {criterion} and applies {sc_desc.lower()} {cond_text} with minor gaps in {vbe.lower()}.",
        "satisfactory": f"Partially {criterion}; applies {sc_desc.lower()} {cond_text} but inconsistently demonstrates {vbe.lower()}.",
        "poor":      f"Does not {criterion}; unable to apply {sc_desc.lower()} {cond_text}; lacks adherence to {vbe.lower()}."
    }

# ============================================================
# CLO table (persist)
# ============================================================
def read_clo_table() -> pd.DataFrame:
    try:
        return pd.read_excel(WORKBOOK_PATH, sheet_name="CLO_Table", engine="openpyxl")
    except Exception:
        return pd.DataFrame()

def write_clo_table(df: pd.DataFrame) -> None:
    book = load_workbook(WORKBOOK_PATH)
    if "CLO_Table" in book.sheetnames:
        del book["CLO_Table"]
    with pd.ExcelWriter(WORKBOOK_PATH, engine="openpyxl", mode="a") as writer:
        writer._book = book
        df.to_excel(writer, sheet_name="CLO_Table", index=False)

# ============================================================
# Routes
# ============================================================
@app.route("/")
def index():
    profile = request.args.get("profile", "").strip().lower()
    df_map = get_mapping_dict(profile)
    plos = df_map[df_map.columns[0]].dropna().astype(str).tolist() if not df_map.empty else []
    df_ct = read_clo_table()
    table_html = df_ct.to_html(classes="table table-striped table-sm", index=False) if not df_ct.empty else "<p>No CLO records yet.</p>"
    return render_template("generator.html", plos=plos, table_html=table_html, profile=profile)

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
    df = load_sheet_df(sheetmap.get(domain, "Bloom_Cognitive"))
    if df.empty:
        return jsonify([])
    mask = df.iloc[:, 0].astype(str).str.lower() == str(bloom).lower()
    if not mask.any():
        return jsonify([])
    # Verbs expected in 2nd column as comma-separated
    verbs = [v.strip() for v in str(df[mask].iloc[0, 1]).split(",") if v.strip()]
    return jsonify(verbs)

@app.route("/api/get_meta/<plo>/<bloom>")
def api_get_meta(plo, bloom):
    """Auto-fill SC/VBE/Domain + standardized condition & criterion + assessment/evidence."""
    profile = request.args.get("profile", "").strip().lower()
    details = get_plo_details(plo, profile) or {}
    domain = (details.get("Domain", "") or "").strip().lower()
    bloom_key = (bloom or "").strip()

    # Try one-word override, else Excel
    if domain in ONEWORD_META and bloom_key in ONEWORD_META[domain]:
        meta = ONEWORD_META[domain][bloom_key]
        criterion = meta["criterion"]
        condition_core = meta["condition"]
    else:
        crit, cond = get_criterion_phrase(domain, bloom_key)
        criterion = crit or ""
        condition_core = cond or get_default_condition(domain)

    # Prefix condition now (so UI can show directly)
    condition = f"{decide_connector(domain)} {condition_core}" if condition_core else ""

    assessment, evidence = get_assessment_and_evidence(bloom_key, domain)

    return jsonify({
        "sc_code": details.get("SC_Code", ""),
        "sc_desc": details.get("SC_Desc", ""),
        "vbe": details.get("VBE", ""),
        "domain": domain,
        "criterion": criterion,
        "condition": condition,   # already prefixed with when/by
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
    vbe_style = request.form.get("vbe_style", "guided")

    # Retrieve SC + VBE + Domain
    details = get_plo_details(plo, profile)
    if not details:
        return jsonify({"error": "PLO not found"}), 400

    domain = details["Domain"].lower()

    # ----------------------------------------------------
    # CONDITION + CRITERION
    # ----------------------------------------------------
    criterion, condition_raw = get_criterion_phrase(domain, bloom)
    if not condition_raw:
        condition_raw = get_default_condition(domain)

    # ONE-WORD meta priority
    if domain in ONEWORD_META and bloom in ONEWORD_META[domain]:
        criterion = ONEWORD_META[domain][bloom]["criterion"]
        condition_core = ONEWORD_META[domain][bloom]["condition"]
    else:
        condition_core = condition_raw

    # ----------------------------------------------------
    # MAIN CLO (uses NEW parameter name: condition_core)
    # ----------------------------------------------------
    clo = construct_clo_sentence(
        verb=verb,
        content=content,
        sc_desc=details["SC_Desc"],
        condition_core=condition_core,
        criterion=criterion,
        vbe_text=details["VBE"],
        domain=domain,
        vbe_style=vbe_style
    )

    # ----------------------------------------------------
    # VARIANTS (A/B/C)
    # ----------------------------------------------------
    clo_a, clo_b, clo_c = make_clo_variants(
        verb=verb,
        content=content,
        sc_desc=details["SC_Desc"],
        condition_core=condition_core,
        criterion=criterion,
        domain=domain,
        vbe_text=details["VBE"],
        vbe_style=vbe_style
    )
    clo_options = {"A": clo_a, "B": clo_b, "C": clo_c}

    # ----------------------------------------------------
    # ASSESSMENT + EVIDENCE
    # ----------------------------------------------------
    assessment, evidence = get_assessment_and_evidence(bloom, domain)

    # ----------------------------------------------------
    # RUBRIC
    # ----------------------------------------------------
def rubric_generator(clo, verb, criterion, condition, sc_desc, vbe):
    """
    Builds a complete rubric block for the CLO.
    Returns dictionary structured for both Excel export and frontend display.
    """

    verb = (verb or "").strip()
    criterion = (criterion or "").strip()
    condition = (condition or "").strip()
    sc_desc = (sc_desc or "").strip()
    vbe = (vbe or "").strip()

    # --------------------------
    # PERFORMANCE INDICATOR
    # --------------------------
    indicator = (
        f"Ability to {verb.lower()} {sc_desc.lower()} {condition} "
        f"{criterion} while demonstrating {vbe.lower()}."
    ).strip()

    # --------------------------
    # RUBRIC LEVEL DESCRIPTORS
    # --------------------------
    rubric = {
        "indicator": indicator,
        "excellent": (
            f"Consistently {criterion} and highly proficient in applying "
            f"{sc_desc.lower()} {condition}, with clear adherence to {vbe.lower()}."
        ),
        "good": (
            f"Generally {criterion} and competent in applying {sc_desc.lower()} "
            f"{condition}, with minor gaps in demonstrating {vbe.lower()}."
        ),
        "satisfactory": (
            f"Shows partial ability to apply {sc_desc.lower()} {condition}, "
            f"but performance is inconsistent and only moderately {criterion}."
        ),
        "poor": (
            f"Unable to adequately apply {sc_desc.lower()} {condition}; "
            f"does not meet expected standards for {vbe.lower()}."
        )
    }

    return rubric

    # ----------------------------------------------------
    # SAVE TABLE
    # ----------------------------------------------------
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

    # ----------------------------------------------------
    # RETURN JSON
    # ----------------------------------------------------
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


@app.route("/api/debug_plo/<plo>")
def api_debug_plo(plo):
    profile = request.args.get("profile","")
    info = get_plo_details(plo, profile) or {}
    return jsonify({
        "plo": plo,
        "details": info,
        "exists": bool(info)
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
        writer._book = book
        df.to_excel(writer, sheet_name="CLO_Table", index=False)
    return redirect(url_for("index"))

@app.route("/download")
def download():
    df = read_clo_table()
    if df.empty:
        return "<p>No CLO table to download.</p>"
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="CLO_Table")
    out.seek(0)
    return send_file(
        out,
        as_attachment=True,
        download_name="CLO_Table.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.route("/download_rubric")
def download_rubric():
    df = read_clo_table()
    if df.empty:
        return "<p>No CLO table available.</p>"

    rows = []
    for _, row in df.iterrows():
        plo = row.get("PLO", "")
        details = get_plo_details(str(plo), row.get("Profile", "")) or {}
        domain = (details.get("Domain", "") or "").lower()
        bloom = row.get("Bloom", "")

        # Criterion & condition for rubric
        if domain in ONEWORD_META and bloom in ONEWORD_META[domain]:
            criterion = ONEWORD_META[domain][bloom]["criterion"]
            condition_core = ONEWORD_META[domain][bloom]["condition"]
        else:
            crit, cond = get_criterion_phrase(domain, bloom)
            criterion = crit or ""
            condition_core = cond or get_default_condition(domain)

        rubric = rubric_generator(
        clo,
        verb,
        criterion,
        condition,
        details["SC_Desc"],
        details["VBE"]
        )

        rows.append({
            "CLO": row.get("FullCLO", ""),
            "Performance Indicator": rub["indicator"],
            "Excellent": rub["excellent"],
            "Good": rub["good"],
            "Satisfactory": rub["satisfactory"],
            "Poor": rub["poor"]
        })

    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        pd.DataFrame(rows).to_excel(writer, index=False, sheet_name="Rubric")
    out.seek(0)
    return send_file(
        out,
        as_attachment=True,
        download_name="Rubric.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ============================================================
# Run (local)
# ============================================================
if __name__ == "__main__":
    app.run(debug=True)











