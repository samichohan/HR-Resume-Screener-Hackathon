import os
import re
import uuid
from flask import Flask, request, jsonify, render_template, send_file, abort

from modules import parser, features, database
from modules.model import get_matcher
from modules.explain import explain_score
from modules.llm import generate_explanation
from modules.report import build_report

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "instance", "uploads")
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_FILE_SIZE_MB = 8

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 40 * 1024 * 1024  # 40MB total request cap

os.makedirs(UPLOAD_DIR, exist_ok=True)
database.init_db()
matcher = get_matcher()  # loads (or trains) the ANN once at startup

# The ANN is trained on the 25 categories in the dataset. These aliases let
# HR pick a common role title that isn't one of those 25 labels directly;
# under the hood it's scored against the closest real trained category.
# This mapping is disclosed in the UI, not hidden.
ROLE_ALIASES = {
    "AI Engineer": "Data Science",
    "Machine Learning Engineer": "Data Science",
    "Backend Developer": "Python Developer",
    "Full Stack Developer": "Java Developer",
    "QA Engineer": "Testing",
}


_NON_NAME_HINTS = (
    "developer", "engineer", "skills", "resume", "curriculum", "manager",
    "analyst", "consultant", "designer", "specialist", "administrator",
    "summary", "objective", "profile", "experience", "education",
)


def guess_candidate_name(resume_text: str, filename: str) -> str:
    """Best-effort candidate name: first plausible header line, else filename.
    Real resumes in the training-style dataset often open with a skills/role
    header rather than a name, so we skip lines that look like job titles."""
    first_lines = [l.strip() for l in resume_text.splitlines()[:8] if l.strip()]
    for line in first_lines:
        words = line.split()
        lower = line.lower()
        if (
            1 < len(words) <= 4
            and not any(ch.isdigit() for ch in line)
            and "@" not in line
            and len(line) < 40
            and not any(hint in lower for hint in _NON_NAME_HINTS)
        ):
            return line.title()
    stem = os.path.splitext(filename)[0]
    return re.sub(r"[_\-]+", " ", stem).title()


@app.route("/")
def index():
    return render_template(
        "index.html", categories=matcher.categories, role_aliases=ROLE_ALIASES,
    )


@app.route("/api/model-info")
def model_info():
    return jsonify(matcher.metrics)


SAMPLE_DIR = os.path.join(BASE_DIR, "sample_data")
SAMPLE_FILES = {
    "job_description": "job_description.txt",
    "job_description_ai_engineer": "job_description_ai_engineer.txt",
    "strong_fit": "resume_strong_fit.txt",
    "weak_fit": "resume_weak_fit.txt",
}


@app.route("/api/sample/<key>")
def sample(key):
    filename = SAMPLE_FILES.get(key)
    if not filename:
        abort(404)
    path = os.path.join(SAMPLE_DIR, filename)
    if not os.path.exists(path):
        abort(404)
    with open(path, "r", encoding="utf-8") as f:
        return f.read(), 200, {"Content-Type": "text/plain; charset=utf-8"}


@app.route("/api/screen", methods=["POST"])
def screen():
    job_description = request.form.get("job_description", "").strip()
    target_category = request.form.get("target_category", "").strip()
    files = request.files.getlist("resumes")

    if not job_description:
        return jsonify({"error": "Job description is required."}), 400
    if not files:
        return jsonify({"error": "Upload at least one resume."}), 400

    if not target_category or target_category == "auto":
        target_category = matcher.infer_target_category(job_description)
    elif target_category in ROLE_ALIASES:
        target_category = ROLE_ALIASES[target_category]

    session_id = database.create_session(job_description, target_category)
    session_dir = os.path.join(UPLOAD_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)

    results = []
    errors = []

    for file in files:
        if not file or not file.filename:
            continue
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            errors.append({"filename": file.filename, "error": f"Unsupported type {ext}"})
            continue

        safe_name = f"{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(session_dir, safe_name)
        file.save(file_path)

        try:
            resume_text = parser.extract_text(file_path)
        except parser.ParseError as e:
            errors.append({"filename": file.filename, "error": str(e)})
            continue

        tabular = features.build_features(resume_text, job_description)
        result = matcher.score(resume_text, job_description, target_category, tabular)
        xai_rows = explain_score(result["components"])
        result["xai_rows"] = xai_rows

        candidate_name = guess_candidate_name(resume_text, file.filename)
        explanation = generate_explanation(
            candidate_name, result["match_probability"], target_category,
            xai_rows, tabular["matched_skills"], tabular["missing_skills"],
        )

        candidate_id = database.insert_candidate(
            session_id, file.filename, candidate_name, result, explanation,
            tabular["matched_skills"], tabular["missing_skills"],
            tabular["years_experience"],
        )
        results.append(database.get_candidate(candidate_id))

    return jsonify({
        "session_id": session_id,
        "target_category": target_category,
        "candidates": results,
        "errors": errors,
        "model_accuracy": matcher.metrics["test_accuracy"],
    })


@app.route("/api/candidates/<session_id>")
def get_candidates(session_id):
    session = database.get_session(session_id)
    if not session:
        abort(404)
    return jsonify({
        "session": session,
        "candidates": database.get_candidates_by_session(session_id),
    })


@app.route("/api/hitl/<candidate_id>", methods=["POST"])
def hitl_decision(candidate_id):
    data = request.get_json(force=True) or {}
    decision = data.get("decision")
    note = data.get("note", "")
    if decision not in ("approved", "rejected", "edited"):
        return jsonify({"error": "decision must be approved, rejected, or edited"}), 400
    ok = database.update_hitl_decision(candidate_id, decision, note)
    if not ok:
        abort(404)
    return jsonify(database.get_candidate(candidate_id))


@app.route("/api/report/<session_id>")
def report(session_id):
    session = database.get_session(session_id)
    candidates = database.get_candidates_by_session(session_id)
    if not session or not candidates:
        abort(404)
    pdf_bytes = build_report(session, candidates)
    filename = f"screening_report_{session_id[:8]}.pdf"
    return send_file(
        os_path_or_bytesio(pdf_bytes), mimetype="application/pdf",
        as_attachment=True, download_name=filename,
    )


def os_path_or_bytesio(data: bytes):
    import io
    return io.BytesIO(data)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
