# StyleAI

StyleAI is a Flask-based fashion and style recommendation app. It supports user login, wardrobe management, image-based skin tone analysis, and outfit suggestions.

## Tech Stack

- Python
- Flask
- Flask-Login
- Flask-SQLAlchemy
- Pillow
- NumPy
- Requests

## Project Structure

- `app.py` - main Flask application
- `templates/` - HTML templates
- `static/` - static assets and uploaded files
- `instance/` - local SQLite database storage
- `requirements.txt` - Python dependencies

## Local Setup

1. Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Run the app:

```powershell
python app.py
```

4. Open the local address shown in the terminal, usually:

```text
http://127.0.0.1:5000
```

## Before Uploading to GitHub

Follow these steps before pushing the project to GitHub:

1. Remove secret keys from source files and move them to environment variables.
2. Update `app.py` so API keys are read from the environment instead of being hardcoded.
3. Make sure `.venv/`, `__pycache__/`, and local database files are not committed.
4. Do not upload `instance/styleai.db` unless you intentionally want to share sample data.
5. Check that sensitive files are listed in `.gitignore`.
6. Run the app once more to confirm it starts correctly after your changes.
7. Review the repository for any accidental secrets before committing.

## GitHub Upload Steps

1. Initialize git if needed:

```powershell
git init
```

2. Check the status:

```powershell
git status
```

3. Add files:

```powershell
git add .
```

4. Commit your changes:

```powershell
git commit -m "Initial commit"
```

5. Create a new repository on GitHub.
6. Add the remote repository URL.
7. Push the code:

```powershell
git push -u origin main
```

## Notes

- The SQLite database is created automatically when the app starts.
- If you change the database schema, test the app locally before pushing.
- If you plan to deploy the project later, use environment variables for all API keys.