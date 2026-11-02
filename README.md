# Pierścień COLMI R12 w TouchDesignerze na Windows – zestaw dla studentów

Smart ring **COLMI R12** czytany przez Bluetooth i wysyłany do **TouchDesignera**
przez OSC – ruch ręki, surowy sygnał PPG, puls i HRV, kroki i bateria.
Instalator w jednym kliknięciu, gotowy projekt TD, zapis do CSV.
Nic nie ląduje w systemie i nie potrzeba praw administratora.

```
/ring/acc  gx gy gz      przyspieszenie w g      /ring/beat   impuls na uderzenie serca
/ring/tilt pitch roll    przechylenie            /ring/hr     puls
/ring/mag  |v|           siła ruchu              /ring/hrv    HRV (RMSSD)
/ring/ppg  v             surowy sygnał optyczny  /ring/steps  kroki
```

---

## Czego potrzebujesz

- Windows 10 lub 11 z **Bluetooth** (wbudowanym albo adapterem USB)
- **Python 3.9 lub nowszy** – instalator powie, skąd wziąć, jeśli nie ma
- [TouchDesigner](https://derivative.ca/download) (darmowy Non-Commercial wystarczy)
- pierścień **COLMI R12**, naładowany
- internet **tylko raz**, przy instalacji bibliotek

> **Nie trzeba parować pierścienia w Windows.** Zestaw łączy się z nim sam,
> bez dodawania urządzenia w ustawieniach Bluetooth.

## Instalacja (2 minuty)

1. **Pobierz paczkę:** zielony przycisk **Code → Download ZIP** na tej stronie.
2. **Rozpakuj** ZIP, np. do `Dokumenty`. Nie uruchamiaj niczego z wnętrza ZIP-a.
3. Kliknij dwa razy **`INSTALUJ.bat`**.
   - Jeśli pojawi się *„System Windows ochronił ten komputer"*:
     **Więcej informacji → Uruchom mimo to**.
   - Okno UAC się nie pojawi – ta paczka nie potrzebuje administratora.
4. Instalator zbuduje lokalne środowisko Pythona w folderze `venv`, zainstaluje
   `bleak` i `python-osc` i zrobi dwa skróty na pulpicie.

Żadnego `pip` ręcznie, żadnej zmiennej PATH, nic poza folderem paczki.

## Pierwsze uruchomienie

**Najpierw rzeczy fizyczne – one decydują, czy cokolwiek zadziała:**

1. **Pierścień na palcu, czujnik do skóry.** Dwie małe diody po wewnętrznej
   stronie palca. Czujnik skierowany na zewnątrz nie zmierzy nic.
2. **Dociśnięty.** Nie może się obracać luźno. Luźny daje ruch, ale nie da pulsu.
3. **Zamknij aplikację QRing w telefonie.** Pierścień przyjmuje **jedno**
   połączenie naraz i telefon wygrywa z komputerem.

Potem:

4. Otwórz **`td\RING_START.toe`** – gotowy projekt TouchDesignera.
5. Kliknij **`URUCHOM.bat`**.

W okienku poleci linia statusu:

```
   12.4s  g:+0.03 -0.98 +0.11 |v|=0.99 ######### ppg=6420  hr= 78 (12 uderzen)  bat=78%  kroki=1204  n=143
```

To znaczy, że wszystko działa. Jeśli liczby lecą tutaj, a w TouchDesignerze nie –
problem jest w OSC, patrz [INSTRUKCJA.md](INSTRUKCJA.md) rozdział 7.

Zatrzymanie: **Ctrl+C** w okienku. Program wyłączy strumień w pierścieniu
i zamknie plik CSV.

## Co jest w projekcie TouchDesignera

Komponent `ring` ma w środku `OSC In CHOP` na porcie 9000 i wygładzanie.
Z niego wychodzą gotowe wyjścia – nie trzeba nic składać:

| wyjście | do czego |
|---|---|
| `out_acc_rel` | **ruch wyzerowany względem spoczynku** – to, czego zwykle chcesz do sterowania |
| `out_tilt_xy` | przechylenie znormalizowane 0–1, wygodne pod UV i pozycje |
| `out_mag` | siła ruchu; 1.0 = spoczynek, 2.0+ = szarpnięcie. Dobre do progowania gestów |
| `out_ppg_ac` | przebieg PPG bez linii bazowej – miękki, „oddychający" ruch |
| `out_beat` | impuls przy każdym uderzeniu serca – rytm, flash |
| `out_pulse` | puls i HRV w liczbach |
| `out_acc`, `out_tilt` | surowe wartości, gdy potrzebujesz ich bez obróbki |

`out_acc` zawiera stałą grawitację (jedna oś ma ±1.0 w spoczynku) – do sterowania
użyj `out_acc_rel`.

Chcesz to we własnym projekcie? Przeciągnij **`td\ring_osc.tox`** do swojej sieci.

## Ustawienia

Wszystko w **`ustawienia.txt`**, zwykły plik tekstowy, format `nazwa = wartość`.
W większości przypadków nie trzeba tam nic zmieniać. Najczęściej zmieniane:

| ustawienie | znaczenie |
|---|---|
| `osc` | gdzie wysyłać; `127.0.0.1:9000` = ten sam komputer. Inna maszyna w sieci: wpisz jej IP |
| `czas_minut` | po tym czasie program sam się kończy (domyślnie 60) |
| `puls` | `beats` = puls i HRV, `off` = tylko ruch, bez przerw w strumieniu |
| `poll_hz` | jak często dopytywać o próbkę ruchu. **Nie podnoś powyżej 10** |
| `adres` | zostaw puste; wpisz tylko, gdy w pobliżu jest kilka pierścieni |

Można też podać opcję z linii poleceń – nadpisze plik:
`URUCHOM.bat --osc 192.168.1.50:9000 --seconds 300`

## Nie widzi pierścienia?

Kliknij **`znajdz-pierscien.bat`** – pokaże, co Bluetooth widzi w pobliżu i poda
adres MAC pierścienia. Tylko nasłuchuje, nie wysyła do pierścienia ani jednej
komendy.

Najczęstsze przyczyny, w kolejności: włączona aplikacja QRing w telefonie,
pierścień na ładowarce (wtedy często nie rozgłasza się wcale), pierścień uśpiony
po długim bezruchu, wyłączony Bluetooth.

---

## Co działa, a co nie – uczciwie

**Działa pewnie, sprawdzone na sprzęcie:**

- ruch (akcelerometr) w `g`, ok. **4–5 odczytów na sekundę**
- surowy PPG, ok. 1 na sekundę
- bateria, kroki, kalorie, dystans
- przechylenie i siła ruchu liczone z grawitacji
- automatyczne ponowne łączenie, keepalive, zapis do CSV z surowym hexem

**Działa, ale kaprysi:**

- **puls i HRV.** Liczy je sam pierścień, swoim wewnętrznym detektorem – program
  może tylko poprosić i czekać. Potrzebuje ciepłych palców, dobrego docisku
  i baterii powyżej ~50 %. Zimna ręka = brak pulsu. Kod jest gotowy
  (`puls = beats`) i raz dał 30 uderzeń, 90 bpm, RMSSD 43 ms – ale **nie jest
  to powtarzalne** i nie udało się tego potwierdzić serią pomiarów.

**Nie da się – sprawdzone i zamknięte:**

- szybszego strumienia niż ok. 5 Hz. Firmware na to nie pozwala: przy
  dopytywaniu powyżej 10 Hz czujnik nie przyspiesza, tylko **zastyga**.
  Szczegóły i tabela pomiarów w [INSTRUKCJA.md](INSTRUKCJA.md) rozdział 5.
- komenda ciągłego pulsu `0x1E` – firmware R12 ją odrzuca
- historia z pamięci pierścienia – wszystkie kanały zwracają puste dane

## Bezpieczeństwo pierścienia

Program wysyła **tylko** komendy sprawdzone na R12: `A1 04`/`A1 02` (strumień
surowy), `0x69`/`0x6A` (start/stop pomiaru), `0x03` (bateria).

**Nigdy** nie wysyła wyłączenia pierścienia (`0x08`), resetu fabrycznego (`0xFF`),
ustawiania zegara (`0x01`) ani niczego związanego z firmware, OTA czy
bootloaderem. Tą paczką nie da się zepsuć pierścienia ani utracić danych
z aplikacji.

## Dla ciekawych – co w środku

| plik | rola |
|---|---|
| `src/ring_proto.py` | warstwa protokołu: ramki 16-bajtowe, suma kontrolna, parser pakietów |
| `src/ring_live.py` | sesja BLE, OSC, CSV, podgląd, keepalive, ponowne łączenie |
| `src/skanuj.py` | bierne skanowanie BLE |
| `src/start.py` | czyta `ustawienia.txt` i składa wywołanie |
| `scripts/srodowisko.bat` | wspólny bootstrap: Python, venv, biblioteki |

Akcelerometr na R12 to **signed 16-bit big-endian, 14 bitów dosuniętych do lewej**
(dwa dolne bity zawsze zerowe), czyli **8192 jednostki na 1 g**: Y = bajty 2–3,
Z = 4–5, X = 6–7. To **nie** ten sam układ co w R02 (12-bit) – parser z R02 na
R12 daje błędne osie.

Odstępy R-R siedzą w odpowiedzi `0x69` typu 5 i 8, w bajtach 6–7,
**little-endian, w milisekundach**, nadawane 2× na sekundę z powtórzeniami.

Odinstalowanie: **`odinstaluj.bat`** – usuwa `venv` i skróty, zostawia nagrania
i ustawienia. W systemie nic nie zostało zainstalowane.

---

[INSTRUKCJA.md](INSTRUKCJA.md) – pełna instrukcja: wszystkie adresy OSC, czego
użyć do czego, pomiary częstotliwości, rozwiązywanie problemów.
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) – źródła wiedzy o protokole.
