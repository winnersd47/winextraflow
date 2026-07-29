@echo off
REM WinExtraFlow — weekly free-channel content (quality-gate report + top by WEF)
cd /d C:\Users\v.serdyuk\Documents\AIGrowth\WinExtraFlow\backend
set PYTHONIOENCODING=utf-8
"C:\Users\v.serdyuk\AppData\Local\Programs\Python\Python313\python.exe" -X utf8 scripts\free_channel_weekly.py >> scripts\content.log 2>&1
