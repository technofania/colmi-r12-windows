# Pierścień COLMI R12 → TouchDesigner

Pełna instrukcja. Jeśli chcesz tylko szybko uruchomić — [README.md](README.md).

---

## 1. Co jest w paczce

| plik | do czego |
|---|---|
| `INSTALUJ.bat` | **pierwsze kliknięcie.** Buduje środowisko, instaluje biblioteki, robi skróty |
| `URUCHOM.bat` | **codzienne kliknięcie.** Łączy się z pierścieniem i wysyła OSC |
| `znajdz-pierscien.bat` | pokazuje pierścienie w pobliżu i ich adresy MAC |
| `odinstaluj.bat` | usuwa `venv` i skróty; nagrania i ustawienia zostają |
| `ustawienia.txt` | port OSC, czas pracy, tryb pulsu — zwykły plik tekstowy |
| `td\RING_START.toe` | **gotowy projekt TouchDesignera** - wystarczy kliknąć |
| `tding_osc.tox` | ten sam komponent osobno, do wrzucenia we własny projekt |
| `srcing_live.py` | program właściwy (Bluetooth → OSC) |
| `srcing_proto.py` | warstwa protokołu pierścienia |
| `src\start.py` | czyta `ustawienia.txt` i odpala `ring_live.py` |
| `src\skanuj.py` | skaner Bluetooth |
| `scripts\srodowisko.bat` | wspólny bootstrap: Python, venv, biblioteki |
| `dane_z_pierscienia.csv` | powstaje przy pierwszym uruchomieniu — zapis wszystkiego |

Paczkę można skopiować na pendrive i przenieść na inny komputer. Folder
`venv` (powstaje przy pierwszym starcie) najlepiej wtedy **usunąć** —
na nowym komputerze zbuduje się od nowa.

> Trzymaj paczkę w ścieżce bez polskich znaków i bez spacji, np. `C:\ring`.
> `Program Files` i firmowy pulpit z blokadą zapisu nie zadziałają.

---

## 2. Uruchomienie krok po kroku

### Przed włączeniem programu — rzeczy fizyczne

Te trzy punkty decydują o tym, czy cokolwiek zadziała, i są
ważniejsze niż jakiekolwiek ustawienie w programie:

1. **Pierścień na palcu, czujnik do skóry.** Dwie małe diody po
   wewnętrznej stronie palca. Czujnik skierowany na zewnątrz nie
   zmierzy nic.
2. **Docisk.** Pierścień nie może się obracać luźno. Luźny daje ruch,
   ale nigdy nie da pulsu.
3. **Zamknięta aplikacja QRing w telefonie.** Pierścień przyjmuje
   **jedno** połączenie naraz, a telefon wygrywa z komputerem.
   Dopóki aplikacja chodzi, komputer się nie połączy.

Dodatkowo, jeśli zależy Ci na pulsie: **ciepła ręka** i **bateria
powyżej 50 %**. O tym niżej, w rozdziale 6.

### Kolejność

1. Otwórz stronę TouchDesignera — na dwa sposoby, do wyboru:
   - **najprościej:** kliknij dwa razy `td\RING_START.toe`.
     To gotowy projekt, nie trzeba nic składać.
   - **do własnego projektu:** przeciągnij `tding_osc.tox`
     do swojej sieci (albo *Component → Import File*). Dostaniesz ten
     sam komponent, który możesz wpiąć gdzie chcesz.
2. Kliknij dwa razy `URUCHOM.bat` (przy pierwszym użyciu paczki
   najpierw `INSTALUJ.bat`).
3. Pierwsze uruchomienie buduje własne środowisko Pythona i instaluje
   `bleak` oraz `python-osc` — około minuty, potrzebny internet.
   Następne startują od razu.
4. W czarnym okienku zacznie lecieć linia statusu:

