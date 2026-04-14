import os
import sqlite3
import base64
import io
import json
from datetime import datetime, date

import numpy as np
from PIL import Image
from flask import Flask, render_template, request, jsonify, redirect, url_for

# Try importing face_recognition; provide fallback message if unavailable
try:
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False
    print("WARNING: face_recognition not installed. Run: pip install face-recognition")

app = Flask(__name__)
app.secret_key = "attendance-secret-key"

DB_PATH = "attendance.db"
KNOWN_FACES_DIR = "known_faces"
os.makedirs(KNOWN_FACES_DIR, exist_ok=True)

# ── Database Setup ──────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            department TEXT,
            photo_path TEXT,
            face_encoding TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            check_in TIMESTAMP,
            check_out TIMESTAMP,
            date TEXT NOT NULL,
            status TEXT DEFAULT 'present',
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        );
    """)
    conn.commit()
    conn.close()

init_db()

# ── Helpers ─────────────────────────────────────────────────────
def decode_base64_image(data_url):
    """Convert base64 data URL to PIL Image."""
    header, encoded = data_url.split(",", 1)
    img_bytes = base64.b64decode(encoded)
    return Image.open(io.BytesIO(img_bytes))

def get_face_encoding(pil_image):
    """Return face encoding from a PIL image, or None."""
    if not FACE_RECOGNITION_AVAILABLE:
        return None
    img_array = np.array(pil_image.convert("RGB"))
    encodings = face_recognition.face_encodings(img_array)
    if encodings:
        return encodings[0]
    return None

def load_known_faces():
    """Load all stored face encodings from the database."""
    conn = get_db()
    rows = conn.execute("SELECT id, name, face_encoding FROM employees WHERE face_encoding IS NOT NULL").fetchall()
    conn.close()
    known = []
    for row in rows:
        enc = np.array(json.loads(row["face_encoding"]))
        known.append({"id": row["id"], "name": row["name"], "encoding": enc})
    return known

# ── Routes ──────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET"])
def register_page():
    return render_template("register.html")

@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.json
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    department = data.get("department", "").strip()
    photo_data = data.get("photo")

    if not name or not email:
        return jsonify({"error": "Name and email are required"}), 400

    # Process photo
    encoding_json = None
    photo_path = None
    if photo_data:
        pil_img = decode_base64_image(photo_data)
        enc = get_face_encoding(pil_img)
        if enc is None and FACE_RECOGNITION_AVAILABLE:
            return jsonify({"error": "No face detected in the photo. Please try again."}), 400
        if enc is not None:
            encoding_json = json.dumps(enc.tolist())
        photo_path = os.path.join(KNOWN_FACES_DIR, f"{email}.jpg")
        pil_img.save(photo_path)

    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO employees (name, email, department, photo_path, face_encoding) VALUES (?, ?, ?, ?, ?)",
            (name, email, department, photo_path, encoding_json),
        )
        conn.commit()
        conn.close()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Email already registered"}), 409

    return jsonify({"message": f"{name} registered successfully!"})

@app.route("/api/recognize", methods=["POST"])
def api_recognize():
    if not FACE_RECOGNITION_AVAILABLE:
        return jsonify({"error": "face_recognition library not installed"}), 500

    data = request.json
    photo_data = data.get("photo")
    if not photo_data:
        return jsonify({"error": "No photo provided"}), 400

    pil_img = decode_base64_image(photo_data)
    unknown_enc = get_face_encoding(pil_img)
    if unknown_enc is None:
        return jsonify({"error": "No face detected. Please look at the camera."}), 400

    known_faces = load_known_faces()
    if not known_faces:
        return jsonify({"error": "No employees registered yet."}), 404

    known_encodings = [kf["encoding"] for kf in known_faces]
    distances = face_recognition.face_distance(known_encodings, unknown_enc)
    best_idx = int(np.argmin(distances))
    best_distance = distances[best_idx]

    if best_distance > 0.5:
        return jsonify({"error": "Face not recognized. Please register first."}), 404

    employee = known_faces[best_idx]
    today = date.today().isoformat()

    conn = get_db()
    existing = conn.execute(
        "SELECT * FROM attendance WHERE employee_id = ? AND date = ?",
        (employee["id"], today),
    ).fetchone()

    if existing:
        if existing["check_out"] is None:
            conn.execute(
                "UPDATE attendance SET check_out = ? WHERE id = ?",
                (datetime.now().isoformat(), existing["id"]),
            )
            conn.commit()
            conn.close()
            return jsonify({"message": f"Goodbye {employee['name']}! Checked out.", "action": "check_out", "name": employee["name"]})
        else:
            conn.close()
            return jsonify({"message": f"{employee['name']}, you already checked in and out today.", "action": "already_done", "name": employee["name"]})
    else:
        conn.execute(
            "INSERT INTO attendance (employee_id, check_in, date) VALUES (?, ?, ?)",
            (employee["id"], datetime.now().isoformat(), today),
        )
        conn.commit()
        conn.close()
        return jsonify({"message": f"Welcome {employee['name']}! Checked in.", "action": "check_in", "name": employee["name"]})

@app.route("/api/attendance", methods=["GET"])
def api_attendance():
    selected_date = request.args.get("date", date.today().isoformat())
    conn = get_db()
    rows = conn.execute("""
        SELECT e.name, e.department, a.check_in, a.check_out, a.status, a.date
        FROM attendance a
        JOIN employees e ON a.employee_id = e.id
        WHERE a.date = ?
        ORDER BY a.check_in DESC
    """, (selected_date,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/employees", methods=["GET"])
def api_employees():
    conn = get_db()
    rows = conn.execute("SELECT id, name, email, department, created_at FROM employees ORDER BY name").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/attendance")
def attendance_page():
    return render_template("attendance.html")

@app.route("/mark")
def mark_page():
    return render_template("mark.html")

if __name__ == "__main__":
    print("=" * 50)
    print("  Attendance System - Face Recognition")
    print("  Open http://127.0.0.1:5000 in your browser")
    print("=" * 50)
    app.run(debug=True, host="0.0.0.0", port=5000)
