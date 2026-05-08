@echo off
title Mobility Intelligence Backend
cd /d "c:\Users\IXS3KOR\OneDrive - Bosch Group\AI_Projects\mobility-intelligence\backend"
call "C:\Program Files\Anaconda3\Scripts\activate.bat" intel
uvicorn main:app --host 0.0.0.0 --port 8000 --reload --reload-dir api --reload-dir agents --reload-dir db --reload-dir models --reload-dir services
pause
