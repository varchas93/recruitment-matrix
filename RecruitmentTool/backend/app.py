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

# Simple health
@app.route("/health")
def health():
    return "OK"

# Upload JD (pdf/txt). Saves file and stores parsed text in memory (or disc)
@app.route("/api/upload_jd", methods=["POST"])
def upload_jd():
    if 'jd' not in request.files:
        return jsonify({"error":"Missing 'jd' file"}), 400
    f = request.files['jd']
    name = secure_filename(f.filename)
    dest = os.path.join(app.config['UPLOAD_DIR'], f"jd_{uuid.uuid4().hex}_{name}")
    f.save(dest)
    jd_text = parse_jd_file(dest)  # returns text
    # store JD text to a simple temp file (could be improved to DB)
    jd_store = os.path.join(app.config['UPLOAD_DIR'],'current_jd.txt')
    with open(jd_store, "w", encoding="utf-8") as wf:
        wf.write(jd_text or "")
    return jsonify({"status":"ok", "jd_path": dest}), 200

# Upload resumes (accepts zip, csv, pdf, docx)
@app.route("/api/upload_resumes", methods=["POST"])
def upload_resumes():
    # "resumes" may be multiple files
    files = request.files.getlist('resumes')
    if not files:
        return jsonify({"error":"Missing 'resumes' files"}), 400

    saved = []
    for f in files:
        name = secure_filename(f.filename)
        dest = os.path.join(app.config['UPLOAD_DIR'], f"res_{uuid.uuid4().hex}_{name}")
        f.save(dest)
        saved.append(dest)

    # parse saved files into candidate dict list
    candidates = parse_resumes_upload(saved, app.config['UPLOAD_DIR'])
    # persist parsed candidates to disk for /api/analyze
    import json
    cand_file = os.path.join(app.config['UPLOAD_DIR'], 'current_candidates.json')
    with open(cand_file, "w", encoding="utf-8") as wf:
        json.dump(candidates, wf, ensure_ascii=False, indent=2)
    return jsonify({"status":"ok","files_saved": saved, "parsed_count": len(candidates)})

# Analyze: reads stored JD & parsed candidates, runs analysis and returns dashboard payload
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

    # run the analysis engine (returns dashboard payload)
    payload = analyze_candidates(jd_text, candidates)
    return jsonify(payload)

# Optional demo endpoint - returns demo JSON and includes a local path to the file you uploaded
@app.route("/api/demo", methods=["GET"])
def demo():
    # Developer note: include the uploaded file local path per instruction
    demo_image_local_path = "/mnt/data/05feef5d-174b-40f4-a5c3-2d166fc3b7cd.png"
    # sample demo JSON (frontend can transform local path to a served URL)
    demo_json = {
        "message": "Demo data for dashboard",
        "roles_count": 2,
        "profiles_count": 4,
        "avg_gap_percent": 23.5,
        "avg_match_percent": 76.4,
        "skill_gap_by_role": {"labels":["Dev","Analyst"], "data":[20,28]},
        "top_missing_skills": [{"skill":"cloud","count":3},{"skill":"spark","count":2}],
        "candidates": [
            {"name":"Alice","match":82.3,"missing":["cloud"],"email":"alice@example.com"},
            {"name":"Bob","match":65.4,"missing":["spark","ml"],"email":"bob@example.com"}
        ],
        "heatmap": {"rows":["A","B"], "cols":["python","sql"], "values":[[0.8,0.6],[0.4,0.9]]},
        "preview_image_local_path": demo_image_local_path
    }
    return jsonify(demo_json)

# Keep single-match endpoint for quick testing (existing behavior)
@app.route("/match", methods=["POST"])
def match_route():
    # same interface used earlier: jd_text, jd_skills, resume (single)
    jd_text = request.form.get("jd_text","")
    jd_skills = request.form.get("jd_skills","").split(",") if request.form.get("jd_skills") else []
    if 'resume' not in request.files:
        return jsonify({"error":"Missing resume file"}), 400
    f = request.files['resume']
    tmp = os.path.join(app.config['UPLOAD_DIR'], f"tmp_{uuid.uuid4().hex}_{secure_filename(f.filename)}")
    f.save(tmp)
    result = match_single_resume(jd_text, jd_skills, tmp)
    return jsonify(result)

if __name__ == "__main__":
    # use port 5000 (Render uses PORT env var)
    p = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=p)
