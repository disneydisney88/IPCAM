# Deployment Secrets

Passwords and API keys must never be committed to GitHub. GitHub is for source code, configuration examples, tests and documentation only.

## Current FastAPI dashboard

- The Admin password is created from `Settings → Authorized Public Scan`.
- The password is hashed locally and is not returned by the API.
- Camera usernames/passwords are stored through the local credential adapter; they are not placed in RTSP URLs returned to the browser.
- The local SQLite database and runtime files live outside the repository under `%LOCALAPPDATA%\IPCAM`.
- Do not copy the local database, `.env`, credential files or logs into GitHub.

## Local Streamlit development

If `streamlit_app.py` is added later, use environment variables or a local `.streamlit/secrets.toml` file. Both are ignored by `.gitignore`.

Example local file (never commit the real values):

```toml
SHODAN_API_KEY = "replace-me-locally"
IPCAM_ADMIN_PASSWORD = "replace-me-locally"
```

## Streamlit Cloud

Set the values in the app's Streamlit Cloud **Secrets** panel. Do not place them in `streamlit_app.py`, `README.md`, GitHub Actions logs, screenshots or public issue comments.

## GitHub Actions / deployment

Use repository or environment secrets for CI/CD. Reference them through environment variables, and ensure logs mask their values. Rotate any key immediately if it was ever committed or pasted into a public conversation.

## Shodan scope

The Shodan key may be configured locally, but Shodan requests must remain limited to the user's authorized allowlist. A key alone does not authorize searching unrelated public camera infrastructure.

## Current project status

`streamlit_app.py` is not currently present in this repository. The working application is the FastAPI + React dashboard started by `scripts/start-local.ps1`.
