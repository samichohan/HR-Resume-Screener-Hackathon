"""
Modality 2: TABULAR   -> years_experience, education_score, certifications_count, skill_match_ratio
Modality 3: TEXT/NLP  -> jd_similarity (TF-IDF cosine similarity between resume and job description)

These are the interpretable signals that feed the final match score alongside
the ANN's category-classification confidence (see model.py).
"""
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# A broad, category-agnostic skills vocabulary spanning every job family present
# in the training dataset (engineering, data, sales, HR, legal, health, etc.).
# This keeps skill-matching useful for *any* job description, not just tech roles.
SKILLS_VOCAB = [
    # software / data
    "python", "java", "javascript", "typescript", "c++", "c#", "sql", "nosql",
    "react", "angular", "vue", "node.js", "django", "flask", "spring", ".net",
    "html", "css", "rest api", "graphql", "docker", "kubernetes", "git",
    "aws", "azure", "gcp", "jenkins", "ci/cd", "terraform", "ansible", "linux",
    "hadoop", "spark", "kafka", "airflow", "etl", "data warehouse", "tableau",
    "power bi", "machine learning", "deep learning", "nlp", "tensorflow",
    "pytorch", "scikit-learn", "pandas", "numpy", "statistics", "a/b testing",
    "selenium", "junit", "automation testing", "manual testing", "jira",
    "agile", "scrum", "blockchain", "solidity", "smart contracts", "sap",
    "salesforce", "oracle", "mongodb", "postgresql", "mysql", "excel",
    "network security", "firewall", "penetration testing", "cybersecurity",
    # engineering
    "autocad", "solidworks", "matlab", "plc", "hvac", "civil engineering",
    "structural design", "circuit design", "embedded systems", "cad",
    "manufacturing", "six sigma", "quality control", "project management",
    "pmo", "pmp", "cost estimation", "supply chain",
    # business / HR / sales
    "recruitment", "onboarding", "payroll", "employee relations",
    "performance management", "talent acquisition", "negotiation",
    "business analysis", "requirements gathering", "stakeholder management",
    "sales", "crm", "lead generation", "account management", "marketing",
    "digital marketing", "seo", "content strategy", "customer service",
    "operations management", "budgeting", "forecasting", "financial analysis",
    # legal / health / arts
    "litigation", "contract law", "legal research", "compliance",
    "patient care", "clinical", "nutrition", "physiotherapy", "fitness training",
    "graphic design", "adobe photoshop", "illustrator", "figma", "ui/ux",
    "video editing", "content writing", "communication", "leadership",
    "presentation skills", "team management", "problem solving",
]

_DEGREE_PATTERNS = [
    (r"\b(ph\.?d|doctorate)\b", 1.0),
    (r"\b(m\.?tech|m\.?s\b|master'?s|mba|m\.?sc|m\.?a\b)\b", 0.8),
    (r"\b(b\.?tech|b\.?e\b|bachelor'?s|b\.?sc|b\.?a\b|b\.?com)\b", 0.6),
    (r"\b(diploma|associate degree)\b", 0.4),
    (r"\b(high school|hsc|secondary school)\b", 0.2),
]

_CERT_PATTERN = re.compile(
    r"\b(certified|certification|certificate)\b", re.IGNORECASE
)
_EXPERIENCE_PATTERN = re.compile(
    r"(\d{1,2})\+?\s*(?:years?|yrs?)\b", re.IGNORECASE
)


def extract_skills(text: str) -> set:
    text_lower = text.lower()
    return {skill for skill in SKILLS_VOCAB if skill in text_lower}


def estimate_years_experience(text: str) -> float:
    matches = _EXPERIENCE_PATTERN.findall(text)
    if not matches:
        return 0.0
    years = [int(m) for m in matches]
    return float(min(max(years), 25))  # cap at 25 to avoid outliers


def estimate_education_score(text: str) -> float:
    text_lower = text.lower()
    for pattern, score in _DEGREE_PATTERNS:
        if re.search(pattern, text_lower):
            return score
    return 0.1  # no recognizable education keyword found


def count_certifications(text: str) -> int:
    return len(_CERT_PATTERN.findall(text))


def jd_similarity(resume_text: str, jd_text: str) -> float:
    """TF-IDF cosine similarity between the resume and the job description
    (Modality: Text/NLP)."""
    if not jd_text.strip():
        return 0.0
    vectorizer = TfidfVectorizer(stop_words="english", max_features=2000)
    try:
        matrix = vectorizer.fit_transform([resume_text, jd_text])
    except ValueError:
        return 0.0
    sim = cosine_similarity(matrix[0:1], matrix[1:2])[0][0]
    return float(sim)


def build_features(resume_text: str, jd_text: str) -> dict:
    """Builds the full tabular + text/NLP feature set for one resume vs one JD."""
    resume_skills = extract_skills(resume_text)
    jd_skills = extract_skills(jd_text) if jd_text.strip() else set()

    if jd_skills:
        matched = resume_skills & jd_skills
        missing = jd_skills - resume_skills
        skill_match_ratio = len(matched) / len(jd_skills)
    else:
        matched, missing = set(), set()
        skill_match_ratio = 0.0

    return {
        "years_experience": estimate_years_experience(resume_text),
        "education_score": estimate_education_score(resume_text),
        "certifications_count": count_certifications(resume_text),
        "skill_match_ratio": round(skill_match_ratio, 4),
        "jd_similarity": round(jd_similarity(resume_text, jd_text), 4),
        "matched_skills": sorted(matched),
        "missing_skills": sorted(missing),
        "resume_skills": sorted(resume_skills),
    }
