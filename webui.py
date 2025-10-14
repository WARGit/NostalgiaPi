from datetime import datetime
import requests
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

@app.route("/multi_schedule")
def multi_schedule():
    cfg = load_config()
    peers = cfg.get("system", {}).get("peers", [])

    all_channels = []

    for peer in peers:
        try:
            r = requests.get(peer["url"], timeout=3)
            r.raise_for_status()
            data = r.json()
            all_channels.append({
                "channel_name": data.get("channel_name", peer["name"]),
                "entries": data.get("entries", []),
                "banner": data.get("banner"),
                "random_images": data.get("random_images", [])
            })
        except Exception as ex:
            all_channels.append({
                "channel_name": peer["name"],
                "entries": [],
                "error": str(ex)
            })

    return render_template(
        "multi_schedule.html",
        channels=all_channels,
        schedule_name="TV Guide"
    )

def run_flask():

    with open(CONFIG_FILE_NAME, "r") as f:
        cfg = json.load(f)
    app.run(host="0.0.0.0", port=cfg["system"]["webuiport"], debug=False, threaded=True)