```
   12.4s  g:+0.03 -0.98 +0.11 |v|=0.99 ######### ppg=6420  hr= 78 (12 uderzen)  bat=78%  kroki=1204  n=143
```

   To znaczy, że wszystko działa: `g:` to trzy osie w `g`, `|v|` to
   siła wektora (1.00 w spoczynku), `n` to licznik pakietów.

Zatrzymanie: **Ctrl+C** w okienku. Program posprząta po sobie,
wyłączy strumień w pierścieniu i zamknie plik CSV.

---

## 3. Strona TouchDesignera

Komponent `ring_osc` ma w środku `OSC In CHOP` na porcie **9000**
(z `Strip Prefixes` włączonym) i wygładzanie `lag 0.14 s`. Z niego
wychodzą gotowe wyjścia:

| wyjście | kanały | co to jest |
|---|---|---|
| `out_acc` | `ax ay az` | przyspieszenie w `g`; w spoczynku jedna oś ma ±1.0 (grawitacja) |
| `out_acc_rel` | `ax ay az` | **to, czego zwykle chcesz** — odjęta pozycja spoczynkowa, więc 0 = ręka nieruchomo, a wychylenie daje odchyłkę od zera |
| `out_tilt` | `pitch roll` | przechylenie w stopniach, liczone z grawitacji |
| `out_tilt_xy` | `rollx rolly pitchn` | to samo znormalizowane do 0–1, wygodne pod UV i pozycje |
| `out_mag` | `mag` | długość wektora; 1.0 = spoczynek, 2.0+ = szarpnięcie. Dobre do progowania |
| `out_ppg_ac` | `ppg` | PPG z odjętą linią bazową — falowanie krwi |
| `out_beat` | `beat` | koperta impulsu przy każdym uderzeniu serca (atak 0.02 s, zanik 0.45 s) |
| `out_pulse` | `hr hr_inst hrv hrv_sdnn rr` | puls i HRV w liczbach |

Przykładowa wizualizacja (kropka reagująca na ruch i bijąca w rytm
serca) jest w komponencie jako `out` — można ją usunąć, to tylko podgląd.

### Czego użyć do czego

- **sterowanie pozycją / obrotem** → `out_acc_rel` albo `out_tilt_xy`.
  Nie `out_acc`, bo tam siedzi stała grawitacja.
- **trigger na gest, uderzenie, rzut** → `out_mag` z progiem około 1.5.
- **oddychający, miękki ruch** → `out_ppg_ac`.
- **rytm, flash, puls obrazu** → `out_beat`.

### Wszystkie adresy OSC

Jeśli chcesz zrobić własny `OSC In CHOP` zamiast korzystać z komponentu:

```
/ring/acc       gx gy gz     przyspieszenie w g
/ring/mag       |v|          długość wektora w g
/ring/tilt      pitch roll   stopnie
/ring/ppg       v            surowe PPG
/ring/spo2raw   v            surowy kanał SpO2
/ring/rr        ms           odstęp między uderzeniami (nadawany 2x/s)
/ring/beat      n            licznik uderzeń, rośnie o 1 na uderzenie
/ring/hr        bpm          puls, mediana — stabilny
/ring/hr_inst   bpm          puls z ostatniego odstępu — szarpie, ale natychmiast
/ring/hrv       ms           HRV jako RMSSD
/ring/hrv_sdnn  ms           HRV jako SDNN
/ring/spo2      %            saturacja
/ring/battery   %            bateria
/ring/steps     n            kroki
/ring/calories  kcal         kalorie
/ring/distance  m            dystans
```

---

## 4. Ustawienia

Wszystko w `ustawienia.txt`, format `nazwa = wartość`. Najczęściej
zmieniane:

- **`osc`** — gdzie wysyłać. `127.0.0.1:9000` to ten sam komputer.
  Żeby wysłać na inną maszynę w sieci, wpisz jej adres IP, np.
  `192.168.1.50:9000`. Puste = nie wysyłaj OSC wcale (sam podgląd i CSV).
