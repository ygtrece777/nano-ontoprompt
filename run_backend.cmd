@echo off
set PYTHONPATH=D:\本体\nano-ontoprompt\backend\.venv\Lib\site-packages
cd /d D:\本体\nano-ontoprompt\backend
"C:\Users\26451\AppData\Local\Programs\Python\Python311\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --lifespan off
