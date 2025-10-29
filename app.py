from flask import Flask, render_template

app = Flask(__name__)

@app.route("/")
def index():
    print("✅ Route / accessed successfully — rendering template now.")
    return render_template("CLO_Generator.html")

if __name__ == "__main__":
    print("🚀 Flask app is starting...")
    app.run(debug=True)