- **`czas_minut`** — po tym czasie program sam się kończy. Domyślnie 60.
- **`puls`** — `beats` (puls i HRV, zalecane) albo `off` (tylko ruch,
  bez żadnych przerw w strumieniu).
- **`poll_hz`** — jak często dopytywać o próbkę ruchu. **Nie podnoś
  powyżej 10.** Wyjaśnienie w rozdziale 5.
- **`adres`** — zostaw puste, chyba że w pobliżu jest więcej niż jeden
  pierścień (np. cała grupa na zajęciach). Wtedy uruchom `znajdz-pierscien.bat`
  i wpisz adres swojego.

Można też podać opcję z linii poleceń — nadpisze plik:

```
URUCHOM.bat --osc 192.168.1.50:9000 --seconds 300
```

---

## 5. Dlaczego to nie chodzi szybciej

To najczęstsze pytanie, więc od razu: **ok. 4–5 odczytów ruchu na
sekundę to sufit tego pierścienia**, nie niedoróbka programu.

Pierścień sam z siebie nadaje jedną próbkę na sekundę. Okazało się, że
odpowiada na każde zapytanie, więc program dopytuje go 10 razy na
sekundę i dzięki temu wyciąga 4–5 realnych odświeżeń. Zmierzone:

| dopytywanie | realne odświeżenia ruchu | PPG |
|---|---|---|
| brak | 1.0 Hz | żyje |
| 5 Hz | 2.6 Hz | żyje |
| **10 Hz** | **4.1–5.5 Hz** | **żyje** |
| 20 Hz | 0.0 Hz | martwe |

Powyżej 10 Hz czujnik nie przyspiesza, tylko **zastyga** — każde
zapytanie przerywa mu cykl pomiarowy, zanim się skończy. Dlatego 10 to
zmierzone optimum, a nie "im więcej, tym lepiej".

Jedyny kanał szybszy niż 1 Hz to odstępy między uderzeniami serca
(2 Hz), ale one nie mówią nic o ruchu.

Skutek uboczny dopytywania: **bateria schodzi szybciej.** Przy
`poll_hz = 10` licz się ze zjedzeniem kilkudziesięciu procent w ciągu
godziny. Jeśli potrzebujesz tylko wolnego, długiego logowania — ustaw
`poll_hz = 0`.

Co jeszcze sprawdzono i co nie pomogło: wszystkie podtypy strumienia
surowego (żaden nie daje szybszego), kanał "big data", komenda ciągłego
pulsu `0x1E` (firmware R12 ją odrzuca), modyfikacja firmware (dotyczy
innego układu, a jedna osoba przy próbie **zepsuła pierścień na stałe**).

---

## 6. Puls — dlaczego kapryśny

Puls i HRV liczy **sam pierścień**, swoim wewnętrznym detektorem.
Program może go tylko poprosić i czekać. Jeśli detektor nie znajdzie
tętna, nie da się tego obejść po stronie komputera.

Co z obserwacji realnie decyduje, w kolejności ważności:

1. **Bateria.** Każdy udany pomiar był przy ≥ 51 %, każdy nieudany
   przy ≤ 50 %. Nie wiemy, czy to przyczyna, czy zbieg okoliczności,
   ale zależność była bez wyjątku.
2. **Ciepła ręka.** Zimne palce to mała amplituda sygnału. Rozetrzyj
   dłonie, poczekaj minutę.
3. **Docisk i miejsce.** Wyżej na palcu, tam gdzie grubiej, czujnik do
   skóry po wewnętrznej stronie.
4. **Bezruch.** W trakcie okienka pomiarowego (25 s) ręka płasko
   i nieruchomo.

