@echo off
cd /d "%~dp0"
title Pierscien COLMI R12 - odinstalowanie

echo.
echo ======================================================================
echo   ODINSTALOWANIE
echo ======================================================================
echo.
echo   Do skasowania:
echo     - folder venv (srodowisko Pythona tej paczki)
echo     - skroty z pulpitu
echo.
echo   NIE bedzie kasowane:
echo     - dane_z_pierscienia.csv ani zadne inne nagranie
echo     - ustawienia.txt
echo     - pliki TouchDesignera
echo.
echo   W systemie nic nie zostalo zainstalowane, wiec nic nie trzeba
echo   odkrecac. Caly folder paczki mozna potem po prostu usunac.
echo.
set /p ZGODA="Kasowac? [t/N] "
if /i not "%ZGODA%"=="t" goto anulowane

if exist "venv" rmdir /s /q venv
echo   venv skasowany.

powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\skroty.ps1" -Usun
echo.
echo   Gotowe.
echo.
pause
exit /b 0

:anulowane
echo.
echo   Anulowane, nic nie zmienione.
echo.
pause
exit /b 0
