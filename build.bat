@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "APP_NAME=PeckTeX"
set "ENTRY_FILE=main.py"
set "ICON_FILE=assets\icons\app_64.ico"
set "ADD_DATA_SPEC=assets\icons;assets\icons"
set "DEBUG_BUILD=1"

:parse_args
if "%~1"=="" goto :args_done
if /i "%~1"=="--release" set "DEBUG_BUILD=0"
if /i "%~1"=="--debug" set "DEBUG_BUILD=1"
shift
goto :parse_args

:args_done

if "%APP_NAME%"=="" (
    echo [ERROR] APP_NAME is empty.
    echo         Set APP_NAME before running this script.
    goto :fail
)

if "%ADD_DATA_SPEC%"=="" (
    echo [ERROR] ADD_DATA_SPEC is empty.
    echo         Example: assets\icons;assets\icons
    goto :fail
)

if not "%DEBUG_BUILD%"=="0" if not "%DEBUG_BUILD%"=="1" (
    echo [ERROR] Invalid DEBUG_BUILD value: %DEBUG_BUILD%
    echo         Allowed values: 0 ^| 1
    goto :fail
)

set "DIST_DIR=dist\%APP_NAME%"
set "WINDOWED_FLAG="
if "%DEBUG_BUILD%"=="0" set "WINDOWED_FLAG=--windowed"

echo ==========================================
echo    %APP_NAME% Build Script (PyInstaller)
echo ==========================================

if "%DEBUG_BUILD%"=="1" (
    echo Mode: DEBUG ^(console visible^)
) else (
    echo Mode: RELEASE ^(console hidden^)
)
echo Add data: %ADD_DATA_SPEC%

if not exist "%ENTRY_FILE%" (
    echo [ERROR] Entry file not found: %ENTRY_FILE%
    goto :fail
)

if not exist "%ICON_FILE%" (
    echo [ERROR] Icon file not found: %ICON_FILE%
    goto :fail
)

where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python was not found in PATH.
    echo         Activate your environment first, then rerun this script.
    goto :fail
)

python -m PyInstaller --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] PyInstaller is not available in current Python environment.
    echo         Install it with: pip install pyinstaller
    goto :fail
)

python -c "import PySide6, openai, httpx" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Required runtime packages are missing in current environment.
    echo         Install dependencies with: pip install -r requirements.txt
    goto :fail
)

echo Cleaning previous build output...
for %%D in ("build" "%DIST_DIR%" "%APP_NAME%.spec") do (
    if exist "%%~D" (
        if exist "%%~D\" ( rd /s /q "%%~D" ) else ( del /q "%%~D" )
    )
)

echo Building %APP_NAME%...
python -m PyInstaller ^
    --clean ^
    --noconfirm ^
    --onedir ^
    %WINDOWED_FLAG% ^
    --icon "%ICON_FILE%" ^
    --add-data "%ADD_DATA_SPEC%" ^
    --exclude-module "PySide6.QtWebEngineCore" ^
    --exclude-module "PySide6.QtWebEngineWidgets" ^
    --exclude-module "PySide6.QtWebEngineQuick" ^
    --exclude-module "PySide6.QtWebChannel" ^
    --exclude-module "PySide6.QtQml" ^
    --exclude-module "PySide6.QtQuick" ^
    --exclude-module "PySide6.QtQuick3D" ^
    --exclude-module "PySide6.QtQuickControls2" ^
    --exclude-module "PySide6.QtQuickWidgets" ^
    --exclude-module "PySide6.Qt3DCore" ^
    --exclude-module "PySide6.Qt3DRender" ^
    --exclude-module "PySide6.Qt3DInput" ^
    --exclude-module "PySide6.Qt3DAnimation" ^
    --exclude-module "PySide6.Qt3DExtras" ^
    --name "%APP_NAME%" ^
    "%ENTRY_FILE%"

if %ERRORLEVEL% neq 0 (
    echo [ERROR] Build failed. Check logs above.
    goto :fail
)

if not exist "%DIST_DIR%\%APP_NAME%.exe" (
    echo [ERROR] Build finished but expected executable was not found.
    echo         Expected: %DIST_DIR%\%APP_NAME%.exe
    goto :fail
)

echo ==========================================
echo Build succeeded.
echo Output folder: %~dp0%DIST_DIR%
echo Executable  : %~dp0%DIST_DIR%\%APP_NAME%.exe
echo ==========================================

goto :end

:fail
pause
endlocal
exit /b 1

:end
pause
endlocal
exit /b 0
