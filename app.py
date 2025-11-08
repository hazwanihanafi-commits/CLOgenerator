from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
import pandas as pd
import os
from datetime import datetime
from openpyxl import load_workbook
from io import BytesIO

app = Flask(__name__, template_folder="templates")

WORKBOOK_PATH = os.path.join(os.getcwd(), "SCLOG.xlsx")

# -----------------------------
# Load Sheet Helper
# -----------------------------
def load_sheet_df(sheet_name):
    try:
        return pd.read_excel(WORKBOOK_PATH, sheet_name=sheet_name, engine="openpyxl")
    except:
        return pd.DataFrame()


# -----------------------------
# MULTI-DISCIPLINE MAPPING
# -----------------------------
# --- SHEET MAP (7 disciplines) ---
PROFILE_SHEETS = {
    "": "Mapping",               # default
    "health": "Mapping_health",
    "sc": "Mapping_sc",
    "eng": "Mapping_eng",
    "socs": "Mapping_socs",
    "edu": "Mapping_edu",
    "bus": "Mapping_bus",
    "arts": "Mapping_arts",
}

def load_sheet_df(sheet_name):
    try:
        return pd.read_excel(WORKBOOK_PATH, sheet_name=sheet_name, engine="openpyxl")
    except Exception:
        return pd.DataFrame()

def get_mapping_dict(profile: str | None) -> pd.DataFrame:
    """Try the profile sheet, then fall back to default Mapping if missing/empty."""
    profile = (profile or "").strip().lower()
    sheet = PROFILE_SHEETS.get(profile, "Mapping")

    df = load_sheet_df(sheet)
    if df.empty and sheet != "Mapping":
        # fallback to default Mapping if requested sheet missing
        df = load_sheet_df("Mapping")

    if df.empty:
        return pd.DataFrame()

    df.columns = [str(c).strip() for c in df.columns]
    return df

def get_plo_details(plo: str, profile: str | None):
    df = get_mapping_dict(profile)
    if df.empty:
        return None
    keycol = df.columns[0]
    mask = df[keycol].astype(str).str.strip().str.upper() == str(plo).strip().upper()
    if not mask.any():
        return None
    row = df[mask].iloc[0]
    cols = {c.lower(): c for c in df.columns}
    return {
        "PLO": row[keycol],
        "SC_Code": row.get(cols.get("sc code"), ""),
        "SC_Desc": row.get(cols.get("sc description"), ""),
        "VBE": row.get(cols.get("vbe"), ""),
        "Domain": row.get(cols.get("domain"), ""),
    }

def get_criterion_phrase(domain, bloom):
    df = load_sheet_df("Criterion")
    if df.empty:
        return "", ""
    df.columns = [str(c).strip() for c in df.columns]
    dom_col = next((c for c in df.columns if "domain" in c.lower()), None)
    bloom_col = next((c for c in df.columns if "bloom" in c.lower()), None)
    crit_col = next((c for c in df.columns if "criterion" in c.lower()), None)
    cond_col = next((c for c in df.columns if "condition" in c.lower()), None)
    if not all([dom_col, bloom_col, crit_col, cond_col]):
        return "", ""
    mask = (df[dom_col].astype(str).str.lower() == str(domain).lower()) & \
           (df[bloom_col].astype(str).str.lower() == str(bloom).lower())
    if not mask.any():
        return "", ""
    row = df[mask].iloc[0]
    return str(row.get(crit_col, "")), str(row.get(cond_col, ""))

def get_default_condition(domain):
    mapping = {
        "cognitive": "based on case scenarios or clinical data",
        "affective": "during clinical or group activities",
        "psychomotor": "under supervised practical conditions",
    }
    return mapping.get(str(domain).strip().lower(), "")

def get_assessment_and_evidence(bloom, domain):
    domain_lower = str(domain).lower()
    sheet = "Assess_Affective_Psychomotor" if domain_lower in ("affective", "psychomotor") else "Bloom_Assessments"
    df = load_sheet_df(sheet)
    if df.empty:
        return "", ""
    df.columns = [c.strip() for c in df.columns]
    bloom_col, assess_col, evid_col = df.columns[:3]
    mask = df[bloom_col].astype(str).str.strip().str.lower() == str(bloom).strip().lower()
    if not mask.any():
        return "", ""
    row = df[mask].iloc[0]
    return str(row.get(assess_col, "")), str(row.get(evid_col, ""))

