from flask import Flask, request, jsonify, render_template_string, send_from_directory, abort, redirect, url_for, Response
import csv, io, os, json, hashlib
from datetime import datetime, timezone
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# ---------- Paths & Config ----------
BASE_DIR    = os.path.dirname(__file__)
DATA_FILE   = os.path.join(BASE_DIR, "data.jsonl")
METER_FILE  = os.path.join(BASE_DIR, "data2.jsonl")
ERROR_FILE  = os.path.join(BASE_DIR, "errors.jsonl")
OTA_DIR     = os.path.join(BASE_DIR, "ota")

DASHBOARD_DIR = os.path.join(BASE_DIR, "firmware_dashboard")
DASHBOARD_STATUS_FILE = os.path.join(DASHBOARD_DIR, "status.json")

# Optional API key. If not set, endpoint is open.
DASHBOARD_API_KEY = os.environ.get("FIRMWARE_DASHBOARD_API_KEY", "")

os.makedirs(OTA_DIR, exist_ok=True)
os.makedirs(DASHBOARD_DIR, exist_ok=True)

# ---------- Helpers ----------
def read_jsonl(path):
    msgs = []
    if os.path.exists(path):
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if not line: continue
                try:
                    msgs.append(json.loads(line))
                except:
                    continue
    return msgs

def build_csv_response(filename_prefix, headers, rows):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([label for label, key in headers])

    for row in rows:
        writer.writerow([row.get(key, "") if isinstance(row, dict) else "" for label, key in headers])

    current_date = datetime.now().date().isoformat()
    filename = f"{filename_prefix}_{current_date}.csv"

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def atomic_write(path, bytes_data):
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(bytes_data)
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)

def default_dashboard_status():
    return {
        "status": "idle",
        "phase": "Waiting for requirement",
        "progress": 0,
        "updated_at": "",
        "requirement": "",
        "validation_token": "",
        "attempt": 0,
        "max_attempts": 3,
        "code_review": "",
        "board_status": "",
        "terminal_output": "",
        "terminal_outputs": [],
        "result": "",
        "commit_url": "",
        "logs": []
    }

def read_dashboard_status():
    if not os.path.exists(DASHBOARD_STATUS_FILE):
        return default_dashboard_status()

    try:
        with open(DASHBOARD_STATUS_FILE, "r") as f:
            status = json.load(f)
            return {**default_dashboard_status(), **status}
    except:
        return {
            **default_dashboard_status(),
            "status": "dashboard status file error"
        }

def write_dashboard_status(status):
    atomic_write(
        DASHBOARD_STATUS_FILE,
        json.dumps(status, indent=2).encode("utf-8")
    )

def rebuild_terminal_output(status):
    terminal_outputs = status.get("terminal_outputs", [])
    if not isinstance(terminal_outputs, list):
        terminal_outputs = []

    parts = []
    for entry in terminal_outputs:
        if not isinstance(entry, dict):
            continue

        time_value = entry.get("time", "")
        content = entry.get("content", "")
        if not content:
            continue

        parts.append(
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{time_value}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{content}"
        )

    status["terminal_outputs"] = terminal_outputs[-50:]
    status["terminal_output"] = "\n\n".join(parts[-50:])

def update_dashboard_status(update_data):
    status = read_dashboard_status()

    log_message = update_data.pop("log_message", None)
    if log_message is None:
        log_message = update_data.pop("log", None)

    terminal_output = update_data.pop("terminal_output", None)

    for key, value in update_data.items():
        status[key] = value

    # If a workflow starts a fresh run, clear terminal output history too.
    if "logs" in update_data and update_data.get("logs") == []:
        status["terminal_outputs"] = []
        status["terminal_output"] = ""

    status["updated_at"] = datetime.now(timezone.utc).isoformat()

    if log_message:
        if "logs" not in status or not isinstance(status["logs"], list):
            status["logs"] = []

        status["logs"].append({
            "time": datetime.now(timezone.utc).isoformat(),
            "message": str(log_message)
        })

    if terminal_output:
        if "terminal_outputs" not in status or not isinstance(status["terminal_outputs"], list):
            status["terminal_outputs"] = []

        status["terminal_outputs"].append({
            "time": datetime.now(timezone.utc).isoformat(),
            "content": str(terminal_output)
        })

        rebuild_terminal_output(status)

    write_dashboard_status(status)
    return status

