# COLMI R12 w TouchDesignerze (Windows)

Pierścień COLMI R12 gada po Bluetooth. Ten zestaw go czyta i wysyła dane do
TouchDesignera przez OSC: ruch ręki, surowy sygnał z czujnika optycznego, puls
z HRV, kroki i stan baterii.

Robione na zajęcia, więc instalacja to jedno kliknięcie i nie potrzebuje
administratora. Nic nie wchodzi do systemu, wszystko siedzi w folderze paczki.

## Co musisz mieć

Windows 10 albo 11 z Bluetoothem (wbudowany wystarcza, adapter USB też).
Python 3.9 lub nowszy; jak go nie ma, instalator powie, skąd wziąć.
TouchDesignera, bo w nim to działa (darmowa wersja Non-Commercial wystarcza).
Naładowany pierścień COLMI R12. Internet, ale tylko raz, przy pobieraniu
dwóch bibliotek.

Pierścienia nie trzeba parować w ustawieniach Bluetooth. Zestaw znajduje go sam.

## Instalacja

Code → Download ZIP, rozpakuj u siebie (byle nie w Program Files i nie
uruchamiaj niczego z wnętrza ZIP-a), kliknij `INSTALUJ.bat`.

Windows może zapytać przez "System Windows ochronił ten komputer". Wtedy
Więcej informacji → Uruchom mimo to. UAC się nie pojawi, bo paczka nie rusza
systemu.

Instalator buduje sobie osobne środowisko Pythona w podfolderze `venv`,
dociąga `bleak` i `python-osc` i robi dwa skróty na pulpicie. Potem już nie
jest potrzebny.

## Jak uruchomić

Najpierw założenie pierścienia, bo od tego zależy więcej niż od jakichkolwiek
ustawień:

- czujnik (dwie diody) musi dotykać skóry, po wewnętrznej stronie palca
- pierścień dociśnięty, żeby nie obracał się luźno; luźny pokaże ruch, ale
  pulsu nie da
- zamknij QRing w telefonie, bo pierścień obsługuje jedno połączenie naraz
  i telefon zawsze wygrywa z komputerem

Potem otwórz `td\RING_START.toe` i kliknij `URUCHOM.bat`. W czarnym okienku
poleci coś takiego:

```
   12.4s  g:+0.03 -0.98 +0.11 |v|=0.99 ######### ppg=6420  hr= 78 (12 uderzen)  bat=78%  kroki=1204  n=143
```

Jak liczby się ruszają, strumień idzie. Jak ruszają się tutaj, a w
TouchDesignerze nie, to problem siedzi po stronie OSC i opisałem go
w [INSTRUKCJA.md](INSTRUKCJA.md).

Wyjście: Ctrl+C. Program wyłącza wtedy strumień w pierścieniu i domyka CSV.

## Co dostajesz w TouchDesignerze

Komponent `ring` ma w środku OSC In CHOP na porcie 9000 i trochę wygładzania.
Wychodzą z niego gotowe kanały.

`out_acc_rel` to ruch wyzerowany względem spoczynku i w większości przypadków
właśnie tego chcesz do sterowania. `out_acc` daje to samo surowo, ale z wpisaną
grawitacją (jedna oś ma ±1.0, kiedy ręka leży), więc do sterowania nadaje się
słabo.

`out_tilt_xy` to przechylenie przeskalowane na 0-1, wygodne pod UV i pozycje.
`out_tilt` to samo w stopniach.

`out_mag` mówi, jak mocno pierścień jest szarpany: 1.0 w spoczynku, 2.0 i więcej
przy wymachu. Dobre na progi i triggery.

`out_ppg_ac` to przebieg z czujnika optycznego po odjęciu linii bazowej. Miękki,
falujący sygnał.

`out_beat` strzela impulsem na każde uderzenie serca, a `out_pulse` podaje puls
i HRV liczbowo.

Jak chcesz to u siebie, a nie w moim projekcie, przeciągnij `td\ring_osc.tox`
do swojej sieci.

## Ustawienia

W `ustawienia.txt`, zwykły tekst, `nazwa = wartość`. Zwykle nie ma tam po co
zaglądać. Co się czasem przydaje:

`osc` mówi, gdzie wysyłać. `127.0.0.1:9000` to ten sam komputer; żeby strzelać
na inną maszynę w sieci, wpisz jej IP.

`czas_minut` to po ilu minutach program sam się zamknie.

`puls` ustawiony na `beats` zbiera puls i HRV. `off` zostawia tylko ruch i nie
przerywa strumienia ani na sekundę.

