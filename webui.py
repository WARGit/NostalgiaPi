from datetime import datetime

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
    # Load queued.json
    with open("queued.json", "r") as f:
        data = json.load(f)
    entries = data  # no filtering, all entries are shows

    for e in entries:
        t = datetime.strptime(e["time"], "%H:%M")
        e["time_formatted"] = t.strftime("%I:%M %p").lstrip("0")  # e.g. 6:00 AM

        # random icon or none
        if random.choice([True, False]):
            e["icon"] = f"img/icons/{random.choice(['new.png', 'rerun.png'])}"
        else:
            e["icon"] = None

        # tie banner to month
    month_name = datetime.now().strftime("%B").lower()  # e.g. 'september'
    banner_dir = os.path.join(app.static_folder, "img", "banners")

    banner = None
    if os.path.exists(banner_dir):
        for ext in ("png", "jpg", "jpeg", "gif"):
            candidate = f"{month_name}.{ext}"
            if candidate in os.listdir(banner_dir):
                banner = candidate
                break

    # fallback: pick a random banner if no month-specific one found
    if banner is None:
        banners = os.listdir(banner_dir) if os.path.exists(banner_dir) else []
        banner = random.choice(banners) if banners else None

    # floating images
    img_dir = os.path.join(app.static_folder, "img", "tvguide")
    img_files = os.listdir(img_dir) if os.path.exists(img_dir) else []
    random_images = random.sample(img_files, min(3, len(img_files)))

    return render_template(
        "view_schedule.html",
        entries=entries,
        random_images=random_images,
        banner=banner,
        schedule_name="Tonight's Schedule"  # replace with JSON-driven schedule name later
    )

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

    with open(CONFIG_FILE_NAME, "r") as f:
        cfg = json.load(f)
    app.run(host="0.0.0.0", port=cfg["system"]["webuiport"], debug=False, threaded=True)
