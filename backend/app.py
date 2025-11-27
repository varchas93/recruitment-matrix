import os
import uuid
import json
import logging
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from flask_cors import CORS

from utils.parser import parse_jd_file, parse_resumes_upload
from utils.matcher import analyze_candidates

# ---------------- LOGGING ---------------- #
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ---------------- APP SETUP ---------------- #
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
CORS(app)

app.config["UPLOAD_DIR"] = UPLOAD_DIR
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200MB

# ---------------- HELPERS ---------------- #
def safe_jsonify(obj, status=200):
    return jsonify(obj), status

# ---------------- ROUTES ---------------- #

@app.route("/health", methods=["GET"])
def health():
    return "OK", 200


# ---------- UPLOAD JD ---------- #
@app.route("/api/upload_jd", methods=["POST"])
def upload_jd():
    try:
        if "jd" not in request.files:
            return safe_jsonify({"error": "Missing JD file"}, 400)

        f = request.files["jd"]
        if f.filename == "":
            return safe_jsonify({"error": "Empty JD filename"}, 400)

        filename = secure_filename(f.filename)
        dest = os.path.join(UPLOAD_DIR, f"jd_{uuid.uuid4().hex}_{filename}")
        f.save(dest)

        logging.info(f"Saved JD → {dest}")

        jd_text = parse_jd_file(dest) or ""

        jd_store = os.path.join(UPLOAD_DIR, "current_jd.txt")
        with open(jd_store, "w", encoding="utf-8") as wf:
            wf.write(jd_text)

        return safe_jsonify({
            "status": "ok",
            "jd_word_count": len(jd_text.split())
        })

    except Exception as e:
        logging.exception("upload_jd failed")
        return safe_jsonify({"error": "Server error", "detail": str(e)}, 500)


# ---------- UPLOAD RESUMES ---------- #
@app.route("/api/upload_resumes", methods=["POST"])
def upload_resumes():
    try:
        files = request.files.getlist("resumes")
        if not files:
            return safe_jsonify({"error": "No resumes uploaded"}, 400)

        saved_paths = []
        for f in files:
            if f.filename == "":
                continue

            filename = secure_filename(f.filename)
            dest = os.path.join(UPLOAD_DIR, f"res_{uuid.uuid4().hex}_{filename}")
            f.save(dest)
            saved_paths.append(dest)

        logging.info(f"Saved resumes: {saved_paths}")

        candidates = parse_resumes_upload(saved_paths, UPLOAD_DIR)

        cand_store = os.path.join(UPLOAD_DIR, "current_candidates.json")
        with open(cand_store, "w", encoding="utf-8") as wf:
            json.dump(candidates, wf, indent=2, ensure_ascii=False)

        return safe_jsonify({
            "status": "ok",
            "parsed_count": len(candidates)
        })

    except Exception as e:
        logging.exception("upload_resumes failed")
        return safe_jsonify({"error": "Server error", "detail": str(e)}, 500)


# ---------- ANALYZE ---------- #
@app.route("/api/analyze", methods=["GET"])
def analyze():
    try:
        jd_store = os.path.join(UPLOAD_DIR, "current_jd.txt")
        cand_store = os.path.join(UPLOAD_DIR, "current_candidates.json")

        if not os.path.exists(cand_store):
            return safe_jsonify({"error": "Upload resumes first"}, 400)

        with open(cand_store, "r", encoding="utf-8") as rf:
            candidates = json.load(rf)

        jd_text = ""
        if os.path.exists(jd_store):
            with open(jd_store, "r", encoding="utf-8") as rf:
                jd_text = rf.read()

        result = analyze_candidates(jd_text, candidates)

        return safe_jsonify({
            "status": "ok",
            "jd": result["jd"],
            "candidates": result["candidates"]
        })

    except Exception as e:
        logging.exception("analyze failed")
        return safe_jsonify({"error": "Server error", "detail": str(e)}, 500)


# ---------- START ---------- #
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
