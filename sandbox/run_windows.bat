@echo off
chcp 65001 >nul
echo.
echo ============================================
echo   ✈️  출장 데이터 조회 챗봇 시작
echo ============================================
echo.

:: ------------------------------------------------------------
:: 1. Python 확인
:: ------------------------------------------------------------
echo [1/3] Python 확인 중...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ❌ Python이 설치되어 있지 않습니다!
    echo.
    echo 아래 주소에서 Python을 설치해주세요:
    echo https://www.python.org/downloads/
    echo.
    echo 설치 시 "Add Python to PATH" 체크박스를 반드시 체크하세요!
    pause
    exit /b 1
)
echo    ✅ Python 확인 완료
echo.

:: ------------------------------------------------------------
:: 2. 가상환경 생성 및 패키지 설치
:: ------------------------------------------------------------
echo [2/3] 필요한 패키지 설치 중... (처음 한 번만 시간이 걸립니다)
if not exist ".venv" (
    python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -r requirements.txt -q
if %errorlevel% neq 0 (
    echo.
    echo ❌ 패키지 설치에 실패했습니다.
    pause
    exit /b 1
)
echo    ✅ 패키지 설치 완료
echo.

:: ------------------------------------------------------------
:: 3. GEMINI_API_KEY 확인
:: ------------------------------------------------------------
echo [3/3] Gemini API 키 확인 중...
if "%GEMINI_API_KEY%"=="" (
    echo.
    echo ❌ GEMINI_API_KEY가 설정되어 있지 않습니다!
    echo.
    echo 해결 방법:
    echo   1. https://aistudio.google.com/apikey 에서 API 키 발급
    echo   2. 이 파일(run_windows.bat)을 메모장으로 열어서
    echo      아래 줄을 찾아 본인의 키로 교체하세요:
    echo      set GEMINI_API_KEY=여기에_API_키_입력
    echo.
    pause
    exit /b 1
)
echo    ✅ API 키 확인 완료
echo.

:: ------------------------------------------------------------
:: 앱 실행
:: ------------------------------------------------------------
echo ============================================
echo   브라우저가 자동으로 열립니다.
echo   안 열리면: http://localhost:8501 접속
echo.
echo   종료하려면 이 창을 닫으세요.
echo ============================================
echo.
streamlit run app.py

pause