# ---------- Basic ----------
@app.route("/")
def index():
    html = """
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Bitflow92 Telemetry Server</title>
      <style>
        body { font-family: Arial, sans-serif; margin: 24px; background: #f6f7f9; color: #222; }
        a { color: #0b6bcb; text-decoration: none; }
        .hero { background: white; padding: 28px; border-radius: 14px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); margin-bottom: 18px; }
        .hero h1 { margin: 0 0 8px 0; font-size: 34px; }
        .hero p { margin: 0; color: #666; font-size: 16px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; }
        .card { background: white; padding: 20px; border-radius: 14px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); }
        .card h2 { margin: 0 0 8px 0; font-size: 22px; }
        .card p { color: #666; margin: 0 0 14px 0; }
        .button { display: inline-block; background: #0b6bcb; color: white; padding: 10px 14px; border-radius: 8px; font-weight: 700; }
      </style>
    </head>
    <body>
      <div class="hero">
        <h1>Bitflow92 Telemetry Server</h1>
        <p>Flask server is running. Select a dashboard below.</p>
      </div>

      <div class="grid">
        <div class="card">
          <h2>Device Data</h2>
          <p>FIDL device readings and history.</p>
          <a class="button" href="/messages">Open Dashboard</a>
        </div>
        <div class="card">
          <h2>INA219 Solar Meter</h2>
          <p>Solar voltage, current, power and temperature readings.</p>
          <a class="button" href="/meter">Open Dashboard</a>
        </div>
        <div class="card">
          <h2>Error Logs</h2>
          <p>Incoming request and server error logs.</p>
          <a class="button" href="/log/errors">Open Logs</a>
        </div>
        <div class="card">
          <h2>ESP32 Firmware Dashboard</h2>
          <p>Firmware workflow status and terminal output.</p>
          <a class="button" href="/firmware-dashboard">Open Dashboard</a>
        </div>
      </div>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200

# ---------- Firmware Dashboard ----------
@app.route("/firmware-dashboard")
def firmware_dashboard():
    html = """
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>ESP32 Firmware Dashboard</title>
      <style>
        body {
          font-family: Arial, sans-serif;
          margin: 24px;
          background: #f6f7f9;
          color: #222;
        }
        .top {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 16px;
          margin-bottom: 18px;
        }
        a {
          color: #0b6bcb;
          text-decoration: none;
        }
        .grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
          gap: 16px;
        }
        .card {
          background: white;
          padding: 18px;
          border-radius: 12px;
          box-shadow: 0 2px 10px rgba(0,0,0,0.08);
          margin-bottom: 16px;
        }
        .status {
          font-size: 30px;
          font-weight: 700;
          margin-bottom: 8px;
        }
        .phase {
          font-size: 18px;
          font-weight: 600;
          margin-top: 4px;
        }
        .muted {
          color: #666;
          font-size: 14px;
        }
        pre {
          white-space: pre-wrap;
          word-break: break-word;
          background: #111;
          color: #eee;
          padding: 14px;
          border-radius: 8px;
          max-height: 440px;
          overflow: auto;
        }
        .label {
          font-weight: 700;
        }
        .progress-wrap {
          background: #ddd;
          border-radius: 12px;
          overflow: hidden;
          height: 24px;
          margin-top: 12px;
        }
        .progress-bar {
          height: 24px;
          width: 0%;
          background: #22c55e;
          transition: width 0.4s ease;
        }
        .progress-text {
          margin-top: 8px;
          font-weight: 700;
        }
      </style>
    </head>
    <body>
      <div class="top">
        <h1>ESP32 Firmware Dashboard</h1>
        <a href="/">Home</a>
      </div>

      <div class="card">
        <div class="status" id="status">Loading...</div>
        <div class="phase" id="phase"></div>
        <div class="muted" id="updated"></div>

        <div class="progress-wrap">
          <div class="progress-bar" id="progressBar"></div>
        </div>
        <div class="progress-text" id="progressText"></div>
      </div>

      <div class="grid">
        <div class="card">
          <h2>Validation</h2>
          <p><span class="label">Token:</span> <span id="token"></span></p>
          <p><span class="label">Attempt:</span> <span id="attempt"></span></p>
          <p><span class="label">Board:</span> <span id="board"></span></p>
          <p><span class="label">Result:</span> <span id="result"></span></p>
          <p><span class="label">Commit:</span> <span id="commit"></span></p>
        </div>

        <div class="card">
          <h2>Activity Log</h2>
          <pre id="logs"></pre>
        </div>
      </div>

      <div class="card">
        <h2>Code Review</h2>
        <pre id="review"></pre>
      </div>

      <div class="card">
        <h2>Requirement</h2>
        <pre id="requirement"></pre>
      </div>

      <div class="card">
        <h2>Terminal Output</h2>
        <pre id="terminal"></pre>
      </div>

      <script>
        async function loadStatus() {
          try {
            const res = await fetch("/firmware-dashboard/status?t=" + Date.now());
            const data = await res.json();

            document.getElementById("status").textContent = data.status || "unknown";
            document.getElementById("phase").textContent = data.phase || "";
            document.getElementById("updated").textContent = "Updated: " + (data.updated_at || "");
            document.getElementById("requirement").textContent = data.requirement || "";
            document.getElementById("token").textContent = data.validation_token || "";

            const retryAttempt = Number(data.attempt || 0);
            const maxRetries = Number(data.max_attempts || 3);
            document.getElementById("attempt").textContent = `${retryAttempt + 1} / ${maxRetries + 1}`;

            document.getElementById("board").textContent = data.board_status || "";
            document.getElementById("review").textContent = data.code_review || "";
            document.getElementById("result").textContent = data.result || "";
            document.getElementById("terminal").textContent = data.terminal_output || "";

            const progress = data.progress || 0;
            document.getElementById("progressBar").style.width = progress + "%";
            document.getElementById("progressText").textContent = progress + "%";

            const logs = data.logs || [];
            document.getElementById("logs").textContent = logs
              .map(l => `${l.time || ""} - ${l.message || ""}`)
              .join("\\n");

            const commit = data.commit_url || "";
            document.getElementById("commit").innerHTML = commit
              ? `<a href="${commit}" target="_blank">Open commit</a>`
              : "";
          } catch (e) {
            document.getElementById("status").textContent = "dashboard error";
            document.getElementById("terminal").textContent = String(e);
          }
        }

        loadStatus();
        setInterval(loadStatus, 3000);
      </script>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route("/firmware-dashboard/status")
