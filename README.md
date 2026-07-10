# StyleAI

> An AI-powered fashion assistant that gives personalized outfit recommendations from user photos, wardrobe items, skin tone, gender, and occasion.

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-Web_App-000000?style=for-the-badge&logo=flask&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![AI](https://img.shields.io/badge/AI-Fashion_Assistant-FF6F61?style=for-the-badge)

## Problem Statement

Choosing outfits that suit your skin tone or a specific occasion is often guesswork without expert styling advice. Most people don't have quick access to personalized fashion feedback. StyleAI solves this by analyzing a user's photo and wardrobe to give instant, AI-driven outfit recommendations.

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
git clone https://github.com/Jyothi377/StyleAi.git
cd StyleAI
```

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

## Screenshots

*Register page*
<img width="1913" height="909" alt="Screenshot 2026-06-21 194737" src="https://github.com/user-attachments/assets/e45288a1-4b46-426b-8c8c-c3fb1b2c9b9d" />

*photo upload*
<img width="1913" height="914" alt="Screenshot 2026-06-21 194813" src="https://github.com/user-attachments/assets/b49ded4b-cddb-43f1-836c-8b1303fe8b23" />

*Result*
<img width="1895" height="912" alt="Screenshot 2026-06-21 195111" src="https://github.com/user-attachments/assets/c61f2cd5-7fdd-4ab8-ab35-9631552614bd" />

*History*
<img width="1893" height="916" alt="Screenshot 2026-06-21 195621" src="https://github.com/user-attachments/assets/6f7c05da-668d-4d5e-8d07-c66f9be45ca1" />

*Wardrobe upload*
<img width="1890" height="914" alt="Screenshot 2026-06-21 195732" src="https://github.com/user-attachments/assets/dafb1c85-369d-4490-8772-1521cef17ece" />

*Occasion-based outfit combo from wadrobe*
<img width="1897" height="913" alt="Screenshot 2026-06-21 195848" src="https://github.com/user-attachments/assets/40db4211-7f95-41c5-8a71-e827a4431a50" />



## Known Limitations

- Not yet deployed live — currently runs locally only
- Basic authentication only — no password reset, email verification, or social login
- Skin tone detection accuracy can vary depending on lighting and photo quality

## Future Improvements

- Deploy the app live (Render/Vercel/Railway) for public access
- Add password reset and email verification
- Improve skin tone detection accuracy across varied lighting conditions
- Add mobile-responsive UI

## What I Learned

Building StyleAI helped me practice integrating multiple AI APIs (Gemini, Groq) into a single Flask application, managing user authentication and sessions, structuring a database with Flask-SQLAlchemy, and handling real-world image processing challenges like inconsistent lighting affecting model accuracy.

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
