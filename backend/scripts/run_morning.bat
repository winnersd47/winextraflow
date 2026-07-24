@echo off
REM WinExtraFlow — daily morning market overview -> VIP
cd /d C:\Users\v.serdyuk\Documents\AIGrowth\WinExtraFlow\backend
set PYTHONIOENCODING=utf-8
"C:\Users\v.serdyuk\AppData\Local\Programs\Python\Python313\python.exe" -X utf8 scripts\morning_overview.py >> scripts\content.log 2>&1
