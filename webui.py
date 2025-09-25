from flask import Flask, jsonify, request, render_template
import json
import os

CONFIG_FILE_NAME = "config_pi.json" if os.name != "nt" else "config_nt.json"

app = Flask(__name__, static_folder="static")

def load_config():
    if not os.path.exists(CONFIG_FILE_NAME):
        return {}
    with open(CONFIG_FILE_NAME, "r") as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_FILE_NAME, "w") as f:
        json.dump(cfg, f, indent=2)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/wizard")
def wizard():
    return render_template("wizard.html")

@app.route("/config", methods=["GET"])
def get_config():
    cfg = load_config()
    return jsonify(cfg)

@app.route("/config", methods=["POST"])
def update_config():
    new_cfg = request.json
    save_config(new_cfg)
    return jsonify({"status": "ok"})

def run_flask():
    # Threaded=True lets Flask handle multiple requests at once
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
