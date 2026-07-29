@echo off
REM WinExtraFlow — publish the next feature post to the free channel (rotates)
cd /d C:\Users\v.serdyuk\Documents\AIGrowth\WinExtraFlow\backend
set PYTHONIOENCODING=utf-8
"C:\Users\v.serdyuk\AppData\Local\Programs\Python\Python313\python.exe" -X utf8 scripts\feature_posts.py next >> scripts\content.log 2>&1
