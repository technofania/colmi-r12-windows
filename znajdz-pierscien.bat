@echo off
cd /d "%~dp0"
title Szukam pierscieni w poblizu

echo.
echo ======================================================================
echo   SZUKANIE PIERSCIENI W POBLIZU
echo   Tylko nasluchuje. Nie wysyla do pierscienia ani jednej komendy.
echo ======================================================================
echo.

call scripts\srodowisko.bat
if errorlevel 1 goto koniec_blad

set PYTHONIOENCODING=utf-8
"%VPY%" src\skanuj.py %*
echo.
pause
exit /b 0

:koniec_blad
pause
exit /b 1
