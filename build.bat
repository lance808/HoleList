@echo off
chcp 65001 >nul
echo ========================================
echo   挖坑备忘录 - 打包工具
echo ========================================
echo.

REM 检查 pyinstaller
pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] 安装 pyinstaller...
    pip install pyinstaller
)

echo [*] 开始打包...

pyinstaller --onefile --windowed --noconfirm --clean --name "挖坑备忘录" ^
    --add-data "data_manager.py;." ^
    --add-data "hole_page.py;." ^
    --add-data "memo_page.py;." ^
    --add-data "settings_dialog.py;." ^
    main.py

echo.
echo ========================================
echo   打包完成!
echo   exe 位置: dist\挖坑备忘录.exe
echo ========================================
pause