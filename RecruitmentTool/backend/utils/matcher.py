import re
import pandas as pd
from docx import Document

# Extract text from DOCX
def extract_text_from_docx(file_path):
    doc = Document(file_path)
    return "\n".join([para.text for para in doc.paragraphs])

# Extract email from resume text
def extract_email(text):
    match = re.search(r"[a-zA-Z0-9+._%-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    return match.group(0) if match else "Not Found"

# Extract years of experience
def extract_experience(text):
    match = re.search(r"(\d+)\+?\s*(years|year|yrs)", text.lower())
    return int(match.group(1)) if match else 0

# Skill matching
def match_skills(jd_skills, resume_text):
    resume_text = resume_text.lower()
    matches = [skill for skill in jd_skills if skill.lower() in resume_text]
    percentage = (len(matches) / len(jd_skills)) * 100 if jd_skills else 0
    return matches, round(percentage, 2)

# MAIN PIPELINE
def process_resume(jd_text, jd_skills, resume_path):
    text = extract_text_from_docx(resume_path)

    email = extract_email(text)
    experience = extract_experience(text)
    matched_skills, score = match_skills(jd_skills, text)

    return {
        "email": email,
        "experience_found": experience,
        "jd_vs_resume_score": score,
        "skills_matched": matched_skills,
    }
