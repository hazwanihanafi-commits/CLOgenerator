from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
import pandas as pd
import os
from datetime import datetime
from openpyxl import load_workbook
from io import BytesIO

app = Flask(__name__, template_folder="templates")

WORKBOOK_PATH = os.path.join(os.getcwd(), "SCLOG.xlsx")

# ------------------------------------------------------------
# ONE-WORD META
# ------------------------------------------------------------
ONEWORD_META = {
    "cognitive": {
        "Remember":  {"criterion": "accurately", "condition": "recalling information"},
        "Understand": {"criterion": "coherently", "condition": "explaining concepts"},
        "Apply": {"criterion": "effectively", "condition": "applying methods"},
        "Analyze": {"criterion": "critically", "condition": "evaluating information"},
        "Evaluate": {"criterion": "independently", "condition": "making judgments"},
        "Create": {"criterion": "innovatively", "condition": "generating ideas"}
    },
    "affective": {
        "Receive": {"criterion": "openly", "condition": "engaging respectfully"},
        "Respond": {"criterion": "responsibly", "condition": "participating actively"},
        "Value": {"criterion": "sincerely", "condition": "demonstrating values"},
        "Organization": {"criterion": "constructively", "condition": "balancing perspectives"},
        "Characterization": {"criterion": "ethically", "condition": "behaving professionally"}
    },
    "psychomotor": {
        "Perception": {"criterion": "accurately", "condition": "identifying cues"},
        "Set": {"criterion": "precisely", "condition": "preparing procedures"},
        "Guided Response": {"criterion": "under supervision", "condition": "practising skills"},
        "Mechanism": {"criterion": "competently", "condition": "performing techniques"},
        "Complex Overt Response": {"criterion": "efficiently", "condition": "executing tasks"},
        "Adaptation": {"criterion": "safely", "condition": "adjusting actions"},
        "Origination": {"criterion": "creatively", "condition": "developing procedures"}
    }
}

# ------------------------------------------------------------
# PROFILE → SHEET MAP
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
# HELPERS
# ------------------------------------------------------------
def load_sheet_df(sheet):
    try:
        return pd.read_excel(WORKBOOK_PATH, sheet_name=sheet, engine="openpyxl")
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

    col_plo = df.columns[0]
    mask = df[col_plo].astype(str).str.upper() == str(plo).upper()

    if not mask.any():
        return None

    row = df[mask].iloc[0]

    return {
        "PLO": row[col_plo],
        "SC_Code": row.get("SC Code", ""),
        "SC_Desc": row.get("SC Description", ""),
        "VBE": row.get("VBE", ""),
        "Domain": row.get("Domain", "")
    }

def get_criterion_phrase(domain, bloom):
    df = load_sheet_df("Criterion")
    if df.empty:
        return "", ""

    mask = (
        df.iloc[:, 0].astype(str).str.lower() == domain.lower() and
        df.iloc[:, 1].astype(str).str.lower() == bloom.lower()
    )
    if not mask.any():
        return "", ""

    row = df[mask].iloc[0]
    return str(row[2]).strip(), str(row[3]).strip()

def get_default_condition(domain):
    mapping = {
        "cognitive": "evaluating information",
        "affective": "engaging with others",
        "psychomotor": "performing tasks"
    }
    return mapping.get(domain, "")

def choose_prefix(domain):
    return "by" if domain == "psychomotor" else "when"

def build_condition(condition_word, domain):
    if not condition_word:
        return ""

    c = condition_word.strip()

    if c.lower().startswith(("when ", "by ")):
        c = c.split(" ", 1)[1].strip()

    prefix = choose_prefix(domain)
    return f"{prefix} {c}"

def sc_snippet(sc_desc):
    if not sc_desc:
        return ""
    sc = sc_desc.strip().lower()
    if sc.startswith("using "):
        return sc
    return f"using {sc}"

def vbe_phrase(vbe, style="guided"):
    if not vbe:
        return ""
    v = vbe.lower()
    if style == "accordance":
        return f"in accordance with {v}"
    if style == "aligned":
        return f"aligned with {v}"
    return f"guided by {v}"

# ------------------------------------------------------------
# BUILD CLO SENTENCE
# ------------------------------------------------------------
def construct_clo_sentence(verb, content, sc_desc, condition, criterion, vbe_text, vbe_style="guided"):
    verb = verb.strip().lower()
    content = content.strip()

    sc_part = sc_snippet(sc_desc)

    crit = criterion.strip()
    if crit and not crit.lower().startswith("to "):
        crit = f"to {crit}"

    sentence = f"{verb} {content}"

    if sc_part:
        sentence += f" {sc_part}"

    if condition:
        sentence += f" {condition}"

    if crit:
        sentence += f" {crit}"

    vp = vbe_phrase(vbe_text, vbe_style)
    if vp:
        sentence += f" {vp}"

    sentence = sentence.strip().capitalize()
    if not sentence.endswith("."):
        sentence += "."

    return sentence

# ------------------------------------------------------------
# CLO VARIANTS (A/B/C)
# ------------------------------------------------------------
def make_clo_variants(verb, content, sc_desc, condition_word, criterion, domain, vbe_text):
    prefix = choose_prefix(domain)
    cond = build_condition(condition_word, domain)

    sc = sc_snippet(sc_desc)
    vbe = vbe_phrase(vbe_text)

    # A: method-oriented
    a = f"{verb} {content} {sc} {cond} to {criterion} {vbe}".strip()

    # B: condition earlier
    b = f"{verb} {content} {cond} {sc} to {criterion} {vbe}".strip()

    # C: hybrid
    c = f"{verb} {content} {sc} {cond} to {criterion} {vbe}".strip()

    def clean(x):
        x = x.replace("  ", " ").strip().capitalize()
        if not x.endswith("."):
            x += "."
        return x

    return clean(a), clean(b), clean(c)

