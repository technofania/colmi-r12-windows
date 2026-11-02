#!/usr/bin/env python3
"""
ring_proto.py - wspolna warstwa protokolu QRing dla pierscieni COLMI (R02 / R12).

Uzywana przez acc_probe.py i ring_live.py, zeby nie powtarzac protokolu.
Zrodla: inzynieria wstecshna R02 (tahnok/colmi_r02_client,
edgeimpulse/example-data-collection-colmi-r02).

Potwierdzone na COLMI R12 (firmware stock, listopad 2025):
  - uslugi GATT identyczne jak w R02 (UART 6e40fff0 + kanal V2 de5bf728),
  - bateria 0x03 odpowiada poprawnie,
  - surowy strumien A1 04 dziala i zwraca podtypy 01 / 02 / 03.
"""

import asyncio
import collections
import datetime as dt
import statistics as st
import sys

from bleak import BleakClient, BleakScanner

# --- UUID ---
UART_SERVICE = "6e40fff0-b5a3-f393-e0a9-e50e24dcca9e"
UART_WRITE = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
UART_NOTIFY = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
V2_SERVICE = "de5bf728-d711-4e47-af26-65e3012a5dc7"
V2_WRITE = "de5bf72a-d711-4e47-af26-65e3012a5dc7"
V2_NOTIFY = "de5bf729-d711-4e47-af26-65e3012a5dc7"

# --- komendy ---
# Nazwy i numery z Gadgetbridge (devices/yawell/ring/YawellRingConstants.java),
# czyli z dzialajacej obslugi wlasnie R12, nie z domyslow po R02.
#
# NIE WYSYLAC: 0x08 = wylaczenie pierscienia, 0xFF = reset fabryczny,
# 0x01 = ustawienie zegara (zmienia stan pierscienia bez potrzeby).
CMD_BATTERY = 0x03
CMD_REALTIME_HR = 0x1E   # ciagly puls, ~1 Hz
CMD_RT_START = 0x69      # jednorazowy pomiar ("manual heart rate")
CMD_RT_STOP = 0x6A
CMD_NOTIFICATION = 0x73
CMD_RAW = 0xA1           # surowy strumien; Gadgetbridge tej komendy nie zna

# argumenty 0x1E
RT2_ENABLE = 0x01
RT2_DISABLE = 0x02
RT2_CONTINUE = 0x03      # pomiar gasnie po 60 s, trzeba odswiezac

# typy strumienia dla 0x69 / 0x6A
RT_HEART_RATE = 0x01
RT_SPO2 = 0x03
RT_HRV = 0x05            # "beat-to-beat health check"
RT_STRESS = 0x08
RT_NAMES = {RT_HEART_RATE: "hr", RT_SPO2: "spo2", RT_HRV: "hrv", RT_STRESS: "stress"}

# Typy, ktore zamiast jednej liczby oddaja strumien odstepow miedzy
# uderzeniami serca (R-R) w milisekundach, little-endian w bajtach 6-7.
# Ustalone pomiarowo na R12: suma odstepow zgadza sie z czasem pomiaru
# w 95-96%, a liczba uderzen z pulsem wyliczonym ze sredniego odstepu.
RT_RR_TYPES = (RT_HRV, RT_STRESS)

# Odmowa wykonania komendy: pierscien odpowiada numerem komendy z ustawionym
# najwyzszym bitem i bajtem 0xEE. Zaobserwowane na R12 dla 0x1E (-> 0x9E 0xEE):
# ta komenda jest w Gadgetbridge, ale firmware R12 jej nie obsluguje.
NAK_MARKER = 0xEE

ACT_START = 0x01
ACT_CONTINUE = 0x03

RAW_ENABLE = 0x04
RAW_DISABLE = 0x02

# Skala akcelerometru: ile jednostek na 1 g.
# Wyznaczone pomiarowo na R12 (acc_probe.py, 5 pozycji spoczynkowych):
# sredni modul wektora = 8170 przy rozrzucie 2.0%, czyli 8192 = 2^13.
# Zgadza sie z ST LIS2DW12 w trybie +/-4 g, 14 bitow dosunietych do lewej
# w polu 16-bitowym: 2048 jednostek/g << 2 = 8192.
ACC_COUNTS_PER_G = 8192.0


