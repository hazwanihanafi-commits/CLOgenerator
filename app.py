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
    """Save CLO table back into Excel (Render-compatible)."""
    from openpyxl import load_workbook
    try:
        book = load_workbook(WORKBOOK_PATH)
        with pd.ExcelWriter(
            WORKBOOK_PATH, engine="openpyxl", mode="a", if_sheet_exists="replace"
        ) as writer:
            writer.book = book
            df.to_excel(writer, sheet_name="CLO_Table", index=False)
    except Exception as e:
        print("Error writing CLO_Table:", e)

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
