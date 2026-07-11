"""
THE DEEP LEARNING ENGINE (ANN)
================================
A real feed-forward neural network (sklearn MLPClassifier: 2 hidden layers,
ReLU activations, trained with Adam/backprop) trained on a REAL, public
resume dataset:

    data/UpdatedResumeDataSet.csv
    962 real resumes, labelled across 25 job categories.
    Source: Kaggle "Resume Dataset" (gauravduttakiit/resume-dataset),
    a widely used dataset for resume-classification research.

WHAT THE ANN PREDICTS
----------------------
The ANN is trained as a resume-category classifier: given the TF-IDF
representation of a resume's text, it predicts a probability distribution
over the 25 job categories (Java Developer, Data Science, HR, ...).

WHY THIS IS THE RIGHT "PREDICTIVE ENGINE" FOR RESUME-TO-JD MATCHING
----------------------------------------------------------------------
When HR runs a screening job, they pick the target category the job
description belongs to (or we infer it automatically from the JD text
using the same trained ANN). The ANN's predicted probability for that
specific category on a given resume IS the model's real, learned signal
for "does this resume look like it belongs to this job family" -- trained
end-to-end on real labelled data, with a real held-out accuracy score
(see train() below, printed at training time).

That probability is then combined with three fully-interpretable,
independently computed signals (skill overlap, TF-IDF similarity to the
JD text, experience/education signals) into the final match_probability.
The combination weights are fixed and disclosed (not hidden), which is
what makes explain.py's per-candidate breakdown meaningful rather than
decorative.
"""
import os
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neural_network import MLPClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from sklearn.preprocessing import LabelEncoder

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "UpdatedResumeDataSet.csv")
MODEL_DIR = os.path.join(BASE_DIR, "instance", "model")
VECTORIZER_PATH = os.path.join(MODEL_DIR, "tfidf_vectorizer.joblib")
CLASSIFIER_PATH = os.path.join(MODEL_DIR, "ann_classifier.joblib")
LABEL_ENCODER_PATH = os.path.join(MODEL_DIR, "label_encoder.joblib")
METRICS_PATH = os.path.join(MODEL_DIR, "training_metrics.json")

# Fixed, disclosed weights for the final match score.
# category_confidence: how strongly the ANN recognises this resume as the
#                       target job family (the deep-learning signal)
# jd_similarity:        raw TF-IDF overlap between resume text and JD text
# skill_match_ratio:    fraction of JD's named skills found in the resume
# experience_score:     normalised years-of-experience signal
# education_score:      normalised education-level signal
WEIGHTS = {
    "category_confidence": 0.40,
    "jd_similarity": 0.20,
    "skill_match_ratio": 0.25,
    "experience_score": 0.10,
    "education_score": 0.05,
}


def _clean_text(text: str) -> str:
    text = text.lower()
    return text


