import os
import csv
import zipfile
from .helpers import extract_text_from_docx, extract_text_from_pdf, safe_read_text

def parse_jd_file(path):
    # basic: txt or pdf
    ext = os.path.splitext(path)[1].lower()
    if ext in (".txt",):
        return safe_read_text(path)
    if ext in (".pdf",):
        return extract_text_from_pdf(path)
    # default
    return safe_read_text(path)

def parse_resumes_upload(saved_paths, workdir):
    """
    Accepts list of file paths (zip/pdf/docx/csv). Returns list of parsed candidate dicts:
    [{"name":..., "email":..., "skills":[...], "experience":n, "raw_text":...}, ...]
    """
    candidates = []
    for p in saved_paths:
        ext = os.path.splitext(p)[1].lower()
        if ext == ".zip":
            try:
                with zipfile.ZipFile(p, "r") as z:
                    z.extractall(workdir)
                    # find files extracted and parse them
                    for name in z.namelist():
                        fpath = os.path.join(workdir, name)
                        if os.path.isfile(fpath):
                            candidates.extend(parse_resumes_upload([fpath], workdir))
            except Exception:
                continue
        elif ext in (".csv",):
            # parse CSV expecting columns like name, skills, email, experience
            try:
                import pandas as pd
                df = pd.read_csv(p)
                for _, row in df.iterrows():
                    skills = []
                    if 'skills' in row and not pd.isna(row['skills']):
                        skills = [s.strip() for s in str(row['skills']).split(",") if s.strip()]
                    candidates.append({
                        "name": str(row.get('name','')) if 'name' in row else '',
                        "email": str(row.get('email','')) if 'email' in row else '',
                        "skills": skills,
                        "experience": float(row.get('experience', 0)) if 'experience' in row else 0,
                        "raw_text": str(row.get('resume_text','')) if 'resume_text' in row else ''
                    })
            except Exception:
                continue
        elif ext in (".docx",):
            text = extract_text_from_docx(p)
            candidates.append({"name":"","email":"","skills":[], "experience":0,"raw_text": text})
        elif ext in (".pdf",):
            text = extract_text_from_pdf(p)
            candidates.append({"name":"","email":"","skills":[], "experience":0,"raw_text": text})
        else:
            # generic attempt to read text
            try:
                text = safe_read_text(p)
                candidates.append({"name":"","email":"","skills":[], "experience":0,"raw_text": text})
            except Exception:
                continue
    return candidates
