import os
import uuid
import json
import logging
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from flask_cors import CORS

# --- Import local utilities ---
from utils.parser import parse_jd_file, parse_resumes_upload
from utils.matcher import analyze_candidates

# -----------------------------------------
# Logging Setup
# -----------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# -----------------------------------------
# Flask App Setup
# -----------------------------------------
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
CORS(app)  # enable CORS for frontend access

app.config['UPLOAD_DIR'] = UPLOAD_DIR
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200 MB limit

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "zip"}

# -----------------------------------------
# Helpers
# -----------------------------------------
def safe_jsonify(obj, status=200):
    return jsonify(obj), status

# -----------------------------------------
# Health Check
# -----------------------------------------
@app.route("/health", methods=["GET"])
def health():
    return "OK", 200


# -----------------------------------------
# Upload JD
# -----------------------------------------
@app.route("/api/upload_jd", methods=["POST"])
def upload_jd():
    try:
        if "jd" not in request.files:
            return safe_jsonify({"error": "Missing 'jd' file"}, 400)

        f = request.files["jd"]
        if f.filename == "":
            return safe
