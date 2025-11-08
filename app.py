from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
import pandas as pd
import os
from datetime import datetime
from openpyxl import load_workbook
from io import BytesIO

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
# LOAD EXCEL SHEET
# ------------------------------------------------------------
def load_sheet_df(sheet_name):
    try:
        return pd.read_excel(WORKBOOK_PATH, sheet_name=sheet_name, engine="openpyxl")
    except Exception:
        return pd.DataFrame()

# ------------------------------------------------------------
# GET MAPPING TABLE
# ------------------------------------------------------------
def get_mapping_dict(profile=None):
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

    # Normalize column names (remove spaces, lowercase)
    colmap = {c.strip().lower().replace(" ", ""): c for c in df.columns}

    # Identify columns regardless of format in Excel
    col_plo = list(df.columns)[0]                 # first column is always PLO
    col_sc = colmap.get("sccode")
    col_desc = colmap.get("scdescription")
    col_vbe = colmap.get("vbe")
    col_domain = colmap.get("domain")

    # Match PLO
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

# ---------- Polishing helpers ----------
def polish_condition(condition: str, remove_condition: bool, profile: str = "", bloom: str = "") -> str:
    if remove_condition:
        return ""
    c = (condition or "").strip()
    if not c:
        return ""
    # normalise opener (prefer “in/when/during/under/by” once only)
    starters = ("in ", "when ", "during ", "under ", "by ", "based ")
    if not c.lower().startswith(starters):
        # heuristic: analysis/synthesis → “when”, practice → “in/under”
        if str(bloom).lower() in ("analyze", "analyse", "evaluate", "evaluation", "create", "synthesize", "synthesis"):
            c = "when " + c
        else:
            c = "in " + c
    # spacing
    return " ".join(c.split())

def vbe_phrase(vbe: str, style: str = "guided") -> str:
    vbe = (vbe or "").strip()
    if not vbe:
        return ""
    style = (style or "guided").lower()
    if style == "accordance":
        return f"in accordance with {vbe.lower()}"
    if style == "aligned":
        return f"aligned with {vbe.lower()}"
    # default “C” = guided
    return f"guided by {vbe.lower()}"

def sc_snippet(sc_desc: str) -> str:
    return f"using {sc_desc.lower()}" if sc_desc else ""

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
# CLO SENTENCE BUILDER
# ------------------------------------------------------------
def construct_clo_sentence(verb, content, sc_desc, condition, criterion, vbe_text, vbe_style="guided"):
    parts = []

    # Verb in lower then sentence-case later
    base = f"{str(verb).strip().lower()} {str(content).strip()}"
    parts.append(base)

    # SC
    sc_part = sc_snippet(sc_desc)
    if sc_part:
        parts.append(sc_part)

    # Hybrid “by applying …” if the criterion sounds like performance standard
    # otherwise we just append criterion as-is.
    crit = (criterion or "").strip()
    if crit:
        # light polish: ensure not double “by”
        if not crit.lower().startswith(("by ", "to ", "with ", "at ", "according ", "in ")):
            crit = "to " + crit
        parts.append(crit)

    # Condition (optional, already polished)
    if condition:
        parts.append(condition)

    # VBE phrase (Option C default = guided by)
    vbe_part = vbe_phrase(vbe_text, vbe_style)
    if vbe_part:
        parts.append(vbe_part)

    sentence = " ".join([p for p in parts if p]).strip()
    if sentence:
        sentence = sentence[0].upper() + sentence[1:]
        if not sentence.endswith("."):
            sentence += "."
    return sentence

def variants(verb, content, sc_desc, condition, criterion, vbe_text, vbe_style="guided"):
    """Return 3 polished alternatives (A/B/C) including a hybrid."""
    # A: concise, no condition
    a = construct_clo_sentence(verb, content, sc_desc, "", criterion, vbe_text, vbe_style)

    # B: include condition
    b = construct_clo_sentence(verb, content, sc_desc, condition, criterion, vbe_text, vbe_style)

    # C: hybrid wording: “… by applying …” + condition
    # reframe criterion to a doing-action when possible
    crit = (criterion or "").strip()
    if crit and not crit.lower().startswith("by "):
        crit_h = "by " + crit.lstrip("to ").lstrip()
    else:
        crit_h = crit
    c = construct_clo_sentence(verb, content, sc_desc, condition, crit_h, vbe_text, vbe_style)
    # ------------------------------------------------------------