def train(random_state: int = 42, verbose: bool = True) -> dict:
    """Trains the ANN on the real dataset and persists it to instance/model/.
    Returns a dict of training metrics."""
    os.makedirs(MODEL_DIR, exist_ok=True)

    df = pd.read_csv(DATA_PATH)
    df = df.dropna(subset=["Category", "Resume"])
    df["clean_resume"] = df["Resume"].astype(str).apply(_clean_text)

    label_encoder = LabelEncoder()
    y = label_encoder.fit_transform(df["Category"])

    vectorizer = TfidfVectorizer(
        stop_words="english", max_features=4000, ngram_range=(1, 2), min_df=2
    )
    X = vectorizer.fit_transform(df["clean_resume"])

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=random_state, stratify=y
    )

    clf = MLPClassifier(
        hidden_layer_sizes=(128, 64),
        activation="relu",
        solver="adam",
        alpha=1e-4,
        max_iter=400,
        random_state=random_state,
    )
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    test_accuracy = float(accuracy_score(y_test, y_pred))
    report = classification_report(
        y_test, y_pred, target_names=label_encoder.classes_, output_dict=True,
        zero_division=0,
    )

    joblib.dump(vectorizer, VECTORIZER_PATH)
    joblib.dump(clf, CLASSIFIER_PATH)
    joblib.dump(label_encoder, LABEL_ENCODER_PATH)

    metrics = {
        "dataset": "UpdatedResumeDataSet.csv (real, 962 labelled resumes, 25 categories)",
        "n_samples": int(len(df)),
        "n_train": int(X_train.shape[0]),
        "n_test": int(X_test.shape[0]),
        "n_categories": int(len(label_encoder.classes_)),
        "test_accuracy": round(test_accuracy, 4),
        "architecture": "MLPClassifier(hidden_layer_sizes=(128,64), activation=relu, solver=adam)",
        "categories": list(label_encoder.classes_),
    }
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2)

    if verbose:
        print(f"[model.py] Trained ANN on {len(df)} real resumes.")
        print(f"[model.py] Held-out test accuracy: {test_accuracy:.4f}")

    return metrics


class ResumeMatcher:
    """Loads the trained ANN + vectorizer once and serves predictions."""

    def __init__(self):
        if not (
            os.path.exists(VECTORIZER_PATH)
            and os.path.exists(CLASSIFIER_PATH)
            and os.path.exists(LABEL_ENCODER_PATH)
        ):
            train(verbose=True)
        self.vectorizer = joblib.load(VECTORIZER_PATH)
        self.clf = joblib.load(CLASSIFIER_PATH)
        self.label_encoder = joblib.load(LABEL_ENCODER_PATH)
        with open(METRICS_PATH) as f:
            self.metrics = json.load(f)
        self.categories = list(self.label_encoder.classes_)

    def category_probabilities(self, resume_text: str) -> dict:
        """Runs the real ANN forward pass -> probability per job category."""
        vec = self.vectorizer.transform([_clean_text(resume_text)])
        probs = self.clf.predict_proba(vec)[0]
        return {cat: float(p) for cat, p in zip(self.categories, probs)}

    def infer_target_category(self, jd_text: str) -> str:
        """When HR doesn't pick a category explicitly, classify the JD text
        itself through the same ANN to find the closest job family."""
        probs = self.category_probabilities(jd_text)
        return max(probs, key=probs.get)

    def score(self, resume_text: str, jd_text: str, target_category: str,
              tabular: dict) -> dict:
        """Combines the ANN's category confidence with the interpretable
        tabular/text signals into the final, disclosed match_probability."""
        cat_probs = self.category_probabilities(resume_text)
        category_confidence = cat_probs.get(target_category, 0.0)

        experience_score = min(tabular["years_experience"] / 10.0, 1.0)
        education_score = tabular["education_score"]

        components = {
            "category_confidence": category_confidence,
            "jd_similarity": tabular["jd_similarity"],
            "skill_match_ratio": tabular["skill_match_ratio"],
            "experience_score": experience_score,
            "education_score": education_score,
        }

        match_probability = sum(
            components[k] * WEIGHTS[k] for k in WEIGHTS
        )
        match_probability = float(np.clip(match_probability, 0.0, 1.0))

        # top-3 category guesses, useful context in the UI
        top_categories = sorted(cat_probs.items(), key=lambda kv: -kv[1])[:3]

        return {
            "match_probability": round(match_probability, 4),
            "target_category": target_category,
            "category_confidence": round(category_confidence, 4),
            "top_categories": [
                {"category": c, "probability": round(p, 4)} for c, p in top_categories
            ],
            "components": components,
            "weights": WEIGHTS,
        }


_matcher_singleton = None


def get_matcher() -> ResumeMatcher:
    global _matcher_singleton
    if _matcher_singleton is None:
        _matcher_singleton = ResumeMatcher()
    return _matcher_singleton


if __name__ == "__main__":
    train()