def firmware_dashboard_status():
    return jsonify(read_dashboard_status()), 200

@app.route("/firmware-dashboard/update", methods=["POST"])
def firmware_dashboard_update():
    if DASHBOARD_API_KEY:
        supplied_key = request.headers.get("X-API-Key", "")
        if supplied_key != DASHBOARD_API_KEY:
            return jsonify({"error": "Unauthorized"}), 401

    if not request.is_json:
        return jsonify({"error": "Expected JSON body"}), 400

    try:
        payload = request.get_json()

        if not isinstance(payload, dict):
            return jsonify({"error": "JSON body must be an object"}), 400

        if "dashboard" in payload and isinstance(payload.get("dashboard"), dict):
            dashboard_update = dict(payload["dashboard"])
            passthrough = payload.get("passthrough", payload)
        else:
            dashboard_update = dict(payload)
            passthrough = payload

        update_dashboard_status(dashboard_update)

        return jsonify(passthrough), 200

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


# ---------- INA219 Solar Meter ----------
def normalise_meter_payload(data):
    """Keep the logger payload simple, but add server receive metadata."""
    return {
        "received_at": datetime.now(timezone.utc).isoformat(),
        "count": data.get("count", ""),
        "time": data.get("time", ""),
        "temperature": data.get("temperature", ""),
        "solar_voltage": data.get("solar_voltage", ""),
        "solar_current": data.get("solar_current", ""),
        "solar_power": data.get("solar_power", ""),
    }