# ------------------------------------------------------------
# RUBRIC GENERATOR
# ------------------------------------------------------------
def rubric_generator(clo, verb, criterion, condition, sc_desc, vbe):
    indicator = (
        f"Ability to {verb.lower()} {sc_desc.lower()} {condition} "
        f"to {criterion} while demonstrating {vbe.lower()}."
    )

    return {
        "indicator": indicator,
        "excellent": f"Consistently {criterion} and applies {sc_desc.lower()} {condition} with strong adherence to {vbe.lower()}.",
        "good": f"Generally {criterion} and applies {sc_desc.lower()} {condition} with minor gaps.",
        "satisfactory": f"Partially able to apply {sc_desc.lower()} {condition}; performance is inconsistent.",
        "poor": f"Unable to apply {sc_desc.lower()} {condition}; does not meet expected standards."
    }

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
    profile = request.args.get("profile", "").strip().lower()

    # 1. Load SC/VBE/Domain from PLO mapping
    details = get_plo_details(plo, profile)
    if not details:
        return jsonify({})

    domain = (details.get("Domain") or "").strip()

    # 2. Criterion + Condition from Excel
    criterion, condition = get_criterion_phrase(domain, bloom)
    if not condition:
        condition = get_default_condition(domain)

    # 3. Assessment + Evidence from Excel
    assessment, evidence = get_assessment_and_evidence(bloom, domain)

    # 4. Return all meta for auto-fill
    return jsonify({
        "sc_code": details.get("SC_Code", ""),
        "sc_desc": details.get("SC_Desc", ""),
        "vbe": details.get("VBE", ""),
        "domain": details.get("Domain", ""),
        "condition": condition,
        "criterion": criterion,
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

    details = get_plo_details(plo, profile)
    domain = details["Domain"].lower()

    # condition + criterion
    criterion, cond_word = get_criterion_phrase(domain, bloom)
    if domain in ONEWORD_META and bloom in ONEWORD_META[domain]:
        criterion = ONEWORD_META[domain][bloom]["criterion"]
        cond_word = ONEWORD_META[domain][bloom]["condition"]

    condition = build_condition(cond_word, domain)

    # CLO sentence
    clo = construct_clo_sentence(
        verb, content, details["SC_Desc"], condition, criterion, details["VBE"]
    )

    # CLO variants
    clo_a, clo_b, clo_c = make_clo_variants(
        verb, content, details["SC_Desc"], cond_word, criterion, domain, details["VBE"]
    )

    # assessment + evidence
    assess, evid = get_assessment_and_evidence(bloom, domain)

    # rubric
    rubric = rubric_generator(
        clo, verb, criterion, condition, details["SC_Desc"], details["VBE"]
    )

    # write Excel row
    df = read_clo_table()
    new_row = {
        "ID": len(df) + 1 if not df.empty else 1,
        "Time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "Course": course,
        "PLO": plo,
        "Bloom": bloom,
        "FullCLO": clo,
        "Mapping (SC + VBE)": f"{details['SC_Code']} — {details['VBE']}",
        "Assessment Methods": assess,
        "Evidence of Assessment": evid,
        "Coursework Assessment Percentage (%)": cw,
        "Profile": profile
    }
    df = pd.concat([df, pd.DataFrame([new_row])])
    write_clo_table(df)

    return jsonify({
        "clo": clo,
        "clo_options": {"A": clo_a, "B": clo_b, "C": clo_c},
        "assessment": assess,
        "evidence": evid,
        "rubric": rubric,
        "sc_code": details["SC_Code"],
        "sc_desc": details["SC_Desc"],
        "vbe": details["VBE"],
        "domain": domain
    })

# ------------------------------------------------------------
# Excel Storage
# ------------------------------------------------------------
def read_clo_table():
    try:
        return pd.read_excel(WORKBOOK_PATH, sheet_name="CLO_Table", engine="openpyxl")
    except:
        return pd.DataFrame()

def write_clo_table(df):
    book = load_workbook(WORKBOOK_PATH)
    if "CLO_Table" in book.sheetnames:
        del book["CLO_Table"]
    with pd.ExcelWriter(WORKBOOK_PATH, engine="openpyxl", mode="a") as writer:
        writer._book = book
        df.to_excel(writer, sheet_name="CLO_Table", index=False)

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

# ------------------------------------------------------------
# Download Rubric
# ------------------------------------------------------------
@app.route("/download_rubric")
def download_rubric():
    df = read_clo_table()
    if df.empty:
        return "<p>No CLO table.</p>"

    rows = []
    for idx, row in df.iterrows():
        plo = row["PLO"]
        details = get_plo_details(plo, row.get("Profile", ""))
        domain = details.get("Domain", "")
        bloom = row["Bloom"]

        criterion, cond_word = get_criterion_phrase(domain, bloom)

        if domain in ONEWORD_META and bloom in ONEWORD_META[domain]:
            criterion = ONEWORD_META[domain][bloom]["criterion"]
            cond_word = ONEWORD_META[domain][bloom]["condition"]

        condition = build_condition(cond_word, domain)

        rubric = rubric_generator(
            row["FullCLO"], "apply", criterion, condition,
            details["SC_Desc"], details["VBE"]
        )

        rows.append({
            "CLO": row["FullCLO"],
            "Performance Indicator": rubric["indicator"],
            "Excellent": rubric["excellent"],
            "Good": rubric["good"],
            "Satisfactory": rubric["satisfactory"],
            "Poor": rubric["poor"]
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

# ------------------------------------------------------------
# Run
# ------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)

