# app.py
import os
import uuid
import tempfile
import json
import logging
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from flask_cors import CORS

from utils.parser import parse_jd_file, parse_resumes_upload, extract_text_from_file
from utils.matcher import analyze_candidates, match_single_resume, calculate_jd_resume_match

# --- Logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# --- App setup ---
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__, static_folder=None)
CORS(app)  # allow all origins; tighten if needed
app.config['UPLOAD_DIR'] = UPLOAD_DIR
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200MB

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "zip"}

# ---------- Helpers ----------
def safe_jsonify(obj, status=200):
    return jsonify(obj), status

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in {e.strip(".") for e in ALLOWED_EXTENSIONS}

# ---------- Routes ----------
@app.route("/health", methods=["GET"])
def health():
    return "OK", 200

@app.route("/api/upload_jd", methods=["POST"])
def upload_jd():
    try:
        if 'jd' not in request.files:
            return safe_jsonify({"error": "Missing 'jd' file"}, 400)
        f = request.files['jd']
        if f.filename == "":
            return safe_jsonify({"error": "Empty filename"}, 400)
        name = secure_filename(f.filename)
        dest = os.path.join(app.config['UPLOAD_DIR'], f"jd_{uuid.uuid4().hex}_{name}")
        f.save(dest)
        logging.info(f"Saved JD -> {dest}")

        jd_text = parse_jd_file(dest) or ""
        jd_store = os.path.join(app.config['UPLOAD_DIR'], 'current_jd.txt')
        with open(jd_store, "w", encoding="utf-8") as wf:
            wf.write(jd_text)

        return safe_jsonify({"status": "ok", "jd_path": dest, "jd_word_count": len(jd_text.split())})
    except Exception as e:
        logging.exception("upload_jd failed")
        return safe_jsonify({"error": "Server error while uploading JD", "detail": str(e)}, 500)

@app.route("/api/upload_resumes", methods=["POST"])
def upload_resumes():
    try:
        files = request.files.getlist('resumes')
        if not files:
            return safe_jsonify({"error": "Missing 'resumes' files"}, 400)

        saved = []
        for f in files:
            if f.filename == "":
                continue
            name = secure_filename(f.filename)
            dest = os.path.join(app.config['UPLOAD_DIR'], f"res_{uuid.uuid4().hex}_{name}")
            f.save(dest)
            saved.append(dest)
            logging.info(f"Saved resume -> {dest}")

        candidates = parse_resumes_upload(saved, app.config['UPLOAD_DIR'])

        cand_file = os.path.join(app.config['UPLOAD_DIR'], 'current_candidates.json')
        with open(cand_file, "w", encoding="utf-8") as wf:
            json.dump(candidates, wf, ensure_ascii=False, indent=2)

        return safe_jsonify({"status": "ok", "files_saved": saved, "parsed_count": len(candidates)})
    except Exception as e:
        logging.exception("upload_resumes failed")
        return safe_jsonify({"error": "Server error while uploading resumes", "detail": str(e)}, 500)

@app.route("/api/analyze", methods=["GET"])
def analyze():
    try:
        cand_file = os.path.join(app.config['UPLOAD_DIR'], 'current_candidates.json')
        jd_store = os.path.join(app.config['UPLOAD_DIR'],'current_jd.txt')

        if not os.path.exists(cand_file):
            return safe_jsonify({"error": "No candidates uploaded. POST /api/upload_resumes first."}, 400)

        with open(cand_file, "r", encoding="utf-8") as rf:
            candidates = json.load(rf)

        jd_text = ""
        if os.path.exists(jd_store):
            with open(jd_store, "r", encoding="utf-8") as rf:
                jd_text = rf.read()

        payload = analyze_candidates(jd_text, candidates)
        # ensure consistent shape
        return safe_jsonify({"status":"ok", "jd": payload.get("jd", {}), "candidates": payload.get("candidates", []), "meta": {"jd_word_count": len(jd_text.split()), "candidates_count": len(candidates)}})
    except Exception as e:
        logging.exception("analyze failed")
        return safe_jsonify({"error": "Server error during analysis", "detail": str(e)}, 500)

@app.route("/api/analyze-text", methods=["POST"])
def analyze_text():
    try:
        data = request.get_json()
        if not data:
            return safe_jsonify({"error": "Invalid or empty JSON"}, 400)

        jd_text = data.get("jd_text", "").strip()
        resume_text = data.get("resume_text", "").strip()

        if not jd_text:
            return safe_jsonify({"error": "Missing jd_text"}, 400)
        if not resume_text:
            return safe_jsonify({"error": "Missing resume_text"}, 400)

        resumes = [r.strip() for r in resume_text.split("---") if r.strip()]

        candidates = []
        for idx, r in enumerate(resumes):
            candidates.append({
                "name": f"Resume {idx+1}",
                "text": r
            })

        payload = analyze_candidates(jd_text, candidates)
        return safe_jsonify({
            "status": "success",
            "jd": payload.get("jd", {}),
            "candidates": payload.get("candidates", []),
            "meta": {"jd_word_count": len(jd_text.split()), "resumes_analyzed": len(resumes)}
        })
    except Exception as e:
        logging.exception("analyze-text failed")
        return safe_jsonify({"error":"Server error during text analysis", "detail": str(e)}, 500)

@app.route("/api/match", methods=["POST"])
def api_match():
    try:
        fuzzy_cutoff = float(request.form.get("fuzzy_cutoff", 0.85))

        # JD extraction
        jd_text = ""
        if 'jd' in request.files:
            jd_file = request.files['jd']
            tmpjd = os.path.join(app.config['UPLOAD_DIR'], f"tmp_jd_{uuid.uuid4().hex}_{secure_filename(jd_file.filename)}")
            jd_file.save(tmpjd)
            jd_text = parse_jd_file(tmpjd)
        else:
            stored = os.path.join(app.config['UPLOAD_DIR'], 'current_jd.txt')
            if os.path.exists(stored):
                with open(stored, "r", encoding="utf-8") as rf:
                    jd_text = rf.read()
        if not jd_text:
            return safe_jsonify({"error":"No JD provided or stored. Upload a 'jd' file or POST /api/upload_jd first."}, 400)

        # Candidates extraction
        candidates = []
        files = request.files.getlist('resumes')
        if files:
            saved = []
            for f in files:
                name = secure_filename(f.filename)
                dest = os.path.join(app.config['UPLOAD_DIR'], f"res_{uuid.uuid4().hex}_{name}")
                f.save(dest)
                saved.append(dest)
            candidates = parse_resumes_upload(saved, app.config['UPLOAD_DIR'])
        else:
            cand_file = os.path.join(app.config['UPLOAD_DIR'], 'current_candidates.json')
            if os.path.exists(cand_file):
                with open(cand_file, "r", encoding="utf-8") as rf:
                    candidates = json.load(rf)

        if not candidates:
            return safe_jsonify({"error":"No resumes provided or stored. Upload resumes or POST /api/upload_resumes first."}, 400)

        results = analyze_candidates(jd_text, candidates, fuzzy_cutoff=fuzzy_cutoff, include_match_breakdown=True)
        return safe_jsonify({
            "status":"ok",
            "jd": results.get("jd", {}),
            "candidates": results.get("candidates", []),
            "meta": {"jd_word_count": len(jd_text.split()), "candidates_count": len(candidates)}
        })
    except Exception as e:
        logging.exception("api_match failed")
        return safe_jsonify({"error":"Server error during match", "detail": str(e)}, 500)

# ---------- Run ----------
if __name__ == "__main__":
    p = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=p)