@app.route("/receive-meter", methods=["POST"])
def receive_meter():
    if not request.is_json:
        error = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": "Missing or invalid JSON on /receive-meter",
            "ip": request.remote_addr,
            "headers": dict(request.headers),
            "body": request.data.decode(errors="replace")
        }
        with open(ERROR_FILE, "a") as f:
            f.write(json.dumps(error) + "\n")
        return jsonify({"status": "error", "message": "Missing or invalid JSON"}), 400

    try:
        data = request.get_json()
        if isinstance(data, str):
            data = json.loads(data)

        if not isinstance(data, dict):
            return jsonify({"status": "error", "message": "JSON body must be an object"}), 400

        record = normalise_meter_payload(data)

        with open(METER_FILE, "a") as f:
            f.write(json.dumps(record) + "\n")

        print("✅ Received INA219 meter JSON:", record)
        return jsonify({"status": "success"}), 200

    except Exception as e:
        error = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(e),
            "ip": request.remote_addr,
            "headers": dict(request.headers),
            "body": request.data.decode(errors="replace")
        }
        with open(ERROR_FILE, "a") as f:
            f.write(json.dumps(error) + "\n")
        print("❌ INA219 meter error:", e)
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route("/meter")
def show_meter():
    history = read_jsonl(METER_FILE)
    latest = history[-1] if history else {}
    messages = list(reversed(history))
    html = """
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <meta http-equiv="refresh" content="10">
      <title>INA219 Solar Meter</title>
      <style>
        body { font-family: Arial, sans-serif; margin: 24px; background: #f6f7f9; color: #222; }
        a { color: #0b6bcb; text-decoration: none; }
        .top { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 12px; }
        .card { background: white; padding: 18px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); margin-bottom: 16px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
        .metric { font-size: 28px; font-weight: 700; }
        .label { color: #666; font-size: 14px; }
        table { border-collapse: collapse; width: 100%; background: white; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background: #eee; }
        .muted { color: #666; }
        .actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
        .button { display: inline-block; background: #0b6bcb; color: white; padding: 10px 14px; border-radius: 8px; font-weight: 700; }
        .danger { background: #dc2626; color: white; border: 0; border-radius: 8px; padding: 10px 14px; font-weight: 700; cursor: pointer; }
      </style>
    </head>
    <body>
      <div class="top">
        <div>
          <h2>INA219 Solar Meter</h2>
          <p><a href="/">Home</a> | <a href="/meter.json">Raw JSON</a></p>
        </div>
        <div class="actions">
          <a class="button" href="/meter/download.csv">Download CSV</a>
          <form method="post" action="/meter/delete" onsubmit="return confirm('Delete all INA219 solar meter history?');">
            <button class="danger" type="submit">Delete History</button>
          </form>
        </div>
      </div>

      <div class="card">
        <h3>Latest Reading</h3>
        {% if latest %}
        <div class="grid">
          <div><div class="label">Solar Voltage</div><div class="metric">{{ latest.get('solar_voltage', '') }} V</div></div>
          <div><div class="label">Solar Current</div><div class="metric">{{ latest.get('solar_current', '') }} mA</div></div>
          <div><div class="label">Solar Power</div><div class="metric">{{ latest.get('solar_power', '') }} mW</div></div>
          <div><div class="label">Temperature</div><div class="metric">{{ latest.get('temperature', '') }} °C</div></div>
        </div>
        <p class="muted">Logger time: {{ latest.get('time', '') }} | Server received: {{ latest.get('received_at', '') }} | Count: {{ latest.get('count', '') }}</p>
        {% else %}
        <p>No INA219 meter data received yet.</p>
        {% endif %}
      </div>

      <div class="card">
        <h3>Complete History</h3>
        {% if messages %}
        <table>
          <tr>
            <th>Count</th><th>Logger Time</th><th>Server Received</th><th>Temp °C</th>
            <th>Solar Voltage V</th><th>Solar Current mA</th><th>Solar Power mW</th>
          </tr>
          {% for msg in messages %}
          <tr>
            <td>{{ msg.get('count', '') }}</td>
            <td>{{ msg.get('time', '') }}</td>
            <td>{{ msg.get('received_at', '') }}</td>
            <td>{{ msg.get('temperature', '') }}</td>
            <td>{{ msg.get('solar_voltage', '') }}</td>
            <td>{{ msg.get('solar_current', '') }}</td>
            <td>{{ msg.get('solar_power', '') }}</td>
          </tr>
          {% endfor %}
        </table>
        {% else %}
        <p>No history yet.</p>
        {% endif %}
      </div>
    </body>
    </html>
    """
    return render_template_string(html, messages=messages, latest=latest)

