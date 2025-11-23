from flask import Flask, request, jsonify
import tempfile
from utils.matcher import process_resume

app = Flask(__name__)

# Example list of required skills from JD
# You will pass this from frontend in real use
def extract_jd_skills(jd_text):
    skills = [s.strip() for s in jd_text.split(",")]
    return skills

@app.route("/match", methods=["POST"])
def match():
    jd_text = request.form.get("jd_text")
    jd_skills = extract_jd_skills(request.form.get("jd_skills"))

    uploaded_file = request.files["resume"]
    temp_path = tempfile.mktemp(suffix=".docx")
    uploaded_file.save(temp_path)

    result = process_resume(jd_text, jd_skills, temp_path)
    return jsonify(result)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
