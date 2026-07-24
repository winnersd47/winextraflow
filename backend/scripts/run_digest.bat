@echo off
REM WinExtraFlow — weekly performance digest -> VIP
cd /d C:\Users\v.serdyuk\Documents\AIGrowth\WinExtraFlow\backend
set PYTHONIOENCODING=utf-8
"C:\Users\v.serdyuk\AppData\Local\Programs\Python\Python313\python.exe" -X utf8 scripts\weekly_digest.py >> scripts\content.log 2>&1