def packet(cmd: int, payload: bytes = b"") -> bytes:
    """16 bajtow: [cmd][14 bajtow danych][suma kontrolna = suma(0..14) & 0xFF]."""
    if len(payload) > 14:
        raise ValueError("payload > 14 bajtow")
    b = bytearray(16)
    b[0] = cmd
    b[1:1 + len(payload)] = payload
    b[15] = sum(b[:15]) & 0xFF
    return bytes(b)


def pkt_raw_enable() -> bytes:
    return packet(CMD_RAW, bytes([RAW_ENABLE]))


def pkt_raw_disable() -> bytes:
    return packet(CMD_RAW, bytes([RAW_DISABLE]))


def pkt_hr_rt(action: int) -> bytes:
    """Ciagly puls 0x1E: RT2_ENABLE / RT2_CONTINUE / RT2_DISABLE."""
    return packet(CMD_REALTIME_HR, bytes([action]))


def pkt_rt_start(rt_type: int) -> bytes:
    return packet(CMD_RT_START, bytes([rt_type, ACT_START]))


def pkt_rt_continue(rt_type: int) -> bytes:
    return packet(CMD_RT_START, bytes([rt_type, ACT_CONTINUE]))


def pkt_rt_stop(rt_type: int) -> bytes:
    return packet(CMD_RT_STOP, bytes([rt_type, 0, 0]))


def s12(hi: int, lo: int) -> int:
    """
    12-bitowa liczba ze znakiem wg parsera R02: 8 bitow z hi + dolne 4 bity z lo.

    NIE uzywac na R12 - zostawione tylko do porownania. Na R12 os jest 16-bitowa
    (patrz s16), wiec ten uklad gubi bity 7-4 z lo i wstawia w ich miejsce
    bity wypelnienia. Blad modulu wektora rosnie z 2.0% do 2.8%.
    """
    v = (hi << 4) | (lo & 0x0F)
    return v - 0x1000 if v & 0x800 else v


def s16(hi: int, lo: int) -> int:
    """16-bitowa liczba ze znakiem, big-endian (uklad osi na R12)."""
    v = (hi << 8) | lo
    return v - 0x10000 if v & 0x8000 else v


def u16(hi: int, lo: int) -> int:
    return (hi << 8) | lo


def u16le(lo: int, hi: int) -> int:
    """16 bitow bez znaku, little-endian - tak sa kodowane odstepy R-R."""
    return (hi << 8) | lo


def now_iso() -> str:
    return dt.datetime.now().isoformat(timespec="milliseconds")


