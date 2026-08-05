@echo off
REM ── Static export for Cloudflare Pages ────────────────────────────────────
REM Usage:
REM   build-pages.bat                          -> no backend (landing + legal pages)
REM   build-pages.bat https://api.example.ru   -> full app pointed at that backend
REM
REM Dynamic routes (/dashboard/signals/[id], /dashboard/marketplace/[id]) cannot
REM be statically exported, so they are moved aside during the build and restored
REM afterwards.

setlocal
cd /d %~dp0

if not "%~1"=="" (
    echo NEXT_PUBLIC_API_URL=%~1> .env.production.local
    echo API target: %~1
) else (
    if exist .env.production.local del .env.production.local
    echo API target: none ^(landing + legal pages only^)
)

echo.
echo [1/4] switching to static-export config
if exist next.config.js copy /Y next.config.js next.config.js.standalone.bak >nul
copy /Y next.config.pages.js next.config.js >nul

echo [2/4] moving dynamic routes aside
if exist "src\app\dashboard\signals\[id]" move "src\app\dashboard\signals\[id]" "src\app\dashboard\signals\_id_bak" >nul
if exist "src\app\dashboard\marketplace\[id]" move "src\app\dashboard\marketplace\[id]" "src\app\dashboard\marketplace\_id_bak" >nul

echo [3/4] building
set NODE_OPTIONS=--max-old-space-size=4096
call npx next build

echo [4/4] restoring project state
if exist "src\app\dashboard\signals\_id_bak" move "src\app\dashboard\signals\_id_bak" "src\app\dashboard\signals\[id]" >nul
if exist "src\app\dashboard\marketplace\_id_bak" move "src\app\dashboard\marketplace\_id_bak" "src\app\dashboard\marketplace\[id]" >nul
if exist next.config.js.standalone.bak copy /Y next.config.js.standalone.bak next.config.js >nul

echo.
echo Done. Upload the "out" folder to Cloudflare Pages.
endlocal
