@echo off

cd /d "C:\Users\NANO TECHNOLOGY\OneDrive\Desktop\opportunity-ai"

chcp 65001 >nul

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

call ".venv\Scripts\activate.bat"


echo. >> collector.log
echo ======================================== >> collector.log
echo HELAI OPPORTUNITY DESK COLLECTION START >> collector.log
echo ======================================== >> collector.log

python automatic_collector.py >> collector.log 2>&1

if errorlevel 1 (
    echo Opportunity Desk collector failed. Automation stopped. >> collector.log
    exit /b 1
)


echo. >> collector.log
echo ======================================== >> collector.log
echo HELAI UKRI COLLECTION START >> collector.log
echo ======================================== >> collector.log

python ukri_automatic_collector.py >> collector.log 2>&1

if errorlevel 1 (
    echo UKRI collector failed. Automation stopped. >> collector.log
    exit /b 1
)


echo. >> collector.log
echo ======================================== >> collector.log
echo HELAI KURDISH TRANSLATION START >> collector.log
echo ======================================== >> collector.log

python translation_service.py >> collector.log 2>&1

if errorlevel 1 (
    echo Translation failed. Automation stopped. >> collector.log
    exit /b 1
)


echo. >> collector.log
echo ======================================== >> collector.log
echo HELAI AUTOMATIC MATCHING START >> collector.log
echo ======================================== >> collector.log

python matching_service.py >> collector.log 2>&1

if errorlevel 1 (
    echo Matching failed. Automation stopped. >> collector.log
    exit /b 1
)


echo. >> collector.log
echo ======================================== >> collector.log
echo HELAI NOTIFICATION QUEUE START >> collector.log
echo ======================================== >> collector.log

python notification_service.py >> collector.log 2>&1

if errorlevel 1 (
    echo Notification queue failed. Automation stopped. >> collector.log
    exit /b 1
)


echo. >> collector.log
echo ======================================== >> collector.log
echo HELAI EMAIL DELIVERY START >> collector.log
echo ======================================== >> collector.log

python email_service.py >> collector.log 2>&1

if errorlevel 1 (
    echo Email delivery failed. Automation stopped. >> collector.log
    exit /b 1
)


echo. >> collector.log
echo ======================================== >> collector.log
echo HELAI AUTOMATION COMPLETED SUCCESSFULLY >> collector.log
echo ======================================== >> collector.log

exit /b 0