def parse_packet(d: bytes):
    """
    Rozklada 16-bajtowy pakiet na (kind, dane).

    kind: acc | ppg | spo2raw | hr | spo2 | battery | steps | a1_XX | pkt_XX
    dane: dict z wartosciami, {} gdy pakiet nierozpoznany.

    Osie acc: Y = bajty 2-3, Z = 4-5, X = 6-7 (mapowanie jak w R02), ale na R12
    kazda os to 16 bitow ze znakiem big-endian, nie 12 bitow. Potwierdzone
    pomiarowo: grawitacja zmienia znak na Y po odwroceniu pierscienia, modul
    wektora staly w 5 roznych pozycjach spoczynkowych z bledem 2.0%.
    Pola gx/gy/gz to to samo przeliczone na g.
    """
    if not d:
        return None
    c = d[0]

    if c == CMD_RAW and len(d) >= 10:
        sub = d[1]
        if sub == 0x03:
            x, y, z = s16(d[6], d[7]), s16(d[2], d[3]), s16(d[4], d[5])
            return "acc", {"x": x, "y": y, "z": z,
                           "gx": x / ACC_COUNTS_PER_G,
                           "gy": y / ACC_COUNTS_PER_G,
                           "gz": z / ACC_COUNTS_PER_G}
        if sub == 0x02:
            # Tylko bajty 2-3 sa zywe. Bajty 4-9 to okno automatycznej regulacji
            # czulosci, nie przebieg: na 194 pakietach z czterech zapisow nie
            # zmienily sie ani razu, a ich wartosci skladaja sie na siebie -
            # gora 8424, dol 7100, rozpietosc 1324, czyli dokladnie 8424-7100.
            # Ta sama struktura jest w podtypie 0x01 (137, 100, 37).
            return "ppg", {"ppg": u16(d[2], d[3]), "f1": u16(d[4], d[5]),
                           "f2": u16(d[6], d[7]), "f3": u16(d[8], d[9])}
        if sub == 0x01:
            return "spo2raw", {"v": u16(d[2], d[3]), "f1": d[5], "f2": d[7], "f3": d[9]}
        return f"a1_{sub:02x}", {}

    if c == 0x73 and len(d) >= 11:
        # Niezamawiane pakiety aktywnosci, odkryte na R12 (nieudokumentowane w R02).
        sub = d[1]
        if sub == 0x12:
            # "Live activity" wg Gadgetbridge: trzy liczniki 24-bitowe big-endian,
            # kalorie z dzielnikiem 10, dystans w metrach. Przychodza same, bez
            # zadnej komendy, i tylko gdy pierscien wykryje ruch.
            return "steps", {"steps": (d[2] << 16) | (d[3] << 8) | d[4],
                             "calories": ((d[5] << 16) | (d[6] << 8) | d[7]) / 10,
                             "distance_m": (d[8] << 16) | (d[9] << 8) | d[10]}
        if sub == 0x0c:
            # Samoczynna aktualizacja poziomu baterii (Gadgetbridge:
            # NOTIFICATION_BATTERY_LEVEL), d[3] = ladowanie.
            return "battery", {"level": d[2], "charging": d[3] if len(d) > 3 else 0}
        return f"pkt_73_{sub:02x}", {}

    if c == CMD_REALTIME_HR and len(d) >= 2:
        # Odpowiedz ciaglego pulsu: bpm wprost w bajcie 1, bez bajtu bledu.
        # 0 = pierscien jeszcze nie ma odczytu.
        return ("hr" if d[1] else "hr_wait"), ({"v": d[1]} if d[1] else {})

    if c == CMD_RT_START and len(d) >= 8:
        rt_type = d[1]
        kind = RT_NAMES.get(rt_type, f"rt_{rt_type:02x}")
        if d[2] != 0:
            # Kody bledu wg Gadgetbridge: 1 = pierscien zalozony nieprawidlowo,
            # 2 = blad chwilowy / brak danych.
            return kind + "_err", {"err": d[2]}
        if rt_type in RT_RR_TYPES:
            # Typy 5 i 8 nie oddaja gotowej liczby w bajcie 3 - ten bajt jest
            # zawsze zerem. Prawdziwa dana to odstep R-R w ms w bajtach 6-7,
            # nadawany 2 razy na sekunde z powtarzaniem ostatniej wartosci.
            rr = u16le(d[6], d[7])
            if rr:
                return "rr", {"rr": rr, "bpm": 60000.0 / rr, "src": kind}
            return kind + "_wait", {}
        if d[3] != 0:  # 0 = pierscien jeszcze mierzy
            return kind, {"v": d[3]}
        return kind + "_wait", {}

    if c & 0x80 and len(d) >= 2 and d[1] == NAK_MARKER:
        # Odmowa: komenda nieobslugiwana przez to firmware.
        return "nak", {"cmd": c & 0x7F}

    if c == CMD_BATTERY and len(d) >= 3:
        return "battery", {"level": d[1], "charging": d[2]}

    return f"pkt_{c:02x}", {}