@app.route("/meter/download.csv")
def download_meter_csv():
    headers = [
        ("Count", "count"),
        ("Logger Time", "time"),
        ("Server Received", "received_at"),
        ("Temperature", "temperature"),
        ("Solar Voltage", "solar_voltage"),
        ("Solar Current", "solar_current"),
        ("Solar Power", "solar_power"),
    ]
    return build_csv_response("meter_data", headers, read_jsonl(METER_FILE))

@app.route("/meter/delete", methods=["POST"])
def delete_meter_history():
    try:
        open(METER_FILE, "w").close()
    except Exception as e:
        print("❌ Could not delete INA219 meter history:", e)
    return redirect(url_for("show_meter"))

@app.route("/meter.json")
def meter_json():
    return jsonify(read_jsonl(METER_FILE))

# ---------- JSON Receiver ----------
@app.route("/receive", methods=["POST"])
def receive():
    if not request.is_json:
        error = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": "Missing or invalid JSON",
            "ip": request.remote_addr,
            "headers": dict(request.headers),
            "body": request.data.decode(errors="replace")
        }
        with open(ERROR_FILE, "a") as f:
            f.write(json.dumps(error) + "\n")
        return jsonify({"status": "error", "message": "Missing or invalid JSON"}), 400

    try:
        data = request.get_json()
        if isinstance(data, str):
            data = json.loads(data)

        with open(DATA_FILE, "a") as f:
            f.write(json.dumps(data) + "\n")

        print("✅ Received JSON:", data)
        return jsonify({"status": "success"}), 200

    except Exception as e:
        error = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(e),
            "ip": request.remote_addr,
            "headers": dict(request.headers),
            "body": request.data.decode(errors="replace")
        }
        with open(ERROR_FILE, "a") as f:
            f.write(json.dumps(error) + "\n")
        print("❌ Error:", e)
        return jsonify({"status": "error", "message": str(e)}), 400

# ---------- View Received Messages ----------
@app.route("/messages")
def show_messages():
    history = read_jsonl(DATA_FILE)
    latest = history[-1] if history else {}
    messages = list(reversed(history))
    html = """
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <meta http-equiv="refresh" content="10">
      <title>Device Data Log</title>
      <style>
        body { font-family: Arial, sans-serif; margin: 24px; background: #f6f7f9; color: #222; }
        a { color: #0b6bcb; text-decoration: none; }
        .top { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 12px; }
        .card { background: white; padding: 18px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); margin-bottom: 16px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
        .metric { font-size: 28px; font-weight: 700; }
        .label { color: #666; font-size: 14px; }
        table { border-collapse: collapse; width: 100%; background: white; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background: #eee; }
        .muted { color: #666; }
        .actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
        .button { display: inline-block; background: #0b6bcb; color: white; padding: 10px 14px; border-radius: 8px; font-weight: 700; }
        .danger { background: #dc2626; color: white; border: 0; border-radius: 8px; padding: 10px 14px; font-weight: 700; cursor: pointer; }
      </style>
    </head>
    <body>
      <div class="top">
        <div>
          <h2>Device Data Log</h2>
          <p><a href="/">Home</a> | <a href="/messages.json">Raw JSON</a></p>
        </div>
        <div class="actions">
          <a class="button" href="/messages/download.csv">Download CSV</a>
          <form method="post" action="/messages/delete" onsubmit="return confirm('Delete all device data history?');">
            <button class="danger" type="submit">Delete History</button>
          </form>
        </div>
      </div>

      <div class="card">
        <h3>Latest Reading</h3>
        {% if latest %}
        <div class="grid">
          <div><div class="label">Battery</div><div class="metric">{{ latest.get('battery', '') }} V</div></div>
          <div><div class="label">Temperature</div><div class="metric">{{ latest.get('temperature', '') }} °C</div></div>
          <div><div class="label">Satellites</div><div class="metric">{{ latest.get('satellites', '') }}</div></div>
          <div><div class="label">Board</div><div class="metric">{{ latest.get('board_id', '') }}</div></div>
        </div>
        <p class="muted">Logger time: {{ latest.get('time', '') }} | GPS date: {{ latest.get('gps_date', '') }} | GPS time: {{ latest.get('gps_time', '') }} | Count: {{ latest.get('count', '') }} | Version: {{ latest.get('version', '') }}</p>
        {% else %}
        <p>No device data received yet.</p>
        {% endif %}
      </div>

      <div class="card">
        <h3>Complete History</h3>
        {% if messages %}
        <table>
          <tr>
            <th>Count</th><th>Time</th><th>Battery V</th><th>Temp °C</th>
            <th>Lat</th><th>Long</th><th>GPS Date</th><th>GPS Time</th>
            <th>Sats</th><th>Version</th><th>Board</th>
          </tr>
          {% for msg in messages %}
          <tr>
            <td>{{ msg.get('count', '') }}</td>
            <td>{{ msg.get('time', '') }}</td>
            <td>{{ msg.get('battery', '') }}</td>
            <td>{{ msg.get('temperature', '') }}</td>
            <td>{{ msg.get('latitude', '') }}</td>
            <td>{{ msg.get('longitude', '') }}</td>
            <td>{{ msg.get('gps_date', '') }}</td>
            <td>{{ msg.get('gps_time', '') }}</td>
            <td>{{ msg.get('satellites', '') }}</td>
            <td>{{ msg.get('version', '') }}</td>
            <td>{{ msg.get('board_id', '') }}</td>
          </tr>
          {% endfor %}
        </table>
        {% else %}
        <p>No history yet.</p>
        {% endif %}
      </div>
    </body>
    </html>
    """
    return render_template_string(html, messages=messages, latest=latest)

