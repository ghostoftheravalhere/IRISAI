@echo off
REM setup.bat — Bootstrap the full dev environment on Windows
echo =^> Setting up IRIS AI backend...
cd backend
python -m venv .venv
call .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
if not exist "..\\.env" copy "..\\.env.example" "..\\.env"
echo Backend ready.

echo =^> Setting up IRIS AI frontend...
cd ..\frontend
npm install
echo Frontend ready.

echo.
echo Setup complete.
echo   Start backend : cd backend ^&^& python main.py
echo   Start frontend: cd frontend ^&^& npm run dev