class RrTracker:
    """
    Zbiera odstepy R-R (miedzy uderzeniami serca) i liczy z nich puls i HRV.

    Pierscien nadaje 2 razy na sekunde, ale powtarza ostatnia wartosc, dopoki
    nie wykryje nowego uderzenia. Dlatego powtorzenia trzeba odrzucac - inaczej
    kazde uderzenie policzyloby sie kilka razy i HRV wyszloby falszywie niskie.

    Pulapka: dwa kolejne uderzenia moga naprawde miec ten sam odstep co do
    milisekundy. Odrzucamy powtorzenie tylko wtedy, gdy przyszlo szybciej, niz
    moglo minac jedno uderzenie - wtedy na pewno jest to ta sama wartosc
    nadana ponownie, a nie nowe uderzenie.

    Wspolczynnik REPEAT_FACTOR dobrany na prawdziwym zapisie (ring_report.csv,
    62 pakiety typu 5 i 62 typu 8): sprawdzianem jest to, czy suma przyjetych
    odstepow rowna sie czasowi pomiaru. Dla 1.0-1.25 wychodzi 1.01 i 0.95;
    przy 0.75 typ 8 daje 1.18, czyli policzylby o 18% uderzen za duzo.
    """

    REPEAT_FACTOR = 1.2

    def __init__(self, keep=64):
        self.keep = keep
        self.rr = collections.deque(maxlen=keep)
        self.last_rr = None
        self.last_t = None
        self.beats = 0
        self.repeats = 0

    def add(self, t, rr_ms):
        """Zwraca True, jesli to nowe uderzenie (a nie powtorzenie)."""
        if not 250 <= rr_ms <= 2400:   # 25-240 bpm, poza tym to nie jest puls
            return False
        if (self.last_rr == rr_ms and self.last_t is not None
                and (t - self.last_t) * 1000 < rr_ms * self.REPEAT_FACTOR):
            self.repeats += 1
            return False
        self.rr.append(rr_ms)
        self.last_rr, self.last_t = rr_ms, t
        self.beats += 1
        return True

    @property
    def bpm(self):
        """Puls z mediany ostatnich odstepow - odporna na pojedynczy falsz."""
        if not self.rr:
            return None
        recent = list(self.rr)[-8:]
        return 60000.0 / st.median(recent)

    @property
    def bpm_inst(self):
        """Puls z ostatniego odstepu - szarpie sie, ale reaguje natychmiast."""
        return 60000.0 / self.rr[-1] if self.rr else None

    @property
    def rmssd(self):
        """
        HRV jako RMSSD w ms: pierwiastek ze sredniej kwadratow roznic miedzy
        kolejnymi odstepami. To standardowa miara zmiennosci krotkoterminowej.
        """
        if len(self.rr) < 4:
            return None
        r = list(self.rr)
        diffs = [r[i + 1] - r[i] for i in range(len(r) - 1)]
        return (sum(x * x for x in diffs) / len(diffs)) ** 0.5

    @property
    def sdnn(self):
        """HRV jako odchylenie standardowe odstepow w ms."""
        return st.pstdev(self.rr) if len(self.rr) >= 4 else None


class RingNotFound(RuntimeError):
    """Pierscien nie odpowiedzial na skanowanie - moze byc chwilowe."""


async def find_device(address=None, name_prefix="R12", timeout=10.0):
    """
    Szuka pierscienia po adresie MAC albo po prefiksie nazwy.

    Rzuca RingNotFound zamiast konczyc proces, bo zaraz po rozlaczeniu
    pierscien bywa niewidoczny przez kilka sekund - petla laczaca w
    ring_live.py ma wtedy sprobowac ponownie, a nie umrzec.
    """
    if address:
        dev = await BleakScanner.find_device_by_address(address, timeout=timeout)
    else:
        up = name_prefix.upper()
        dev = await BleakScanner.find_device_by_filter(
            lambda d, ad: bool(d.name or ad.local_name)
            and up in (d.name or ad.local_name or "").upper(),
            timeout=timeout)
    if not dev:
        raise RingNotFound(
            "Nie znaleziono pierscienia. Telefon odlaczony? Pierscien naladowany?")
    return dev


async def subscribe(client: BleakClient, handler) -> str:
    """
    Subskrybuje oba kanaly notify i zwraca UUID charakterystyki do pisania.
    handler dostaje (source, bytes).
    """
    uuids = {ch.uuid.lower() for s in client.services for ch in s.characteristics}
    write_uuid = None
    if UART_NOTIFY in uuids:
        await client.start_notify(UART_NOTIFY, lambda _c, d: handler("uart", bytes(d)))
        write_uuid = UART_WRITE
    if V2_NOTIFY in uuids:
        await client.start_notify(V2_NOTIFY, lambda _c, d: handler("v2", bytes(d)))
        write_uuid = write_uuid or V2_WRITE
    if not write_uuid:
        sys.exit("Pierscien nie ma ani kanalu UART, ani V2 - nieznany protokol.")
    return write_uuid


async def send(client: BleakClient, write_uuid: str, pkt: bytes):
    await client.write_gatt_char(write_uuid, pkt, response=False)
