# Development

## Backend

```powershell
cd backend
& "$env:USERPROFILE\.ipcam\venv\Scripts\python.exe" -m uvicorn app.main:app --reload --port 8000
```

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

Vite listens only on `127.0.0.1:8080` and proxies `/api` to `127.0.0.1:8000`.

## Quality gate

Run `scripts\test-system.ps1`. A milestone is not complete until pytest passes, TypeScript/Vite build succeeds, the backend health endpoint responds, and the dashboard HTML opens locally.

Do not commit `.venv`, `node_modules`, runtime SQLite/WAL files, logs, snapshots, credential files or downloaded executable binaries.