def construct_clo_sentence(verb, content, sc_desc, condition, criterion, vbe):
    text = f"{verb} {content}"
    if sc_desc: text += f" with {sc_desc.lower()}"
    if condition: text += f" {condition}"
    if criterion: text += f" {criterion}"
    if vbe: text += f" guided by {vbe.lower()}"
    text = text.strip()
    if text and not text.endswith("."):
        text = text[0].upper() + text[1:] + "."
    return text

def read_clo_table():
    try:
        return pd.read_excel(WORKBOOK_PATH, sheet_name="CLO_Table", engine="openpyxl")
    except Exception:
        return pd.DataFrame()

def write_clo_table(df):
    try:
        book = load_workbook(WORKBOOK_PATH)
        if "CLO_Table" in book.sheetnames:
            del book["CLO_Table"]
        with pd.ExcelWriter(WORKBOOK_PATH, engine="openpyxl", mode="a") as writer:
            writer._book = book
            df.to_excel(writer, sheet_name="CLO_Table", index=False)
    except Exception as e:
        print("Error writing CLO_Table:", e)

# ------------------ ROUTES ------------------

@app.route("/")
def index():
    profile = request.args.get("profile", "").strip().lower() or ""
    df_map = get_mapping_dict(profile)
    plos = df_map[df_map.columns[0]].dropna().astype(str).tolist() if not df_map.empty else []
    df_ct = read_clo_table()
    table_html = df_ct.to_html(classes="table table-striped table-sm", index=False) if not df_ct.empty else "<p>No CLO records yet.</p>"
    return render_template("generator.html", plos=plos, table_html=table_html, profile=profile)

@app.route("/generate", methods=["POST"])
def generate():
    # IMPORTANT: keep the profile (from query string or hidden input)
    profile = (request.args.get("profile") or request.form.get("profile") or "").strip().lower()

    plo = request.form.get("plo")
    bloom = request.form.get("bloom")
    verb = request.form.get("verb")
    content = request.form.get("content")
    course = request.form.get("course")
    cw = request.form.get("cw")

    details = get_plo_details(plo, profile)
    if not details:
        return jsonify({"error": "PLO not found for selected discipline"}), 400

    domain = details.get("Domain", "")
    sc_code = details.get("SC_Code", "")
    sc_desc = details.get("SC_Desc", "")
    vbe = details.get("VBE", "")

    criterion, condition = get_criterion_phrase(domain, bloom)
    if not condition:
        condition = get_default_condition(domain)

    assessment, evidence = get_assessment_and_evidence(bloom, domain)
    clo = construct_clo_sentence(verb, content, sc_desc, condition, criterion, vbe)

    # save to Excel
    df = read_clo_table()
    new_row = {
        "ID": len(df) + 1 if not df.empty else 1,
        "Time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "Course": course,
        "PLO": plo,
        "Bloom": bloom,
        "FullCLO": clo,
        "Mapping (SC + VBE)": f"{sc_code} — {vbe}",
        "Assessment Methods": assessment,
        "Evidence of Assessment": evidence,
        "Coursework Assessment Percentage (%)": cw,
        "Profile": profile or "",
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    write_clo_table(df)

    return jsonify({"clo": clo, "assessment": assessment, "evidence": evidence})

# Populate blooms based on PLO + profile
@app.route("/api/get_blooms/<plo>")
def api_get_blooms(plo):
    profile = request.args.get("profile", "").strip().lower()
    details = get_plo_details(plo, profile)
    if not details:
        return jsonify([])
    domain = details.get("Domain", "").strip().lower()
    sheet = {"cognitive": "Bloom_Cognitive", "affective": "Bloom_Affective", "psychomotor": "Bloom_Psychomotor"}.get(domain)
    df = load_sheet_df(sheet)
    if df.empty:
        return jsonify([])
    blooms = df.iloc[:, 0].dropna().astype(str).str.strip().tolist()
    return jsonify(blooms)

# Populate verbs based on PLO + bloom + profile
@app.route("/api/get_verbs/<plo>/<bloom>")
def api_get_verbs(plo, bloom):
    profile = request.args.get("profile", "").strip().lower()
    details = get_plo_details(plo, profile)
    if not details:
        return jsonify([])
    domain = details.get("Domain", "").strip().lower()
    sheet = {"cognitive": "Bloom_Cognitive", "affective": "Bloom_Affective", "psychomotor": "Bloom_Psychomotor"}.get(domain)
    df = load_sheet_df(sheet)
    if df.empty:
        return jsonify([])
    mask = df.iloc[:, 0].astype(str).str.strip().str.lower() == str(bloom).strip().lower()
    if not mask.any():
        return jsonify([])
    raw = str(df.loc[mask].iloc[0, 1])
    verbs = [v.strip() for v in raw.split(",") if v.strip()]
    return jsonify(verbs)

# NEW: meta endpoint to auto-fill condition / criterion / assessment / evidence on Bloom change
@app.route("/api/get_meta/<plo>/<bloom>")
def api_get_meta(plo, bloom):
    profile = request.args.get("profile", "").strip().lower()
    details = get_plo_details(plo, profile)
    if not details:
        return jsonify({})
    domain = details.get("Domain", "")
    criterion, condition = get_criterion_phrase(domain, bloom)
    if not condition:
        condition = get_default_condition(domain)
    assessment, evidence = get_assessment_and_evidence(bloom, domain)
    return jsonify({
        "domain": domain,
        "criterion": criterion,
        "condition": condition,
        "assessment": assessment,
        "evidence": evidence
    })

@app.route("/download")
def download():
    df = read_clo_table()
    if df.empty:
        return "<p>No CLO table to download.</p>"
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="CLO_Table", index=False)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name="CLO_Table.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.route("/reset_table")
def reset_table():
    df_empty = pd.DataFrame(columns=[
        "ID","Time","Course","PLO","Bloom","FullCLO",
        "Mapping (SC + VBE)","Assessment Methods","Evidence of Assessment",
        "Coursework Assessment Percentage (%)","Profile"
    ])
    book = load_workbook(WORKBOOK_PATH)
    if "CLO_Table" in book.sheetnames:
        del book["CLO_Table"]
    with pd.ExcelWriter(WORKBOOK_PATH, engine="openpyxl", mode="a") as writer:
        writer._book = book
        df_empty.to_excel(writer, sheet_name="CLO_Table", index=False)
    return redirect(url_for("index"))

