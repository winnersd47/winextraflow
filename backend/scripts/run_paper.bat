@echo off
REM WinExtraFlow — paper accounts: open new signals, settle what the monitor closed.
REM Runs at :25, right after WEF_SignalMonitor (:17), so a signal closed this hour
REM becomes a recorded trade with money attached in the same hour.
cd /d C:\Users\v.serdyuk\Documents\AIGrowth\WinExtraFlow\backend
set PYTHONIOENCODING=utf-8
"C:\Users\v.serdyuk\AppData\Local\Programs\Python\Python313\python.exe" -X utf8 scripts\paper_sync.py >> scripts\paper.log 2>&1
