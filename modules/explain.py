"""
EXPLAINABLE AI
==============
Local, per-candidate permutation feature importance: for each of the 5
signals that feed the final match_probability (see model.py WEIGHTS), we
reset that one signal to a neutral baseline (0) and measure how much the
score drops. A bigger drop means the model relied on that signal more
heavily for *this specific candidate*. This is the same underlying idea as
SHAP (local, per-instance attribution), computed directly from the
disclosed weighted formula so it is exact, not approximated.
"""
from modules.model import WEIGHTS

FEATURE_LABELS = {
    "category_confidence": "Job-category match (ANN)",
    "jd_similarity": "Text similarity to job description",
    "skill_match_ratio": "Skill overlap",
    "experience_score": "Years of experience",
    "education_score": "Education level",
}


def explain_score(components: dict, weights: dict = None) -> list:
    """Returns a list of {feature, label, contribution, impact_pct} sorted
    by impact, descending."""
    weights = weights or WEIGHTS
    full_score = sum(components[k] * weights[k] for k in weights)

    rows = []
    for key, weight in weights.items():
        contribution = components[key] * weight
        baseline_score = full_score - contribution  # this feature reset to 0
        drop = full_score - baseline_score  # == contribution, kept explicit
        rows.append(
            {
                "feature": key,
                "label": FEATURE_LABELS.get(key, key),
                "value": round(components[key], 4),
                "weight": weight,
                "contribution": round(contribution, 4),
                "impact_pct": round(
                    (drop / full_score * 100) if full_score > 0 else 0, 1
                ),
            }
        )

    rows.sort(key=lambda r: -r["contribution"])
    return rows
