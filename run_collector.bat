@echo off

cd /d "C:\Users\NANO TECHNOLOGY\OneDrive\Desktop\opportunity-ai"

chcp 65001 >nul

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

call ".venv\Scripts\activate.bat"


echo. >> collector.log
echo ======================================== >> collector.log
echo HELAI ONE-CYCLE AUTOMATION START >> collector.log
echo ======================================== >> collector.log

python helai_run_once.py >> collector.log 2>&1

if errorlevel 1 (
    echo HelAI automation failed. Check the log above. >> collector.log
    exit /b 1
)

echo. >> collector.log
echo ======================================== >> collector.log
echo HELAI AUTOMATION COMPLETED SUCCESSFULLY >> collector.log
echo ======================================== >> collector.log

exit /b 0
