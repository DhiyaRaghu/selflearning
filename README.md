# Career Coach AI

Career Coach AI is a responsive web app with a Python standard-library backend and SQLite storage. It can run locally without installing packages. `render.yaml` describes a Render web service with a persistent disk for the database.

## Run locally

1. Install Python 3.11 or newer.
2. In this folder, run `python server.py`.
3. Open `http://127.0.0.1:8000`.
4. Create an account or choose **Continue as guest**.

Local accounts use an HttpOnly session cookie and PBKDF2 password hashes. Signed-in profiles, practice progress, confirmed skills, and saved sample roles are stored in SQLite. The database path can be changed with `CAREER_DB_PATH`.

## Deploy on Render

1. Push this project to a GitHub repository.
2. In Render, create a new Blueprint and select that repository. Render reads `render.yaml` and provisions the web service and persistent disk.
3. Wait for the deploy to finish, then open the generated `*.onrender.com` address and register an account.
4. Keep the persistent disk mounted at `/var/data`; it holds the SQLite database across deploys.

The included Render disk requires a paid Render web service plan. For a public, multi-instance product, replace SQLite with managed PostgreSQL and add database backups, rate limits, account recovery, and monitoring before inviting a broad audience.

## What works now

- Account registration, sign-in, sign-out, and persistent profiles
- Aptitude practice, saved practice progress, and browser-local interview sessions
- Saved sample jobs and confirmed learner skills
- Text resume skill extraction (TXT only)
- Profile and progress persistence to SQLite for signed-in users
- Guest mode for trying the interface without an account

## Still needs provider integrations

- AI-generated question variants and evaluated coaching: connect a model provider on the server and store its API key as a private environment variable. Do not put provider keys in `app.js`.
- Current job listings: connect a licensed job feed or employer source; visible jobs are examples.
- PDF/DOCX resume extraction: add a parser, consent copy, and retention/deletion controls. The current endpoint accepts plain text only.
- Live group discussions: add a WebRTC room provider, participant identity, moderation, and consent flows. Current rooms are previews.
- Coding execution: connect an isolated code-runner service. The current editor does not execute submitted code.
- Production account recovery, email verification, anti-abuse controls, and privacy/retention policy.

Do not upload confidential resumes until the production storage, access controls, retention, and deletion flow are implemented.

