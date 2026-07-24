@echo off
REM WinExtraFlow — hourly TP/SL monitor (closes signals + notifies VIP)
cd /d C:\Users\v.serdyuk\Documents\AIGrowth\WinExtraFlow\backend
set PYTHONIOENCODING=utf-8
"C:\Users\v.serdyuk\AppData\Local\Programs\Python\Python313\python.exe" -X utf8 scripts\monitor_signals.py >> scripts\monitor.log 2>&1
