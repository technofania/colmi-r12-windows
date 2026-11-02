# Third-party notices

## Protokół COLMI / QRing

Protokół w `src/ring_proto.py` (ramki 16-bajtowe `[cmd][14 B danych][suma]`,
suma kontrolna `sum(bytes[0:15]) & 0xFF`, usługa UART `6e40fff0-…`, komendy
`0x03` bateria, `0x69`/`0x6A` start/stop pomiaru, `0xA1` strumień surowy)
został napisany na podstawie publicznej dokumentacji reverse engineeringu
pierścienia **COLMI R02**:

- https://github.com/tahnok/colmi_r02_client (MIT License)
- https://github.com/edgeimpulse/example-data-collection-colmi-r02
- https://codeberg.org/Freeyourgadget/Gadgetbridge – implementacja QRing /
  Yawell (`devices/yawell/ring/`), użyta jako źródło znaczeń kodów błędów
  i podtypów

**Nie skopiowano żadnego kodu** z tych projektów. Implementacja tutaj jest
napisana od zera na podstawie opisu protokołu i zweryfikowana na realnym
pierścieniu COLMI R12 (hardware `RT11CR_V1.0`, firmware `RT11CR_1.00.08_250514`).

Ustalenia własne, których nie ma w żadnym z powyższych źródeł, bo R12 ma inny
sprzęt niż R02 (Realtek zamiast BlueX, akcelerometr ST zamiast STK8321):

- **kodowanie akcelerometru na R12**: signed 16-bit big-endian, 14 bitów
  dosuniętych do lewej, 8192 jednostki na 1 g; Y = bajty 2–3, Z = 4–5, X = 6–7
  (parser 12-bitowy z R02 daje na R12 błędne osie)
- **komenda `A1 04` działa na R12** i pierścień odpowiada na każde zapytanie,
  co pozwala podnieść tempo z 1 Hz do ok. 5 Hz
- **odstępy R-R** w odpowiedzi `0x69` typu 5 i 8, bajty 6–7, little-endian, ms
- `0x73 0x12` = kroki / kalorie (÷10) / dystans, `0x73 0x0c` = bateria
- `0x1E` (ciągły puls) jest na R12 **nieobsługiwane** – firmware odpowiada
  `0x9E 0xEE`

## Biblioteki instalowane przez `INSTALUJ.bat`

Nie są dołączone do tej paczki – `pip` pobiera je przy instalacji.

| biblioteka | licencja | źródło |
|---|---|---|
| [bleak](https://github.com/hbldh/bleak) | MIT | Bluetooth Low Energy na Windows (backend WinRT) |
| [python-osc](https://github.com/attwad/python-osc) | Unlicense (domena publiczna) | wysyłanie OSC do TouchDesignera |

Zależności pośrednie `bleak` na Windows (`winrt-*`, `typing-extensions`)
instalują się automatycznie i mają własne licencje – patrz ich strony w PyPI.

## TouchDesigner

TouchDesigner jest produktem [Derivative](https://derivative.ca/) i nie jest
częścią tej paczki. Pliki `td/RING_START.toe` i `td/ring_osc.tox` to własne
projekty, zbudowane wyłącznie ze standardowych operatorów.
