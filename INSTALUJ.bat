@echo off
cd /d "%~dp0"
title Pierscien COLMI R12 - instalacja

echo.
echo ======================================================================
echo   PIERSCIEN COLMI R12  -^>  TOUCHDESIGNER
echo   Instalacja. Nic nie laduje w systemie - wszystko zostaje tutaj.
echo ======================================================================
echo.

echo [1/3] Srodowisko Pythona i biblioteki
call scripts\srodowisko.bat
if errorlevel 1 goto koniec_blad

echo [2/3] Sprawdzam biblioteki
rem Wersji NIE czytamy z bleak.__version__ - bleak 3.x tego atrybutu nie ma
rem i taki test wywalal instalator na poprawnie zainstalowanej bibliotece.
"%VPY%" -c "import bleak, pythonosc, importlib.metadata as m; print('    bleak', m.version('bleak'), '+ python-osc', m.version('python-osc'), 'OK')"
if errorlevel 1 goto blad_bleak

echo [3/3] Skroty na pulpicie
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\skroty.ps1" -Korzen "%CD%"
if errorlevel 1 echo    (skrotow nie udalo sie zrobic - to nie blokuje niczego)

echo.
echo ======================================================================
echo   GOTOWE.
echo ======================================================================
echo.
echo   Co dalej:
echo.
echo     1. Zaloz pierscien na palec, czujnikiem do skory, docisniety.
echo     2. Zamknij aplikacje QRing w telefonie, jesli jest wlaczona.
echo        Pierscien przyjmuje tylko JEDNO polaczenie naraz.
echo     3. Otworz td\RING_START.toe - gotowy projekt TouchDesignera.
echo     4. Kliknij URUCHOM.bat
echo.
rem UWAGA: zadnych strzalek "->" w echo. Nieuciekniony znak wieksze to dla
rem cmd przekierowanie, nie strzalka - taka linia nadpisuje plik o nazwie
rem stojacej po niej. Raz skasowala w tym repo znajdz-pierscien.bat.
echo   Pierscienia nie widac:  uruchom znajdz-pierscien.bat
echo   Wszystko inne:          README.md i INSTRUKCJA.md
echo.
pause
exit /b 0

:blad_bleak
echo.
echo   BLAD: biblioteka bleak nie dziala. Bez niej nie ma Bluetooth.
echo   Skasuj folder venv i uruchom INSTALUJ.bat jeszcze raz.
echo.
pause
exit /b 1

:koniec_blad
pause
exit /b 1
