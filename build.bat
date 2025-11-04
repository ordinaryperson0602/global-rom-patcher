@echo off
chcp 65001 >nul
echo ================================
echo 롬파일 패치 도구 빌드 스크립트
echo ================================
echo.

echo [1/3] 이전 빌드 파일 정리 중...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
echo ✓ 정리 완료
echo.

echo [2/3] PyInstaller로 exe 파일 생성 중...
pyinstaller build.spec
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ 빌드 실패!
    pause
    exit /b 1
)
echo ✓ 빌드 완료
echo.

echo [3/3] 최종 확인...
if exist "dist\롬파일패치도구.exe" (
    echo.
    echo ================================
    echo ✓ 빌드 성공!
    echo ================================
    echo.
    echo 생성된 파일: dist\롬파일패치도구.exe
    echo 파일 크기: 
    dir "dist\롬파일패치도구.exe" | findstr "롬파일패치도구.exe"
    echo.
) else (
    echo ❌ exe 파일이 생성되지 않았습니다.
)

echo.
pause

