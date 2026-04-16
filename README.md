# ============================================================
# Resume Analyzer API — README
# ============================================================

## Overview

Production-grade FastAPI backend for evaluating resumes using the **Grok (xAI) LLM**.

Upload a PDF resume → receive a strict, structured ATS-style evaluation JSON → optionally download a formatted PDF report.

---

## Architecture

```
resume-analyzer/
├── app/
│   ├── main.py                  # FastAPI app factory + middleware
│   ├── config.py                # Settings from .env
│   ├── models/
│   │   └── response_model.py    # Pydantic schemas
│   ├── routes/
│   │   └── analyze.py           # POST /analyze, POST /download-pdf
│   ├── services/
│   │   ├── parser.py            # PDF text extraction (PyMuPDF)
│   │   ├── splitter.py          # Section detection (skills/projects/experience/education)
│   │   ├── llm_service.py       # Grok API client
│   │   ├── scoring.py           # Rule-based penalty scoring
│   │   ├── analyzer.py          # Core orchestration pipeline
│   │   └── pdf_generator.py     # ReportLab PDF report generation
│   └── utils/
│       └── helpers.py           # Shared utility functions
├── requirements.txt
├── .env                         # Your secrets (not committed)
└── README.md
```

---

## Quick Start

### 1. Prerequisites

- Python 3.11+
- A valid [xAI Grok API key](https://console.x.ai/)

### 2. Install dependencies

```bash
cd resume-analyzer
pip install -r requirements.txt
```

### 3. Configure environment

Edit `.env` and set your Grok API key:

```env
GROK_API_KEY=xai-xxxxxxxxxxxxxxxxxxxxxxxx
GROK_MODEL=grok-3-mini
```

### 4. Run the server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Open API docs

Visit: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## API Endpoints

### `POST /api/v1/analyze`

Upload a PDF resume for analysis.

**Request:** `multipart/form-data` with field `file` (PDF)

**Response:** `ResumeAnalysisResponse` JSON

```json
{
  "status": "NOT_JOB_READY",
  "overall_score": 28,
  "section_scores": {
    "skills": 4,
    "projects": 2,
    "experience": 1,
    "impact": 1
  },
  "strengths": ["Exposure to Python fundamentals"],
  "weaknesses": ["No real-world projects with measurable outcomes"],
  "missing_elements": ["GitHub profile", "Deployed projects"],
  "job_roles": [],
  "domains": ["Web Development", "Backend Engineering"],
  "improvement_plan": [
    "Build and deploy at least 2 complete projects with live URLs.",
    "Contribute to open-source repositories."
  ],
  "final_verdict": "This resume will be rejected at the ATS stage..."
}
```

---

### `POST /api/v1/download-pdf`

Convert analysis JSON to a downloadable PDF report.

**Request:** `ResumeAnalysisResponse` JSON body

**Response:** `application/pdf` file stream

---

## Scoring Logic

| Condition                          | Penalty            |
|------------------------------------|--------------------|
| No projects section                | −4 from projects   |
| No experience/internship           | −4 from experience |
| Thin projects section (<100 chars) | −2 from projects   |
| No measurable results              | −3 from impact     |
| No skills section                  | −3 from skills     |
| Very thin skills (<50 chars)       | −2 from skills     |
| No education section               | −1 from experience |

**Overall Score** = weighted average × 10 (skills 25%, projects 30%, experience 30%, impact 15%)

**Status Rules:**
- `overall_score < 40` → `NOT_JOB_READY` + `job_roles = []`
- `overall_score >= 40` → `JOB_READY`

---

## Environment Variables

| Variable                 | Default                              | Description                          |
|--------------------------|--------------------------------------|--------------------------------------|
| `GROK_API_KEY`           | *(required)*                         | Your xAI Grok API key                |
| `GROK_API_URL`           | `https://api.x.ai/v1/chat/completions` | Grok API endpoint                  |
| `GROK_MODEL`             | `grok-3-mini`                        | Model to use                         |
| `MAX_FILE_SIZE_MB`       | `10`                                 | Max PDF upload size in MB            |
| `JOB_READY_THRESHOLD`    | `40`                                 | Min score for JOB_READY status       |
| `REQUEST_TIMEOUT_SECONDS`| `60`                                 | Grok API request timeout             |

---

## Tech Stack

| Component      | Library           |
|----------------|-------------------|
| Web Framework  | FastAPI + Uvicorn |
| PDF Parsing    | PyMuPDF (fitz)    |
| PDF Generation | ReportLab         |
| LLM API        | Grok (xAI) via requests |
| Validation     | Pydantic v2       |
| Config         | python-dotenv     |

---

## Health Check

```
GET /health  →  {"status": "healthy"}
GET /        →  {"service": "Resume Analyzer API", "version": "1.0.0", "status": "operational"}
```

---

## License

MIT
