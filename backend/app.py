import os
import uuid
import zipfile
import tempfile
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from utils.parser import parse_jd_file, parse_resumes_upload
from utils.matcher import analyze_candidates, match_single_resume

UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__, static_folder=None)
app.config['UPLOAD_DIR'] = UPLOAD_DIR
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200MB limit

# -----------------------------
# HEALTH CHECK
# -----------------------------
@app.route("/health")
def health():
    return "OK"

# -----------------------------
# UPLOAD JD (PDF/TXT)
# -----------------------------
@app.route("/api/upload_jd", methods=["POST"])
def upload_jd():
    if 'jd' not in request.files:
        return jsonify({"error":"Missing 'jd' file"}), 400
    f = request.files['jd']
    name = secure_filename(f.filename)
    dest = os.path.join(app.config['UPLOAD_DIR'], f"jd_{uuid.uuid4().hex}_{name}")
    f.save(dest)

    jd_text = parse_jd_file(dest)  # parse JD to text

    # Save parsed text
    jd_store = os.path.join(app.config['UPLOAD_DIR'], 'current_jd.txt')
    with open(jd_store, "w", encoding="utf-8") as wf:
        wf.write(jd_text or "")

    return jsonify({"status":"ok", "jd_path": dest}), 200

# -----------------------------
# UPLOAD RESUMES (ZIP/PDF/DOCX)
# -----------------------------
@app.route("/api/upload_resumes", methods=["POST"])
def upload_resumes():
    files = request.files.getlist('resumes')
    if not files:
        return jsonify({"error":"Missing 'resumes' files"}), 400

    saved = []
    for f in files:
        name = secure_filename(f.filename)
        dest = os.path.join(app.config['UPLOAD_DIR'], f"res_{uuid.uuid4().hex}_{name}")
        f.save(dest)
        saved.append(dest)

    # parse resumes
    candidates = parse_resumes_upload(saved, app.config['UPLOAD_DIR'])

    # save parsed data to disk
    import json
    cand_file = os.path.join(app.config['UPLOAD_DIR'], 'current_candidates.json')
    with open(cand_file, "w", encoding="utf-8") as wf:
        json.dump(candidates, wf, ensure_ascii=False, indent=2)

    return jsonify({"status":"ok", "files_saved": saved, "parsed_count": len(candidates)})

# -----------------------------
# RUN ANALYSIS (JD + CANDIDATES)
# -----------------------------
@app.route("/api/analyze", methods=["GET"])
def analyze():
    import json
    jd_store = os.path.join(app.config['UPLOAD_DIR'],'current_jd.txt')
    cand_file = os.path.join(app.config['UPLOAD_DIR'], 'current_candidates.json')

    if not os.path.exists(cand_file):
        return jsonify({"error":"No candidates uploaded. POST /api/upload_resumes first."}), 400

    with open(cand_file, "r", encoding="utf-8") as rf:
        candidates = json.load(rf)

    jd_text = ""
    if os.path.exists(jd_store):
        with open(jd_store, "r", encoding="utf-8") as rf:
            jd_text = rf.read()

    payload = analyze_candidates(jd_text, candidates)
    return jsonify(payload)

# -----------------------------
# NEW ENDPOINT: TEXT INPUT (PASTE JD + RESUME)
# -----------------------------
@app.route("/api/analyze-text", methods=["POST"])
def analyze_text():
    """
    Allows typing/pasting JD and Resume text directly.
    Supports single or multiple resumes separated by ---
    """

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid or empty JSON"}), 400

    jd_text = data.get("jd_text", "").strip()
    resume_text = data.get("resume_text", "").strip()

    if not jd_text:
        return jsonify({"error": "Missing jd_text"}), 400

    if not resume_text:
        return jsonify({"error": "Missing resume_text"}), 400

    # Split resumes by --- (multiple formats)
    resumes = [r.strip() for r in resume_text.split("---") if r.strip()]

    # Convert format to your existing candidate structure
    candidates = []
    for idx, r in enumerate(resumes):
        candidates.append({
            "name": f"Resume {idx+1}",
            "text": r
        })

    # Use your existing engine
    results = analyze_candidates(jd_text, candidates)

    return jsonify({
        "status": "success",
        "jd_word_count": len(jd_text.split()),
        "resumes_analyzed": len(resumes),
        "results": results
    })

# -----------------------------
# OLD SINGLE FILE MATCH (KEEPING)
# -----------------------------
@app.route("/match", methods=["POST"])
def match_route():
    jd_text = request.form.get("jd_text","")
    jd_skills = request.form.get("jd_skills","").split(",") if request.form.get("jd_skills") else []

    if 'resume' not in request.files:
        return jsonify({"error":"Missing resume file"}), 400
    
    f = request.files['resume']
    tmp = os.path.join(app.config['UPLOAD_DIR'], f"tmp_{uuid.uuid4().hex}_{secure_filename(f.filename)}")
    f.save(tmp)

    result = match_single_resume(jd_text, jd_skills, tmp)
    return jsonify(result)

# -----------------------------
# RUN APP
# -----------------------------
if __name__ == "__main__":
    p = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=p)
