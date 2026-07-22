@echo off
REM WinExtraFlow — one-shot signal backfill + VIP broadcast (for Task Scheduler)
cd /d C:\Users\v.serdyuk\Documents\AIGrowth\WinExtraFlow\backend
set PYTHONIOENCODING=utf-8
"C:\Users\v.serdyuk\AppData\Local\Programs\Python\Python313\python.exe" -X utf8 scripts\tg_backfill.py 30 --vip >> scripts\poller.log 2>&1