`poll_hz` to tempo dopytywania pierścienia. Nie podnoś powyżej 10, niżej jest
napisane dlaczego.

`adres` zostaw puste, chyba że w pokoju jest kilka pierścieni.

Opcje z linii poleceń nadpisują plik, np.
`URUCHOM.bat --osc 192.168.1.50:9000 --seconds 300`.

## Nie widzi pierścienia

Kliknij `znajdz-pierscien.bat`. Pokaże, co Bluetooth widzi w pobliżu, razem
z adresami MAC. Tylko nasłuchuje, do pierścienia nie leci ani jedna komenda.

Przyczyny, w kolejności od najczęstszej: włączony QRing w telefonie, pierścień
na ładowarce (wtedy często nie rozgłasza się wcale), pierścień uśpiony po
dłuższym bezruchu, wyłączony Bluetooth.

## Czego ten pierścień nie umie

Ruch wychodzi w tempie około 4-5 odczytów na sekundę i to jest sufit sprzętu,
nie niedoróbka. Pierścień sam z siebie nadaje raz na sekundę, ale odpowiada na
każde zapytanie, więc program dopytuje go 10 razy na sekundę i tyle z tego
wyciąga. Przy 20 Hz czujnik nie przyspiesza, tylko zastyga: przestaje odświeżać
wartości i gasi kanał optyczny. Pomiary są w [INSTRUKCJA.md](INSTRUKCJA.md).

Puls i HRV liczy sam pierścień, swoim detektorem. Program może tylko poprosić
i czekać. Detektor potrzebuje ciepłych palców, dobrego docisku i, z tego co
widziałem, baterii powyżej jakichś 50%. Zimna ręka to brak pulsu. Raz wyszło
30 uderzeń, 90 bpm, RMSSD 43 ms, ale nie udało mi się tego powtórzyć, więc
traktuj puls jako bonus, nie jako pewny kanał. Ruch i PPG są pewne.

Czego się nie da w ogóle: komendę ciągłego pulsu (`0x1E`) firmware R12 odrzuca,
a historia z pamięci pierścienia wychodzi pusta na wszystkich kanałach.

## Bezpieczeństwo

Do pierścienia lecą tylko trzy rodzaje komend. `A1 04` i `A1 02` włączają
i wyłączają strumień surowy, `0x69` i `0x6A` startują i zatrzymują pomiar,
`0x03` pyta o baterię.

Nie ma tu wyłączania pierścienia (`0x08`), resetu fabrycznego (`0xFF`),
ustawiania zegara (`0x01`) ani niczego, co dotyka firmware, OTA czy
bootloadera. Tym zestawem nie zepsujesz pierścienia i nie stracisz danych
z aplikacji.

## Co w środku

`src/ring_proto.py` trzyma protokół: ramki po 16 bajtów, sumę kontrolną
i parser pakietów. `src/ring_live.py` prowadzi sesję BLE, wysyła OSC, pisze CSV
i pilnuje, żeby strumień nie zamilkł. `src/skanuj.py` to skaner,
`src/start.py` czyta ustawienia i składa wywołanie, a `scripts/srodowisko.bat`
zajmuje się Pythonem i bibliotekami.

Dwie rzeczy, które mogą się przydać, jak grzebiesz w R12 sam. Akcelerometr to
signed 16-bit big-endian z 14 bitami dosuniętymi do lewej, czyli 8192 jednostki
na 1 g, przy czym Y siedzi w bajtach 2-3, Z w 4-5, a X w 6-7. To nie ten sam
układ co w R02, więc parser pisany pod R02 da na R12 bzdury. Odstępy R-R
przychodzą w odpowiedzi `0x69` typu 5 i 8, w bajtach 6-7, little-endian,
w milisekundach, nadawane dwa razy na sekundę z powtórzeniami.

CSV zapisuje przy okazji surowy hex każdej ramki. Jak się kiedyś okaże, że coś
parsuję źle, da się to odtworzyć bez powtarzania nagrania.

## Odinstalowanie

`odinstaluj.bat` usuwa `venv` i skróty, a nagrania i ustawienia zostawia.
W systemie nic nie zostało zainstalowane, więc nie ma czego odkręcać; sam folder
można potem skasować.

---

Pełna instrukcja, z wszystkimi adresami OSC, tabelą pomiarów częstotliwości
i rozwiązywaniem problemów: [INSTRUKCJA.md](INSTRUKCJA.md). Skąd wzięła się
wiedza o protokole: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
Licencja MIT.
