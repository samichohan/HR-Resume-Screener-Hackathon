"""
LLM — reasoning / explanation ONLY, never the predictive engine.
=================================================================
Called *after* the ANN + weighted formula have already produced
match_probability and the XAI breakdown. All this module does is phrase
those already-computed numbers as a short paragraph for a recruiter.

If ANTHROPIC_API_KEY is not set, a clear template is used instead, so the
app always works end-to-end with zero external dependencies.
"""
import os

try:
    import anthropic
    _HAS_SDK = True
except ImportError:
    _HAS_SDK = False


def _template_explanation(candidate_name: str, match_probability: float,
                           target_category: str, xai_rows: list,
                           matched_skills: list, missing_skills: list) -> str:
    pct = round(match_probability * 100)
    top_driver = xai_rows[0]["label"] if xai_rows else "overall profile"

    if match_probability >= 0.7:
        verdict = "a strong fit"
    elif match_probability >= 0.45:
        verdict = "a moderate fit"
    else:
        verdict = "a weak fit"

    skills_line = ""
    if matched_skills:
        skills_line = f" Matched skills include {', '.join(matched_skills[:6])}."
    if missing_skills:
        skills_line += f" Missing from the resume: {', '.join(missing_skills[:6])}."

    return (
        f"{candidate_name} scores {pct}% for the {target_category} role, "
        f"making them {verdict}. The strongest driver of this score is "
        f"{top_driver.lower()}.{skills_line} This score is a suggestion — "
        f"please review the full breakdown before making a decision."
    )


def generate_explanation(candidate_name: str, match_probability: float,
                          target_category: str, xai_rows: list,
                          matched_skills: list, missing_skills: list) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key or not _HAS_SDK:
        return _template_explanation(
            candidate_name, match_probability, target_category, xai_rows,
            matched_skills, missing_skills,
        )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        xai_summary = "; ".join(
            f"{r['label']}: {r['value']} (contributes {r['impact_pct']}%)"
            for r in xai_rows
        )
        prompt = (
            f"You are helping a recruiter understand an AI resume-screening "
            f"result. Do not invent any numbers. Candidate: {candidate_name}. "
            f"Target role: {target_category}. Match probability computed by "
            f"the model: {match_probability:.2f}. Feature contributions: "
            f"{xai_summary}. Matched skills: {', '.join(matched_skills) or 'none'}. "
            f"Missing skills: {', '.join(missing_skills) or 'none'}. "
            f"Write a 2-3 sentence, plain-English explanation of this score "
            f"for a recruiter, referencing only the numbers given. End by "
            f"reminding them this is a suggestion, not a decision."
        )
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=220,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            block.text for block in response.content if block.type == "text"
        ).strip()
    except Exception:
        # Never let an LLM/network hiccup break the screening pipeline.
        return _template_explanation(
            candidate_name, match_probability, target_category, xai_rows,
            matched_skills, missing_skills,
        )
