from flask import Flask, render_template, request
import pandas as pd
import os

app = Flask(__name__)

# Path for saving Excel file (Render uses a temp directory)
SAVE_PATH = os.path.join(os.getcwd(), "clo_data.xlsx")

@app.route("/", methods=["GET", "POST"])
def index():
    message = ""
    if request.method == "POST":
        # Get form data
        clo = request.form.get("clo")
        plo = request.form.get("plo")
        bloom = request.form.get("bloom")
        description = request.form.get("description")

        # Store in Excel
        data = {"CLO": [clo], "PLO": [plo], "Bloom Level": [bloom], "Description": [description]}
        df = pd.DataFrame(data)

        # Append or create new file
        if os.path.exists(SAVE_PATH):
            existing = pd.read_excel(SAVE_PATH)
            df = pd.concat([existing, df], ignore_index=True)

        df.to_excel(SAVE_PATH, index=False)
        message = f"✅ CLO '{clo}' added successfully!"

    # If Excel file exists, display it
    if os.path.exists(SAVE_PATH):
        df = pd.read_excel(SAVE_PATH)
        table_html = df.to_html(classes='data', index=False)
    else:
        table_html = "<p>No CLOs added yet.</p>"

    return render_template("editor.html", message=message, table_html=table_html)

if __name__ == "__main__":
    app.run(debug=True)
