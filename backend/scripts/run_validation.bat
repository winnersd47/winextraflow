@echo off
REM WinExtraFlow — is the WEF Score actually predicting outcomes, and is the MT5
REM model's self-assessment calibrated? Prints "недостаточно данных" until the
REM sample supports a conclusion, which is the point: the score must not be
REM described as validated before it is.
cd /d C:\Users\v.serdyuk\Documents\AIGrowth\WinExtraFlow\backend
set PYTHONIOENCODING=utf-8
"C:\Users\v.serdyuk\AppData\Local\Programs\Python\Python313\python.exe" -X utf8 scripts\wef_validation.py >> scripts\validation.log 2>&1