@app.route("/messages/download.csv")
def download_messages_csv():
    headers = [
        ("Count", "count"),
        ("Logger Time", "time"),
        ("Battery", "battery"),
        ("Temperature", "temperature"),
        ("Latitude", "latitude"),
        ("Longitude", "longitude"),
        ("GPS Date", "gps_date"),
        ("GPS Time", "gps_time"),
        ("Satellites", "satellites"),
        ("Version", "version"),
        ("Board", "board_id"),
    ]
    return build_csv_response("device_data", headers, read_jsonl(DATA_FILE))

@app.route("/messages/delete", methods=["POST"])
def delete_messages_history():
    try:
        open(DATA_FILE, "w").close()
    except Exception as e:
        print("❌ Could not delete device data history:", e)
    return redirect(url_for("show_messages"))

@app.route("/messages.json")
def messages_json():
    return jsonify(read_jsonl(DATA_FILE))

# ---------- View Error Logs ----------
@app.route("/log/errors")
def show_errors():
    errors = read_jsonl(ERROR_FILE)
    html = """
    <h2>Error Logs</h2>
    <p><a href="/">Home</a></p>
    {% if errors %}
    <table border="1" cellpadding="6">
      <tr>
        <th>Timestamp</th><th>Error</th><th>IP</th><th>Raw Body</th>
      </tr>
      {% for e in errors %}
      <tr>
        <td>{{ e.get('timestamp', 'N/A') }}</td>
        <td>{{ e.get('error', 'N/A') }}</td>
        <td>{{ e.get('ip', 'N/A') }}</td>
        <td><pre>{{ e.get('body', '') }}</pre></td>
      </tr>
      {% endfor %}
    </table>
    {% else %}
    <p>No errors logged yet.</p>
    {% endif %}
    """
    return render_template_string(html, errors=errors)

# ---------- OTA API ----------
@app.route("/ota/version.json")
def ota_version():
    path = os.path.join(OTA_DIR, "version.json")
    if not os.path.exists(path):
        return jsonify({"error": "version.json not found"}), 404
    with open(path, "r") as f:
        try:
            return jsonify(json.load(f)), 200
        except:
            return jsonify({"error": "Invalid JSON"}), 500

@app.route("/ota/<path:filename>")
def ota_file(filename):
    safe = secure_filename(filename)
    fpath = os.path.join(OTA_DIR, safe)
    if not os.path.exists(fpath):
        abort(404)
    return send_from_directory(OTA_DIR, safe, as_attachment=False)

# ---------- Dev Run ----------
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=38649)
