from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
import pandas as pd
import os
from datetime import datetime
from openpyxl import load_workbook
from io import BytesIO

app = Flask(__name__, template_folder="templates")

WORKBOOK_PATH = os.path.join(os.getcwd(), "SCLOG.xlsx")

# --- Helper functions ---

def load_sheet_df(sheet_name):
    try:
        return pd.read_excel(WORKBOOK_PATH, sheet_name=sheet_name, engine="openpyxl")
    except Exception:
        return pd.DataFrame()

def get_mapping_dict():
    df = load_sheet_df("Mapping")
    if df.empty:
        return pd.DataFrame()
    df.columns = [c.strip() for c in df.columns]
    return df

def get_plo_details(plo):
    df = get_mapping_dict()
    if df.empty:
        return None
    mask = df[df.columns[0]].astype(str).str.strip().str.upper() == str(plo).strip().upper()
    if mask.any():
        row = df[mask].iloc[0]
        cols = {c.lower(): c for c in df.columns}
        return {
            "PLO": row[df.columns[0]],
            "SC_Code": row.get(cols.get("sc code"), ""),
            "SC_Desc": row.get(cols.get("sc description"), ""),
            "VBE": row.get(cols.get("vbe"), ""),
            "Domain": row.get(cols.get("domain"), "")
        }
    return None

def get_criterion_phrase(domain, bloom):
    df = load_sheet_df("Criterion")
    if df.empty:
        return "", ""
    df.columns = [c.strip() for c in df.columns]
    dom_col, bloom_col, crit_col, cond_col = None, None, None, None
    for c in df.columns:
        lc = c.lower()
        if "domain" in lc: dom_col = c
        elif "bloom" in lc: bloom_col = c
        elif "criterion" in lc: crit_col = c
        elif "condition" in lc: cond_col = c
    mask = (df[dom_col].astype(str).str.lower() == str(domain).lower()) & \
           (df[bloom_col].astype(str).str.lower() == str(bloom).lower())
    if mask.any():
        row = df[mask].iloc[0]
        return str(row.get(crit_col, "")), str(row.get(cond_col, ""))
    return "", ""

def get_default_condition(domain):
    mapping = {
        "cognitive": "based on case scenarios or clinical data",
        "affective": "during clinical or group activities",
        "psychomotor": "under supervised practical conditions"
    }
    return mapping.get(str(domain).strip().lower(), "")

def get_assessment_and_evidence(bloom, domain):
    domain_lower = str(domain).lower()
    if domain_lower in ("affective", "psychomotor"):
        df = load_sheet_df("Assess_Affective_Psychomotor")
    else:
        df = load_sheet_df("Bloom_Assessments")
    if df.empty:
        return "", ""
    df.columns = [c.strip() for c in df.columns]
    bloom_col, assess_col, evidence_col = df.columns[:3]
    mask = df[bloom_col].astype(str).str.lower() == str(bloom).lower()
    if mask.any():
        row = df[mask].iloc[0]
        return str(row[assess_col]), str(row[evidence_col])
    return "", ""

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
        df = pd.read_excel(WORKBOOK_PATH, sheet_name="CLO_Table", engine="openpyxl")
    except Exception:
        df = pd.DataFrame()
    return df

def write_clo_table(df):
    """Save CLO table back into Excel safely (compatible with pandas ≥ 2.1)."""
    from openpyxl import load_workbook

    try:
        # Load workbook
        book = load_workbook(WORKBOOK_PATH)

        # Remove existing sheet if exists
        if "CLO_Table" in book.sheetnames:
            std = book["CLO_Table"]
            book.remove(std)

        # Save DataFrame as new sheet
        with pd.ExcelWriter(WORKBOOK_PATH, engine="openpyxl", mode="a") as writer:
            writer._book = book   # ✅ internal property, not the removed setter
            df.to_excel(writer, sheet_name="CLO_Table", index=False)

        print("✅ CLO_Table successfully written.")
    except Exception as e:
        print("⚠️ Error writing CLO_Table:", e)


# --- Routes ---

@app.route("/")
def index():
    df_map = get_mapping_dict()
    plos = []
    if not df_map.empty:
        plos = df_map[df_map.columns[0]].dropna().astype(str).tolist()
    df_ct = read_clo_table()
    table_html = df_ct.to_html(classes="data", index=False) if not df_ct.empty else "<p>No CLO records yet.</p>"
    return render_template("generator.html", plos=plos, table_html=table_html)

@app.route("/generate", methods=["POST"])
def generate():
    plo = request.form.get("plo")
    bloom = request.form.get("bloom")
    verb = request.form.get("verb")
    content = request.form.get("content")
    course = request.form.get("course")
    cw = request.form.get("cw")

    details = get_plo_details(plo) or {}
    domain = details.get("Domain", "")
    sc_code = details.get("SC_Code", "")
    sc_desc = details.get("SC_Desc", "")
    vbe = details.get("VBE", "")
    criterion, condition = get_criterion_phrase(domain, bloom)
    if not condition:
        condition = get_default_condition(domain)
    assessment, evidence = get_assessment_and_evidence(bloom, domain)
    clo = construct_clo_sentence(verb, content, sc_desc, condition, criterion, vbe)

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
        "Coursework Assessment Percentage (%)": cw
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    write_clo_table(df)
    return redirect(url_for("index"))