# CLO VARIANT GENERATOR (A/B/C OPTIONS)
# ------------------------------------------------------------

def make_clo_variants(verb, content, sc_desc, condition_word, criterion, domain, vbe_text):
    """
    Builds A/B/C CLO variants automatically using your universal rules.
    """

    # Prefix rules (psychomotor prefers "by")
    prefix_when = "when"
    prefix_by = "by"
    default_prefix = prefix_by if domain == "psychomotor" else prefix_when

    # Variant A — Method-focused ("by")
    clo_a = (
        f"{verb} {content} using {sc_desc} "
        f"by {condition_word} {criterion} guided by {vbe_text}."
    ).replace("  ", " ").strip().capitalize()

    # Variant B — Context-focused ("when")
    clo_b = (
        f"{verb} {content} using {sc_desc} "
        f"when {condition_word} {criterion} guided by {vbe_text}."
    ).replace("  ", " ").strip().capitalize()

    # Variant C — Hybrid
    clo_c = (
        f"{verb} {content} using {sc_desc} "
        f"{default_prefix} {condition_word} {criterion} guided by {vbe_text}."
    ).replace("  ", " ").strip().capitalize()

    return clo_a, clo_b, clo_c


    return [a, b, c]

# ------------------------------------------------------------
# CLO TABLE
# ------------------------------------------------------------
def read_clo_table():
    try:
        return pd.read_excel(WORKBOOK_PATH, sheet_name="CLO_Table", engine="openpyxl")
    except Exception:
        return pd.DataFrame()

