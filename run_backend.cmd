@echo off
set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%backend"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --lifespan off
) else (
  py -3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --lifespan off
)
