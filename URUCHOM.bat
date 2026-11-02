@echo off
cd /d "%~dp0"
title Pierscien COLMI R12 -^> TouchDesigner

echo.
echo ======================================================================
echo   PIERSCIEN COLMI R12  -^>  TOUCHDESIGNER
echo   Nie zamykaj tego okienka w trakcie pracy.
echo ======================================================================
echo.

rem Sam sie naprawia: jesli ktos nie uruchomil INSTALUJ.bat albo skasowal
rem folder venv, bootstrap zbuduje go tutaj i poleci dalej.
call scripts\srodowisko.bat
if errorlevel 1 goto koniec_blad

set PYTHONIOENCODING=utf-8
"%VPY%" src\start.py %*

echo.
echo ----------------------------------------------------------------------
echo   Koniec. Odebrane dane siedza w dane_z_pierscienia.csv w tym folderze.
echo ----------------------------------------------------------------------
pause
exit /b 0

:koniec_blad
pause
exit /b 1
