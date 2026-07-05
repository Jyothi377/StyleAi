# StyleAI


StyleAI is a Flask-based fashion assistant that helps users get personalized outfit guidance from their own photos and wardrobe. It supports account login and registration, image-based skin tone analysis, AI-generated style recommendations, wardrobe item management, and saved history so users can revisit earlier analyses and suggestions.

## Tech Stack

- Python
- Flask
- Flask-Login
- Flask-SQLAlchemy
- Pillow
- NumPy
- Groq
- Requests
- DDGS

## Project Structure

- `app.py` - main Flask application
- `templates/` - HTML templates
- `static/` - static assets and uploaded images
- `instance/` - local SQLite database storage
- `requirements.txt` - Python dependencies
- `.env.example` - example environment variables
- `.gitignore` - files and folders excluded from Git

## Local Setup

1. Create a virtual environment:

```powershell
python -m venv .venv
```

2. Activate the virtual environment:

```powershell
.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run this first:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

3. Install dependencies:

```powershell
pip install -r requirements.txt
```

4. Add your API keys.

You can use environment variables, or create a local `local_secrets.py` file. Do not upload `local_secrets.py` to GitHub.

Example:

```python
FLASK_SECRET_KEY = "your-secret-key"
GROQ_API_KEY = "your-groq-api-key"
GEMINI_API_KEY = "your-gemini-api-key"
REPLICATE_API_TOKEN = "your-replicate-token"
```

5. Run the app:

```powershell
python app.py
```

6. Open the app in your browser:

```text
http://127.0.0.1:5000
```

## Before Uploading to GitHub

Make sure these files are not committed:

- `.venv/`
- `__pycache__/`
- `local_secrets.py`
- `.env`
- `instance/styleai.db`

These are already listed in `.gitignore`. The `.env.example` file is safe to upload because it contains placeholder values only.

## GitHub Upload Steps

Run these commands from the `StyleAI` folder:

```powershell
cd C:\Users\Pc\OneDrive\Desktop\Projects\StyleAI
git init
git status
git add .
git commit -m "Initial commit"
```

Create a new empty repository on GitHub, then connect it:

```powershell
git remote add origin https://github.com/YOUR_USERNAME/StyleAI.git
git branch -M main
git push -u origin main
```

Replace `YOUR_USERNAME` with your GitHub username.

## Notes

- The SQLite database is created automatically when the app starts.
- Uploaded images are stored in the `static/` folder.
- Keep real API keys private. Use `.env`, environment variables, or `local_secrets.py` for local development.
