from flask import Flask, jsonify, request, render_template
import json
import os
import random

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

@app.route("/view_schedule")
def view_schedule():
    # Load your queued.json
    import json
    with open("queued.json", "r") as f:
        entries = json.load(f)

    # Get list of images from static/img/tvguide
    img_folder = os.path.join(app.static_folder, "img", "tvguide")
    images = [f"img/tvguide/{f}" for f in os.listdir(img_folder)
              if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))]

    # Assign a random image to each entry
    for entry in entries:
        entry["image"] = random.choice(images)

    return render_template("view_schedule.html", entries=entries)


@app.route("/config", methods=["GET"])
def get_config():
    cfg = load_config()
    return jsonify(cfg)

@app.route("/config", methods=["POST"])
def update_config():
    new_cfg = request.json
    save_config(new_cfg)
    return jsonify({"status": "ok"})

@app.route("/queued")
def get_queued():
    """Return queued.json for the web UI"""
    if not os.path.exists("queued.json"):
        return jsonify([])
    with open("queued.json", "r") as f:
        data = json.load(f)
    return jsonify(data)

def run_flask():
    app.run(host="0.0.0.0", port=8000, debug=False, threaded=True)
