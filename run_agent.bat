@echo off

cd /d "C:\Users\NANO TECHNOLOGY\OneDrive\Desktop\opportunity-ai"

chcp 65001 >nul

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

call ".venv\Scripts\activate.bat"

python helai_agent.py