# -----------------------------
# API ENDPOINTS
# -----------------------------
@app.route("/api/get_blooms/<plo>")
def api_get_blooms(plo):
    profile = request.args.get("profile", "").strip().lower() or ""
    details = get_plo_details(plo, profile)
    if not details:
        return jsonify([])

    domain = details.get("Domain", "").lower()
    sheet = {
        "cognitive": "Bloom_Cognitive",
        "affective": "Bloom_Affective",
        "psychomotor": "Bloom_Psychomotor"
    }.get(domain)

    df = load_sheet_df(sheet)
    if df.empty:
        return jsonify([])

    blooms = df.iloc[:, 0].dropna().astype(str).tolist()
    return jsonify(blooms)


@app.route("/api/get_verbs/<plo>/<bloom>")
def api_get_verbs(plo, bloom):
    profile = request.args.get("profile", "").strip().lower() or ""
    details = get_plo_details(plo, profile)
    if not details:
        return jsonify([])

    domain = details.get("Domain", "").lower()
    sheet = {
        "cognitive": "Bloom_Cognitive",
        "affective": "Bloom_Affective",
        "psychomotor": "Bloom_Psychomotor"
    }.get(domain)

    df = load_sheet_df(sheet)
    if df.empty:
        return jsonify([])

    mask = df.iloc[:, 0].astype(str).str.lower() == bloom.lower()
    if not mask.any():
        return jsonify([])

    raw = str(df.loc[mask].iloc[0, 1])
    verbs = [v.strip() for v in raw.split(",") if v.strip()]
    return jsonify(verbs)


@app.route("/api/debug_plo/<plo>")
def api_debug_plo(plo):
    profile = request.args.get("profile", "").strip().lower() or ""
    details = get_plo_details(plo, profile)
    return jsonify({"plo": plo, "details": details or {}, "exists": bool(details)})


# -----------------------------
# Run App
# -----------------------------
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



