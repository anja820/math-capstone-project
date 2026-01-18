# InsightPro - Math Capstone Project

InsightPro is an Instagram profile analysis tool that uses mathematical models (discrete probability and graph theory) to assess profile authenticity and provide content insights.

## Project Structure

```
math-capstone-project/
├── backend/          # FastAPI backend server (Python)
│   ├── app.py       # Main FastAPI application
│   ├── README.md    # Backend setup and running instructions
│   └── ...
└── frontend/         # Streamlit frontend (Python)
    ├── Home.py      # Main Streamlit application
    └── ...
```

## Quick Start

### 1. Backend Setup

The backend must be running before starting the frontend.

See detailed instructions in [backend/README.md](backend/README.md)

Quick start:
```bash
cd backend
pip install -r requirements.txt
playwright install chromium
uvicorn app:app --host 127.0.0.1 --port 8001 --reload
```

The backend will be available at http://127.0.0.1:8001

### 2. Frontend Setup

```bash
cd frontend
pip install -r requirements.txt
streamlit run Home.py
```

The frontend will open in your browser (typically at http://localhost:8501)

## Features

### Mathematical Models
- **Discrete Probability**: Authenticity estimation using Bayesian inference
- **Graph Theory**: Hashtag co-occurrence network analysis
- **Content Classification**: Topic breakdown using keyword matching

### API Endpoints
- User authentication (signup/login)
- Manual profile analysis
- Instagram profile scraping (basic info, detailed audit, follower analysis)

## Requirements

- Python 3.8 or higher
- pip (Python package installer)

## Documentation

- [Backend Setup Guide](backend/README.md) - Detailed instructions for running the FastAPI backend

## License

This is a capstone project for educational purposes.
