import os
import uuid
import tempfile
import json
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

from utils.parser import parse_jd_file, parse_resumes_upload, extract_text_from_file
from utils.matcher import analyze_candidates, match_single_resume, calculate_jd_resume_match

UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__, static_folder=None)
app.config['UPLOAD_DIR'] = UPLOAD_DIR
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200MB limit

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "zip"}

# -----------------------------
# HEALTH CHECK
# -----------------------------
@app.route("/health")
def health():
    return "OK"

# -----------------------------
# UPLOAD JD (PDF/TXT/DOCX)
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

    return jsonify({"status":"ok", "jd_path": dest, "jd_word_count": len((jd_text or "").split())}), 200

# -----------------------------
# UPLOAD RESUMES (ZIP/PDF/DOCX/TXT)
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
    cand_file = os.path.join(app.config['UPLOAD_DIR'], 'current_candidates.json')
    with open(cand_file, "w", encoding="utf-8") as wf:
        json.dump(candidates, wf, ensure_ascii=False, indent=2)

    return jsonify({"status":"ok", "files_saved": saved, "parsed_count": len(candidates)})

# -----------------------------
# RUN ANALYSIS (JD + CANDIDATES)
# -----------------------------
@app.route("/api/analyze", methods=["GET"])
def analyze():
    cand_file = os.path.join(app.config['UPLOAD_DIR'], 'current_candidates.json')
    jd_store = os.path.join(app.config['UPLOAD_DIR'],'current_jd.txt')

    if not os.path.exists(cand_file):
        return jsonify({"error":"No candidates uploaded. POST /api/upload_resumes first."}), 400

    with open(cand_file, "r", encoding="utf-8") as rf:
        candidates = json.load(rf)

    jd_text = ""
    if os.path.exists(jd_store):
        with open(jd_store, "r", encoding="utf-8") as rf:
            jd_text = rf.read()

    # analyze_candidates will return detailed matching results per candidate (see utils/matcher)
    payload = analyze_candidates(jd_text, candidates)
    return jsonify(payload)

# -----------------------------
# NEW ENDPOINT: Analyze JD + resume text pasted (multiple resumes supported)
# -----------------------------
@app.route("/api/analyze-text", methods=["POST"])
def analyze_text():
    """
    Allows typing/pasting JD and Resume text directly.
    Supports single or multiple resumes separated by '---'
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

    resumes = [r.strip() for r in resume_text.split("---") if r.strip()]

    candidates = []
    for idx, r in enumerate(resumes):
        candidates.append({
            "name": f"Resume {idx+1}",
            "text": r
        })

    results = analyze_candidates(jd_text, candidates)
    return jsonify({
        "status": "success",
        "jd_word_count": len(jd_text.split()),
        "resumes_analyzed": len(resumes),
        "results": results
    })

# -----------------------------
# OLD SINGLE FILE MATCH (KEPT)
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
# NEW: MATCH endpoint - upload JD (or use stored JD) and resumes (one or many)
# returns match percent + breakdown per candidate
# -----------------------------
@app.route("/api/match", methods=["POST"])
def api_match():
    """
    Accepts:
      - jd file (jd) OR uses stored current_jd.txt if missing
      - resumes: multiple files in 'resumes' (pdf/docx/txt/zip) OR uses stored current_candidates.json if missing
      - fuzzy_cutoff: optional (float)
    """
    fuzzy_cutoff = float(request.form.get("fuzzy_cutoff", 0.85))

    # ----- JD extraction -----
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
        return jsonify({"error":"No JD provided or stored. Upload a 'jd' file or POST /api/upload_jd first."}), 400

    # ----- Candidates extraction -----
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
        # try stored candidates
        cand_file = os.path.join(app.config['UPLOAD_DIR'], 'current_candidates.json')
        if os.path.exists(cand_file):
            with open(cand_file, "r", encoding="utf-8") as rf:
                candidates = json.load(rf)

    if not candidates:
        return jsonify({"error":"No resumes provided or stored. Upload resumes or POST /api/upload_resumes first."}), 400

    # ----- Run analysis with matching score -----
    results = analyze_candidates(jd_text, candidates, fuzzy_cutoff=fuzzy_cutoff, include_match_breakdown=True)
    return jsonify({
        "ok": True,
        "jd_word_count": len(jd_text.split()),
        "candidates_count": len(candidates),
        "results": results
    })


# -----------------------------
# RUN APP
# -----------------------------
if __name__ == "__main__":
    p = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=p)
