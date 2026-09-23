# DevOps Operational Intelligence Dashboard

A configurable dashboard to monitor multiple AWS accounts and resources
(EC2, ECS, ECR, EKS, S3, CloudWatch). Runs with synthetic **mock** data out of
the box, and switches to **live** AWS data when you attach read-only credentials.

There are two ways to use it:

1. **Ship a single self-contained `.exe`** — the end user just double-clicks it.
   No Python, no Node, no installs required on their machine. *(Recommended for delivery.)*
2. **Run from source** — for development.

---

## Option 1 — Self-contained Windows EXE (no prerequisites for the end user)

### Build it (once, on a machine that has Python 3.10+ and Node.js)
From the project root:
```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```
This builds the frontend, bundles it with the backend, and produces:
```
dist\DevOpsDashboard.exe
```
Everything (the Python runtime, all dependencies, and the web UI) is packed
**inside that one file**.

### Run it (on any Windows machine — nothing to install)
1. Copy `DevOpsDashboard.exe` to a normal folder (e.g. `C:\Users\<you>\DevOpsDashboard\`).
2. Double-click it. A console window opens and your browser launches at
   `http://127.0.0.1:8000`.
3. All configuration and data are stored in a per-user directory:
   a `.devops` folder in your home directory (same convention as `.aws` / `.m2`),
   e.g. `C:\Users\<you>\.devops\devops_dashboard.db`.
   This works even if the exe is run from a read-only location like `Program Files`.
4. To stop it, close the console window (or press `Ctrl+C`).

> Optional environment variables (set before launching):
> `DASHBOARD_PORT` / `DASHBOARD_HOST` change the port/host;
> `DASHBOARD_DATA_DIR` changes where data and config are stored.

### Set it up for your instance and credentials
The exe stores **no** credentials. Configure them at runtime in the UI:

- **Mock mode** — works immediately with synthetic data (no AWS needed).
- **Live AWS** — in the **AWS Accounts** tab add an account with:
  - mode `profile` + a named AWS profile (e.g. `prod-readonly`), **or**
  - mode `env` to use the default AWS credential chain / IAM role.

  Then in **Monitored Resources** add your real resource identifiers:
  | Type | Identifier format |
  |------|-------------------|
  | EC2 | instance id, e.g. `i-0abc123...` |
  | ECS | `cluster/service` |
  | ECR | repository name |
  | EKS | cluster name |
  | S3  | bucket name |
  | CloudWatch | alarm name |

To use `profile`/`env` mode, the machine running the exe needs a local AWS
credential configuration (e.g. run `aws configure --profile prod-readonly`, or
set `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` env vars, or an attached IAM role).
Grant **least-privilege read-only** IAM only:
`ec2:Describe*`, `ecs:Describe*`, `ecr:Describe*`, `eks:Describe*`,
`s3:GetBucket*`, `cloudwatch:Describe*` / `GetMetric*`.

---

## Option 2 — Run from source (development)

### Prerequisites
- Python 3.10+ and Node.js 18+

### Backend
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
On first start it seeds a `Demo (mock)` account with sample resources.
API docs: http://localhost:8000/docs

### Frontend
```powershell
cd frontend
npm install
npm run dev
```
Open http://localhost:5173 (Vite proxies `/api` to the backend on port 8000).

---

## Build, run, and rebuild the EXE (developer steps)

Use these steps whenever you change the code and want a fresh, updated
`DevOpsDashboard.exe` to distribute.

### One-time prerequisites (build machine only)
- **Python 3.10+** (from python.org — not the Microsoft Store stub)
- **Node.js 18+**

### Step 1 — Get the dependencies
```powershell
# Backend deps (creates the virtual environment)
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-build.txt   # adds PyInstaller
deactivate
cd ..

# Frontend deps
cd frontend
npm install
cd ..
```

### Step 2 — (Optional) Test from source before packaging
```powershell
# Terminal 1 — backend API
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend dev server
cd frontend
npm run dev
```
Open http://localhost:5173 and verify your changes.

### Step 3 — Build / rebuild the updated EXE
From the **project root**, run the build script. It rebuilds the frontend,
re-bundles it with the backend, and regenerates the executable:
```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```
Output:
```
dist\DevOpsDashboard.exe   (updated, self-contained)
```
> The script cleans previous build artifacts (`--clean`), so every run produces
> a fresh EXE reflecting your latest code. No manual cleanup needed.

### Step 4 — Run / verify the new EXE
```powershell
.\dist\DevOpsDashboard.exe
```
A console window opens and your browser launches at `http://127.0.0.1:8000`.
To run on a different port without conflicts:
```powershell
$env:DASHBOARD_PORT = "8765"; .\dist\DevOpsDashboard.exe
```

### Step 5 — Distribute
Ship the single `dist\DevOpsDashboard.exe`. The target machine needs **nothing**
installed. Its data lives in `C:\Users\<user>\.devops\`.

> **Clean rebuild tip:** if a build ever behaves oddly, delete
> `backend\build`, `backend\dist`, and `backend\frontend_dist`, then re-run
> `build_exe.ps1`.

---

## Stack
- **Backend:** FastAPI + SQLAlchemy + SQLite, boto3 for AWS
- **Frontend:** React (Vite)
- **Packaging:** PyInstaller (single-file EXE)

## Architecture
```
DevOpsDashboard.exe / uvicorn
   └── FastAPI (app.main)
         ├── /api/accounts    manage AWS account connections
         ├── /api/resources   CRUD monitored resources
         ├── /api/monitor      normalized live/mock status
         │     └── collector_service
         │           ├── aws/mock.py        (mode=mock)
         │           └── aws/collectors.py  (mode=profile/env, boto3)
         └── /                 serves the bundled React UI (frontend_dist)
```
Every resource is normalized to `{status, summary, metrics, details, source}`
so the UI treats mock and live data identically.

## Going live with real AWS
The app never stores AWS secret keys — it only references a profile or the
default credential chain. Grant least-privilege read-only IAM (e.g.
`ec2:Describe*`, `ecs:Describe*`, `ecr:Describe*`, `eks:Describe*`,
`s3:GetBucket*`, `cloudwatch:Describe*`/`GetMetric*`).