Jak to działa technicznie: raz na `puls_co_sekund` (domyślnie 90)
program na 25 sekund **wyłącza strumień ruchu**, bo przy włączonym
strumieniu surowym wewnętrzny detektor uderzeń nie pracuje. Zbiera
uderzenia, liczy puls i HRV, wraca do ruchu. W tym czasie `out_acc`
stoi — to normalne i widać to w statusie jako `zbieram uderzenia...`.

Jeśli puls Cię nie interesuje, ustaw `puls = off`. Strumień ruchu
będzie wtedy bez ani jednej przerwy.

---

## 7. Gdy nie działa

**Okienko mówi "Pierscien niewidoczny w skanowaniu"**
- Aplikacja QRing w telefonie jest włączona → zamknij ją.
- Pierścień leży na ładowarce → zdejmij, na ładowarce często się nie
  rozgłasza.
- Pierścień zasnął po długim bezruchu → poruszaj nim.
- Bluetooth w komputerze wyłączony → włącz.
- Dalej nic → `znajdz-pierscien.bat --wszystko`. Jeśli nie widzi *żadnego*
  urządzenia, problem jest w Bluetooth komputera, nie w pierścieniu.

**Łączy się, ale po chwili zrywa**
Prawie zawsze niska bateria. Naładuj. Drugi powód: za duża odległość
— pierścień ma słaby nadajnik, trzymaj rękę w promieniu 2–3 m od
komputera lub adaptera.

**Liczby lecą w okienku, ale TouchDesigner nic nie dostaje**
- Port się nie zgadza. W `ustawienia.txt` i w `OSC In CHOP` musi być
  ta sama liczba.
- `OSC In CHOP` ma wyłączone `Active`.
- Zapora Windows blokuje port → przy pierwszym uruchomieniu
  TouchDesignera Windows pyta o zgodę, trzeba kliknąć *Zezwól*.
  Jeśli kliknięto *Anuluj*, trzeba to odkręcić w ustawieniach zapory.
- Inny program zajął port 9000 → zmień na 9001 w obu miejscach.

**`out_beat` i `out_pulse` są puste**
Pierścień nie znalazł tętna. Rozdział 6.

**Przy ruchu wartości nie zmieniają się na tej osi, na której się
spodziewasz**
Przypisanie osi do palca jest umowne — nie wiadomo, jak czujnik leży
w obudowie, a dodatkowo zależy to od tego, na którą rękę i w którą
stronę założysz pierścień. Po prostu sprawdź ruchem, która oś robi to,
czego chcesz.

---

## 8. Plik CSV

Przy każdym uruchomieniu powstaje `dane_z_pierscienia.csv` (nazwa
z `ustawienia.txt`). **Nadpisuje się** przy kolejnym starcie — jeśli
nagranie jest cenne, zmień mu nazwę albo skopiuj.

Kolumny: `t_iso` (czas zegarowy), `t_s` (sekundy od startu), `kind`
(rodzaj: `acc`, `ppg`, `rr`, `battery`, `steps`…), `v1 v2 v3`
(wartości) i `hex` — surowa ramka 16 bajtów, dokładnie tak, jak
przyszła z pierścienia.

`hex` jest tam celowo: gdyby kiedyś wyszło, że coś jest parsowane
źle, z tej kolumny można odtworzyć wszystko od nowa, bez powtarzania
nagrania.

---

## 9. Bezpieczeństwo pierścienia

Program wysyła **tylko** komendy sprawdzone na R12:

- `A1 04` / `A1 02` — włącz/wyłącz strumień surowy
- `0x69` / `0x6A` — start/stop pomiaru (puls, SpO2, odstępy R-R)
- `0x03` — bateria

**Nigdy** nie wysyła: wyłączenia pierścienia (`0x08`), resetu
fabrycznego (`0xFF`), ustawiania zegara (`0x01`) ani niczego
związanego z firmware, OTA czy bootloaderem. Nie da się tym
programem zepsuć pierścienia ani utracić danych z aplikacji.

Kroki, kalorie i dystans przychodzą same, bez żadnej komendy.