@app.route("/delete/<int:row_id>")
def delete_row(row_id):
    df = read_clo_table()
    if not df.empty and row_id in df["ID"].values:
        df = df[df["ID"] != row_id]
        write_clo_table(df)
    return redirect(url_for("index"))

@app.route("/edit/<int:row_id>", methods=["POST"])
def edit_row(row_id):
    field = request.form.get("field")
    value = request.form.get("value")
    df = read_clo_table()
    if not df.empty and field in df.columns:
        df.loc[df["ID"] == row_id, field] = value
        write_clo_table(df)
    return "Updated", 200

@app.route("/download")
def download():
    df = read_clo_table()
    if df.empty:
        return "<p>No CLO table to download.</p>"

    # Create a downloadable Excel file in memory
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="CLO_Table", index=False)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="CLO_Table.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

if __name__ == "__main__":
    app.run(debug=True)

@app.route("/get_blooms/<plo>")
def get_blooms(plo):
    """Return Bloom levels list based on the PLO’s domain."""
    details = get_plo_details(plo)
    if not details:
        return jsonify([])

    domain = str(details.get("Domain", "")).lower()
    if not domain:
        return jsonify([])

    # Choose sheet by domain
    sheet_map = {
        "cognitive": "Bloom_Cognitive",
        "affective": "Bloom_Affective",
        "psychomotor": "Bloom_Psychomotor"
    }
    sheet_name = sheet_map.get(domain)
    if not sheet_name:
        return jsonify([])

    df = load_sheet_df(sheet_name)
    if df.empty:
        return jsonify([])

    blooms = df.iloc[:, 0].dropna().astype(str).tolist()
    return jsonify(blooms)


@app.route("/get_verbs/<domain>/<bloom>")
def get_verbs(domain, bloom):
    """Return verb list for the selected domain and Bloom level."""
    domain = str(domain).lower()
    sheet_map = {
        "cognitive": "Bloom_Cognitive",
        "affective": "Bloom_Affective",
        "psychomotor": "Bloom_Psychomotor"
    }
    sheet_name = sheet_map.get(domain)
    if not sheet_name:
        return jsonify([])

    df = load_sheet_df(sheet_name)
    if df.empty:
        return jsonify([])

    mask = df.iloc[:, 0].astype(str).str.lower() == str(bloom).lower()
    if not mask.any():
        return jsonify([])

    verbs = []
    for v in df[mask].iloc[0, 1].split(","):
        if v.strip():
            verbs.append(v.strip())
    return jsonify(verbs)

# ---------- verb / bloom helpers & API endpoints ----------

def get_verbs_for_domain_and_bloom(domain, bloom):
    """Return list of verbs for a given domain and bloom (reads Bloom_Cognitive/Affective/Psychomotor)."""
    sheet_map = {
        "cognitive": "Bloom_Cognitive",
        "affective": "Bloom_Affective",
        "psychomotor": "Bloom_Psychomotor"
    }
    domain_key = str(domain).strip().lower()
    sheet = sheet_map.get(domain_key)
    if not sheet:
        return []
    df = load_sheet_df(sheet)
    if df.empty:
        return []
    # assume first column = Bloom Level, second column = Verbs (comma separated)
    col0 = df.columns[0]
    verb_col = df.columns[1] if len(df.columns) > 1 else None
    if verb_col is None:
        return []
    # find row(s) where bloom matches
    mask = df[col0].astype(str).str.strip().str.lower() == str(bloom).strip().lower()
    if not mask.any():
        return []
    raw = df.loc[mask, verb_col].iloc[0]
    if pd.isna(raw) or str(raw).strip()=="":
        return []
    # split by comma and return cleaned list
    verbs = [v.strip() for v in str(raw).split(",") if v.strip()]
    return verbs

@app.route("/api/get_blooms/<plo>")
def api_get_blooms(plo):
    """Return list of bloom levels for a PLO (based on PLO -> Domain -> Criterion sheet)."""
    details = get_plo_details(plo)
    if not details:
        return jsonify([])
    domain = details.get("Domain", "")
    if not domain:
        return jsonify([])
    # Try to use Criterion sheet to return available bloom levels for the domain
    df = load_sheet_df("Criterion")
    if not df.empty:
        # find domain column and bloom column
        cols = [c.strip() for c in df.columns]
        dom_col = next((c for c in cols if 'domain' in c.lower()), None)
        bloom_col = next((c for c in cols if 'bloom' in c.lower()), None)
        if dom_col and bloom_col:
            vals = df[df[dom_col].astype(str).str.strip().str.lower() == str(domain).strip().lower()][bloom_col].dropna().astype(str).str.strip().unique().tolist()
            if vals:
                return jsonify(vals)
    # fallback to typical bloom list
    return jsonify(["Remember","Understand","Apply","Analyze","Evaluate","Create"])

@app.route("/get_verbs/<plo>/<bloom>")
def get_verbs_route(plo, bloom):
    """Return verbs list for a given plo (resolve domain from plo then find verbs)."""
    details = get_plo_details(plo)
    if not details:
        return jsonify([])
    domain = details.get("Domain", "")
    verbs = get_verbs_for_domain_and_bloom(domain, bloom)
    return jsonify(verbs)



