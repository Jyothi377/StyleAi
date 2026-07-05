# StyleAI

> An AI-powered fashion assistant that gives personalized outfit recommendations from user photos, wardrobe items, skin tone, gender, and occasion.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-Web_App-000000?style=for-the-badge&logo=flask&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![AI](https://img.shields.io/badge/AI-Fashion_Assistant-FF6F61?style=for-the-badge)

## Overview

**StyleAI** is a Flask-based fashion recommendation web app. It helps users analyze their photos, detect skin tone, manage wardrobe items, and receive AI-generated outfit suggestions for different occasions.

The app is designed for users who want quick, personalized styling guidance using their own images and saved clothing items.

## Features

- User registration, login, logout, and session management
- Photo upload for personalized style analysis
- Skin tone detection using image processing and AI-assisted analysis
- AI-generated outfit recommendations based on gender, occasion, and skin tone
- Wardrobe management for adding and deleting clothing items
- Wardrobe-based outfit suggestions
- Saved analysis history
- Favorite, view, delete, and clear history options
- Image search support for outfit item visuals

## Tech Stack

| Category | Technologies |
| --- | --- |
| Backend | Python, Flask |
| Authentication | Flask-Login |
| Database | Flask-SQLAlchemy, SQLite |
| Image Processing | Pillow, NumPy |
| AI / APIs | Groq, Gemini-compatible vision flow, Requests |
| Search | DDGS |
| Frontend | HTML, CSS, Jinja Templates |

## Project Structure

```text
StyleAI/
|-- app.py
|-- requirements.txt
|-- .env.example
|-- .gitignore
|-- templates/
|-- static/
`-- instance/
```

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/StyleAI.git
cd StyleAI
```

Replace `YOUR_USERNAME` with your GitHub username.

### 2. Create a virtual environment

```bash
python -m venv .venv
```

### 3. Activate the virtual environment

**Windows PowerShell**

```powershell
.venv\Scripts\Activate.ps1
```

If activation is blocked, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

**macOS / Linux**

```bash
source .venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure environment variables

Create a `.env` file or use a local `local_secrets.py` file for private keys.

Example:

```python
FLASK_SECRET_KEY = "your-secret-key"
GROQ_API_KEY = "your-groq-api-key"
GEMINI_API_KEY = "your-gemini-api-key"
REPLICATE_API_TOKEN = "your-replicate-token"
```

Do not commit real API keys to GitHub.

### 6. Run the application

```bash
python app.py
```

Open the app in your browser:

```text
http://127.0.0.1:5000
```

## Environment Variables

| Variable | Description |
| --- | --- |
| `FLASK_SECRET_KEY` | Secret key used by Flask sessions |
| `GROQ_API_KEY` | API key for AI-generated recommendations |
| `GEMINI_API_KEY` | API key used for image/vision analysis, if configured |
| `REPLICATE_API_TOKEN` | Optional token for Replicate-based features |

## Important Notes

- The SQLite database is created automatically when the app starts.
- Uploaded user images are stored in the `static/` folder.
- Local database files, API keys, logs, and virtual environments should not be uploaded.
- Use `.env.example` only for placeholder values.

## Files Not to Commit

Make sure these stay private or local:

```text
.venv/
__pycache__/
local_secrets.py
.env
instance/styleai.db
*.log
```

## Author

Jyothi Yelakanti

Developed as a fashion-focused AI web application using Flask and Python.
