# 🚀 SCREEN — AI Resume Screening Desk

An AI-powered Resume Screening and Candidate Matching platform built for the **AI Innovation Hackathon**. The system uses **Deep Learning**, **Natural Language Processing**, **Explainable AI (XAI)**, and a **Human-in-the-Loop (HITL)** workflow to help recruiters automatically screen resumes against job descriptions.

## 🌐 Live Demo

**🔗 Live Application:**  
https://hr-resume-screener-hackathon-production.up.railway.app/

---

# 📌 Overview

SCREEN is an intelligent recruitment assistant that analyzes resumes, predicts the most suitable job category using a trained Artificial Neural Network (ANN), compares candidates against a job description, explains every decision using Explainable AI, and allows recruiters to approve or reject recommendations through a Human-in-the-Loop workflow.

Unlike traditional keyword matching systems, SCREEN combines multiple AI techniques into a production-ready web application.

---

# ✨ Features

- 📄 Resume Parsing (PDF, DOCX, TXT)
- 🧠 Deep Learning Resume Classification (ANN)
- 🤖 Automatic Role Detection from Job Description
- 🎯 Resume vs Job Description Matching
- 📊 Explainable AI (Confidence Score & Score Breakdown)
- 👨‍💼 Human-in-the-Loop Decision Workflow
- 📝 AI Generated Candidate Summary
- 📥 Downloadable PDF Report
- 🌐 Modern Responsive Web Interface
- 💾 SQLite Database Integration

---

# 🧠 AI Pipeline

```
Recruiter Uploads Job Description
            │
            ▼
Auto Role Detection (ANN)
            │
            ▼
Candidate Resume Upload
            │
            ▼
Resume Parser
            │
            ▼
Feature Extraction
            │
            ▼
ANN Resume Classification
            │
            ▼
Resume ↔ JD Similarity
            │
            ▼
Match Probability
            │
            ▼
Explainable AI
            │
            ▼
Human Review
            │
            ▼
PDF Report Generation
```

---

# 🏗️ Technologies Used

## Backend

- Python
- Flask
- Scikit-learn
- NumPy
- Pandas
- Joblib
- SQLite
- ReportLab

## AI / Machine Learning

- Artificial Neural Network (MLPClassifier)
- TF-IDF Vectorization
- Cosine Similarity
- NLP
- Explainable AI

## Frontend

- HTML5
- CSS3
- JavaScript

---

# 📂 Dataset

The model is trained using the **Resume Dataset** originally published on Kaggle.

**Dataset**

- 962 Real Resumes
- 25 Job Categories

Examples include:

- Data Science
- Java Developer
- HR
- Mechanical Engineer
- Testing
- Advocate
- Python Developer
- DevOps
- Business Analyst
- Sales

---

# 🧠 Deep Learning Model

The predictive engine is an Artificial Neural Network.

Architecture:

```
TF-IDF
        │
        ▼
MLPClassifier
(128 Hidden Units)
        │
        ▼
64 Hidden Units
        │
        ▼
Softmax Output
(25 Categories)
```

The model predicts the probability that a resume belongs to the selected job category.

---

# 📊 Explainable AI

Instead of returning only a score, SCREEN explains every prediction using multiple interpretable components.

The final score combines:

- ANN Confidence
- Skill Overlap
- Resume ↔ Job Description Similarity
- Experience Score
- Education Score

Each contribution is displayed individually for complete transparency.

---

# 👨‍💼 Human-in-the-Loop

Recruiters remain in full control.

After AI screening, recruiters can:

- ✅ Approve Candidate
- ❌ Reject Candidate
- ✏️ Modify Decision
- 📝 Add Notes

This ensures AI recommendations are always reviewed by a human before final hiring decisions.

---

# 📄 Supported File Types

- PDF
- DOCX
- TXT

---

# 📥 Generated Reports

The application automatically generates a professional PDF report containing:

- Candidate Information
- Match Score
- Predicted Role
- Explainable AI Breakdown
- Recruiter Decision
- Final Recommendation

---

# 📁 Project Structure

```
resume-screener
│
├── app.py
├── requirements.txt
├── data/
├── modules/
│   ├── parser.py
│   ├── features.py
│   ├── model.py
│   ├── explain.py
│   ├── llm.py
│   ├── database.py
│   └── report.py
│
├── templates/
├── static/
├── sample_data/
└── instance/
```

---

# ⚙️ Installation

```bash
git clone https://github.com/samichohan/HR-Resume-Screener-Hackathon.git

cd HR-Resume-Screener-Hackathon

pip install -r requirements.txt

python app.py
```

Open

```
http://localhost:5000
```

---

# 🚀 Deployment

The application is deployed on Railway.

**Live URL**

https://hr-resume-screener-hackathon-production.up.railway.app/

---

# 🎯 Hackathon Requirements Covered

| Requirement | Status |
|------------|--------|
| Multimodal Data | ✅ |
| Deep Learning | ✅ |
| Explainable AI | ✅ |
| Human-in-the-Loop | ✅ |
| Working Web Application | ✅ |
| PDF Report Generation | ✅ |
| Business Use Case | ✅ |
| Production Deployment | ✅ |

---

# 👨‍💻 Developed By

**Abdul Sami Chohan**

AI & Data Science Developer

GitHub:
https://github.com/samichohan

---

# ⭐ If you found this project useful, don't forget to give it a Star.<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/cffb0c7a-02b0-4ebf-b467-0bded398e00a" />
