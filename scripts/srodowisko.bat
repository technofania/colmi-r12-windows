@echo off
rem ======================================================================
rem  srodowisko.bat - wspolny bootstrap dla INSTALUJ.bat, URUCHOM.bat
rem  i znajdz-pierscien.bat. Buduje lokalne srodowisko Pythona w folderze
rem  venv i instaluje bleak oraz python-osc.
rem
rem  Po powrocie: VPY wskazuje na Pythona z venv i errorlevel = 0.
rem  Przy bledzie errorlevel jest rozny od zera, a komunikat juz poszedl
rem  na ekran.
rem
rem  Wolajacy musi najpierw zrobic cd do korzenia paczki.
rem  Celowo BEZ setlocal - zmienna VPY ma przejsc do wolajacego skryptu.
rem ======================================================================

set "VPY="
set "PY="

rem Nie wystarczy sprawdzic, czy komenda ISTNIEJE. Na testowym komputerze
rem "py" byl w PATH, ale wskazywal na odinstalowanego Pythona 3.14 i
rem wywalal sie przy kazdym uruchomieniu. Dlatego kazdy kandydat jest
rem naprawde ODPALANY, a nie tylko szukany w PATH.
call :sprobuj py -3
if defined PY goto mam_pythona
call :sprobuj python
if defined PY goto mam_pythona
call :sprobuj python3
if defined PY goto mam_pythona
goto brak_pythona

:sprobuj
%* -c "import sys" >nul 2>nul
if errorlevel 1 exit /b 1
set "PY=%*"
exit /b 0

:mam_pythona
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" >nul 2>nul
if errorlevel 1 goto stary_python

if not exist "venv\Scripts\python.exe" goto zbuduj

set "VPY=venv\Scripts\python.exe"

rem Srodowisko skopiowane z innego komputera NIE dziala: w jego plikach
rem siedza bezwzgledne sciezki do tamtego Pythona. Plik istnieje, wiec
rem bez tej kontroli skrypt poszedlby dalej i wywalil sie pozniej, w
rem zupelnie niezrozumialym miejscu.
"%VPY%" -c "import sys" >nul 2>nul
if not errorlevel 1 goto sprawdz_biblioteki
echo    Srodowisko pochodzi z innego komputera - buduje od nowa...
rmdir /s /q venv

:zbuduj
echo    Buduje lokalne srodowisko Pythona (folder venv)...
%PY% -m venv venv
if errorlevel 1 goto blad_venv
set "VPY=venv\Scripts\python.exe"

:sprawdz_biblioteki
if exist "venv\gotowe.txt" goto koniec_ok
echo    Instaluje biblioteki: bleak (Bluetooth) i python-osc.
echo    Pierwszy raz trwa to okolo minuty. Potrzebny internet.
echo.
"%VPY%" -m pip install --upgrade pip --quiet --disable-pip-version-check
"%VPY%" -m pip install -r src\requirements.txt --disable-pip-version-check
if errorlevel 1 goto blad_pip
echo zainstalowane> "venv\gotowe.txt"
echo.

:koniec_ok
exit /b 0

:brak_pythona
echo.
echo   BLAD: nie znalazlem Pythona na tym komputerze.
echo.
echo   Co zrobic:
echo     1. Wejdz na https://www.python.org/downloads/
echo     2. Pobierz i zainstaluj Pythona 3.11 albo nowszego.
echo     3. W instalatorze ZAZNACZ pole "Add Python to PATH" - to wazne.
echo     4. Uruchom ten skrypt jeszcze raz.
echo.
exit /b 2

:stary_python
echo.
echo   BLAD: Python na tym komputerze jest za stary (potrzebny 3.9 lub nowszy).
echo   Zainstaluj nowszy z https://www.python.org/downloads/ i sprobuj ponownie.
echo.
exit /b 3

:blad_venv
echo.
echo   BLAD: nie udalo sie zbudowac srodowiska Pythona (venv).
echo   Najczestsza przyczyna: paczka lezy w folderze, do ktorego Windows
echo   nie pozwala pisac - np. w Program Files albo wprost w ZIP-ie.
echo   Rozpakuj ZIP i przenies folder np. do Dokumentow, potem sprobuj ponownie.
echo.
exit /b 4

:blad_pip
echo.
echo   BLAD: nie udalo sie zainstalowac bibliotek.
echo   Sprawdz, czy komputer ma internet. W sieci uczelnianej z proxy pip
echo   bywa blokowany - sprobuj na innej sieci albo przez telefon.
echo.
exit /b 5
