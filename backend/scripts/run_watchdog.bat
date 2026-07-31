@echo off
REM WinExtraFlow — daily operations watchdog (report to admin if configured)
cd /d C:\Users\v.serdyuk\Documents\AIGrowth\WinExtraFlow\backend
set PYTHONIOENCODING=utf-8
"C:\Users\v.serdyuk\AppData\Local\Programs\Python\Python313\python.exe" -X utf8 scripts\watchdog.py >> scripts\watchdog.log 2>&1