def write_clo_table(df):
    book = load_workbook(WORKBOOK_PATH)
    if "CLO_Table" in book.sheetnames:
        del book["CLO_Table"]
    with pd.ExcelWriter(WORKBOOK_PATH, engine="openpyxl", mode="a") as writer:
        writer._book = book
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
    """
    Meta endpoint used by UI to auto-fill:
    - SC Code / SC Description
    - VBE
    - Domain
    - ONE-WORD criterion
    - ONE-WORD condition (auto 'when' or 'by')
    - Assessment & Evidence
    """

    profile = request.args.get("profile", "").strip().lower()
    details = get_plo_details(plo, profile) or {}

    domain = (details.get("Domain", "") or "").strip().lower()
    bloom_key = (bloom or "").strip()

    # ------------------------------------------------------------
    # ✅ One-word Criterion + Condition mapping (universal)
    # ------------------------------------------------------------
    ONEWORD_META = {
        "cognitive": {
            "Remember":   {"criterion": "accurately",    "condition": "interpreting"},
            "Understand": {"criterion": "coherently",    "condition": "interpreting"},
            "Apply":      {"criterion": "effectively",   "condition": "interpreting"},
            "Analyze":    {"criterion": "critically",    "condition": "interpreting"},
            "Evaluate":   {"criterion": "independently", "condition": "interpreting"},
            "Create":     {"criterion": "innovatively",  "condition": "interpreting"}
        },
        "affective": {
            "Receive":         {"criterion": "openly",         "condition": "engaging"},
            "Respond":         {"criterion": "responsibly",    "condition": "engaging"},
            "Value":           {"criterion": "sincerely",      "condition": "engaging"},
            "Organization":    {"criterion": "constructively", "condition": "engaging"},
            "Characterization":{"criterion": "ethically",      "condition": "engaging"}
        },
        "psychomotor": {
            "Perception":            {"criterion": "attentively", "condition": "performing"},
            "Set":                   {"criterion": "precisely",    "condition": "performing"},
            "Guided Response":       {"criterion": "controlled",   "condition": "performing"},
            "Mechanism":             {"criterion": "competently",  "condition": "performing"},
            "Complex Overt Response":{"criterion": "confidently",  "condition": "performing"},
            "Adaptation":            {"criterion": "safely",       "condition": "performing"},
            "Origination":           {"criterion": "creatively",   "condition": "performing"}
        }
    }

    # ------------------------------------------------------------
    # ✅ Decide "when" vs "by" automatically
    # ------------------------------------------------------------
    def choose_prefix(domain):
        if domain == "psychomotor":
            return "by"
        return "when"

    # ------------------------------------------------------------
    # ✅ Try one-word mapping first
    # ------------------------------------------------------------
    if domain in ONEWORD_META and bloom_key in ONEWORD_META[domain]:
        meta = ONEWORD_META[domain][bloom_key]
        oneword_criterion = meta["criterion"]
        oneword_condition = meta["condition"]
        prefix = choose_prefix(domain)
        polished_condition = f"{prefix} {oneword_condition}"
    else:
        # fallback to your Excel sheet Criterion
        crit, cond = get_criterion_phrase(domain, bloom_key)
        oneword_criterion = crit
        polished_condition = cond or get_default_condition(domain)

    # ------------------------------------------------------------
    # ✅ Assessment & Evidence (unchanged)
    # ------------------------------------------------------------
    assessment, evidence = get_assessment_and_evidence(bloom_key, domain)

    return jsonify({
        "sc_code": details.get("SC_Code", ""),
        "sc_desc": details.get("SC_Desc", ""),
        "vbe": details.get("VBE", ""),
        "domain": domain,
        "criterion": oneword_criterion,
        "condition": polished_condition,
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
    include_condition = (request.form.get("include_condition", "1") == "1")
    vbe_style = request.form.get("vbe_style", "guided")   # "guided" | "accordance" | "aligned"

    details = get_plo_details(plo, profile)
    if not details:
        return jsonify({"error": "PLO not found"}), 400

    domain = details["Domain"]

    criterion, condition_phrase = get_criterion_phrase(domain, bloom)
   # Get one-word JSON condition if available
if domain in ONEWORD_META and bloom in ONEWORD_META[domain]:
    condition_word = ONEWORD_META[domain][bloom]["condition"]
    criterion = ONEWORD_META[domain][bloom]["criterion"]
else:
    # fallback: extract the first verb from condition phrase
    condition_word = condition_phrase.split()[1] if len(condition_phrase.split()) > 1 else condition_phrase

    # Assessment/Evidence auto-fill
    assessment, evidence = get_assessment_and_evidence(bloom, domain)

    # Polish condition or remove if requested
    polished_condition = polish_oneword_condition(domain, mapping_condition)

    # Build variants (A/B/C)
    clo_options = variants(
        verb=verb,
        content=content,
        sc_desc=details["SC_Desc"],
        condition=polished_condition,
        criterion=criterion,
        vbe_text=details["VBE"],
        vbe_style=vbe_style
    )
    clo = clo_options[0]  # store A as the canonical record (shortest)

    # Save CLO into table
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

# ------------------------------------------------------------
# Build A/B/C CLO variants
# ------------------------------------------------------------
clo_a, clo_b, clo_c = make_clo_variants(
    verb=verb,
    content=content,
    sc_desc=details["SC_Desc"],
    condition_word=condition_word,
    criterion=criterion,
    domain=domain,
    vbe_text=details["VBE"]
)

# Package them for JSON output
clo_options = {
    "A": clo_a,
    "B": clo_b,
    "C": clo_c
}

# ------------------------------------------------------------
# Return JSON to front-end
# ------------------------------------------------------------
return jsonify({
    "clo": clo,
    "clo_options": clo_options,
    "assessment": assessment,
    "evidence": evidence,
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

    domain = details["Domain"].lower()
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

    domain = details["Domain"].lower()
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
        writer._book = book
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

if __name__ == "__main__":
    app.run(debug=True)




