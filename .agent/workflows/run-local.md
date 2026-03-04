---
description: Run the MedTrack application locally for development and testing
---

## Prerequisites
- Python 3.9+ installed
- Virtual environment created (optional but recommended)
- `.env` file present with AWS credentials OR local storage fallback available

## Steps

// turbo
1. Navigate to the project directory
```bash
cd c:\Users\every\.gemini\antigravity\playground\holographic-ring\medtrack
```

2. (Optional) Create and activate a virtual environment
```bash
python -m venv venv
.\venv\Scripts\activate
```

// turbo
3. Install dependencies
```bash
pip install -r requirements-lite.txt
```

// turbo
4. Start the local development server
```bash
python app.py
```

## Expected Output
```
 * Running on http://127.0.0.1:5000
 * Debug mode: on
 * Restarting with stat
```

## Access the App
Open your browser and go to: http://127.0.0.1:5000

## Notes
- If AWS credentials are not set, the app falls back to `local_storage.py` (JSON files in `local_data/`)
- Templates served from `templates/` directory
- Static files from `static/` directory
- Uploaded files saved in `uploads/` directory
