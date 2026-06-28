@echo off
chcp 65001 >nul
echo ========================================
echo   HoleList - 启动器编译
echo ========================================
echo.

REM 查找 csc.exe
set CSC=
for %%f in (
    "C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"
    "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
) do if exist %%f set CSC=%%f

if "%CSC%"=="" (
    echo [错误] 未找到 .NET Framework 编译器 csc.exe
    echo 请安装 .NET Framework 4.0+
    pause
    exit /b 1
)

echo [*] 编译器: %CSC%
echo [*] 正在编译 launcher.cs ...
%CSC% /target:winexe /out:HoleList.exe launcher.cs

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo   编译完成! 启动器: HoleList.exe
    echo   将该 exe 放到 main.py 同目录下双击即可
    echo ========================================
) else (
    echo [错误] 编译失败
)
pause