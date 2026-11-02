#!/usr/bin/env python3
"""
ring_live.py - strumien na zywo z pierscienia COLMI R12 do TouchDesignera (OSC).

Co wysyla przez OSC:
  /ring/acc       gx gy gz    - przyspieszenie w g
  /ring/mag       |v|         - modul wektora w g (wygodne do progowania w TD)
  /ring/tilt      pitch roll  - kat wychylenia w stopniach (z grawitacji)
  /ring/ppg       v           - surowa wartosc PPG
  /ring/spo2raw   v           - surowy kanal SpO2
  /ring/rr        ms          - odstep miedzy uderzeniami serca (2 Hz!)
  /ring/beat      n           - licznik uderzen; roscie co jedno uderzenie
  /ring/hr        bpm         - puls (mediana z ostatnich odstepow, stabilny)
  /ring/hr_inst   bpm         - puls z ostatniego odstepu (szarpie, ale natychmiast)
  /ring/hrv       ms          - HRV jako RMSSD
  /ring/hrv_sdnn  ms          - HRV jako SDNN
  /ring/spo2      %           - SpO2 (tryb 0x69 typ 3)
  /ring/battery   %           - poziom baterii
  /ring/steps     n           - licznik krokow
  /ring/calories  kcal        - kalorie
  /ring/distance  m           - dystans w metrach

Dodatkowo: zapis do CSV (z surowym hexem), podglad na zywo w terminalu
(bez zadnych zaleznosci) albo w matplotlib (--plot, jesli zainstalowany),
keepalive, watchdog strumienia i automatyczne ponowne laczenie.

Przyklady:
  python ring_live.py --address AA:BB:CC:DD:EE:FF --osc 127.0.0.1:9000
  python ring_live.py --address AA:BB:CC:DD:EE:FF --csv live.csv --hr-mode interleave
  python ring_live.py --address AA:BB:CC:DD:EE:FF --quiet --seconds 600

Wysyla do pierscienia tylko komendy potwierdzone na R12:
  A1 04 / A1 02  surowy strumien (akcelerometr, PPG, SpO2) - dziala, ~1 Hz
  0x69 / 0x6A    typ 5 lub 8: strumien odstepow R-R - dziala, 2 Hz
                 typ 1: jednorazowy puls, typ 3: SpO2
  0x03           bateria - dziala
  0x1E           ciagly puls - firmware R12 ODMAWIA (odpowiada 0x9E 0xEE),
                 zostawione tylko jako opcja --hr-mode realtime
Nigdy nie wysyla: 0x08 (wylaczenie), 0xFF (reset fabryczny), 0x01 (zegar)
ani niczego zwiazanego z firmware, OTA czy bootloaderem.

Kroki, kalorie i dystans przychodza same, bez zadnej komendy (0x73 0x12).
"""

import argparse
import asyncio
import collections
import csv
import math
import os
import statistics as st
import sys
import time

from bleak import BleakClient

import ring_proto as rp

# Ponizej tej czestotliwosci PPG nie da sie wyliczyc pulsu z przebiegu
# (tetno to 0.7-3.5 Hz, wiec Nyquist wymaga co najmniej ~7 Hz, z zapasem 8).
MIN_PPG_HZ = 8.0


class PpgHeartRate:
    """
    Puls z surowego PPG: filtr pasmowy 0.7-3.5 Hz + detekcja szczytow.

    Filtr jest zlozony z czlonow jednobiegunowych (bez scipy ani numpy):
    wolny dolnoprzepustowy 0.7 Hz odejmowany od sygnalu daje gorna
    przepustowosc, a kaskada LP_POLES czlonow 3.5 Hz obciera szum. Szczyt
    liczy sie, gdy probka jest lokalnym maksimum powyzej progu i minal czas
    refrakcji; bpm to mediana ostatnich odstepow.

    LP_POLES i THR_FACTOR dobrane sweepem na sygnale syntetycznym (sinus
    tetna + dryf linii bazowej 0.05 Hz + szum gaussowski). Jeden biegun
    gubil sie przy szumie (blad do 67%); trzy daja blad <= 2.6% dla
    48-140 bpm, takze przy szumie rzedu polowy amplitudy sygnalu.

    UWAGA: stock firmware R12 podaje PPG z czestotliwoscia ~1 Hz, czyli
    ponizej MIN_PPG_HZ. Wtedy ta klasa swiadomie nic nie zwraca i ustawia
    .blocked_reason zamiast podawac wymyslona liczbe. Kod zadziala, jesli
    pierscien kiedys bedzie dawal szybszy strumien.
    """

    F_LOW = 0.7
    F_HIGH = 3.5
    LP_POLES = 3
    THR_FACTOR = 0.7
    BPM_MIN, BPM_MAX = 40, 200

    def __init__(self):
        self.times = collections.deque(maxlen=64)
        self.slow = None                    # dolnoprzepustowy 0.7 Hz (linia bazowa)
        self.lp = [None] * self.LP_POLES    # kaskada dolnoprzepustowa 3.5 Hz
        self.prev = None                    # poprzednia probka po filtrze
        self.rising = False
        self.last_peak_t = None
        self.intervals = collections.deque(maxlen=8)
        self.amp = collections.deque(maxlen=48)
        self.bpm = None
        self.blocked_reason = None

    @property
    def rate_hz(self):
        if len(self.times) < 8:
            return None
        span = self.times[-1] - self.times[0]
        return (len(self.times) - 1) / span if span > 0 else None

    def add(self, t, value):
        """Dodaje probke PPG. Zwraca bpm albo None."""
        self.times.append(t)
        fs = self.rate_hz
        if fs is None:
            return None
        if fs < MIN_PPG_HZ:
            self.blocked_reason = (
                f"PPG ma tylko {fs:.1f} Hz, potrzebne >= {MIN_PPG_HZ:.0f} Hz")
            return None
        self.blocked_reason = None

        # filtr pasmowy
        a_slow = 1 - math.exp(-2 * math.pi * self.F_LOW / fs)
        a_fast = 1 - math.exp(-2 * math.pi * self.F_HIGH / fs)
        self.slow = value if self.slow is None else self.slow + a_slow * (value - self.slow)
        x = value - self.slow
        for i in range(self.LP_POLES):
            self.lp[i] = x if self.lp[i] is None else self.lp[i] + a_fast * (x - self.lp[i])
            x = self.lp[i]

        self.amp.append(abs(x))
        if self.prev is None:
            self.prev = x
            return self.bpm

        # prog adaptacyjny od mediany amplitudy - odporniejszy na pojedyncze skoki
        thr = self.THR_FACTOR * st.median(self.amp) if len(self.amp) >= 8 else 0.0
        min_gap = 60.0 / self.BPM_MAX

        if x > self.prev:
            self.rising = True
        elif self.rising:
            # wlasnie minelo lokalne maksimum (self.prev)
            self.rising = False
            if self.prev > thr and thr > 0:
                if self.last_peak_t is None:
                    self.last_peak_t = t
                else:
                    gap = t - self.last_peak_t
                    if gap >= min_gap:
                        self.last_peak_t = t
                        if gap <= 60.0 / self.BPM_MIN:
                            self.intervals.append(gap)
                            if len(self.intervals) >= 3:
                                self.bpm = 60.0 / st.median(self.intervals)
        self.prev = x
        return self.bpm


class Sink:
    """Rozsyla probki: OSC + CSV + podglad."""

    def __init__(self, csv_path=None, osc=None, plot=False):
        self.t0 = time.perf_counter()
        self.csv_file = None
        self.writer = None
        if csv_path:
            self.csv_file = open(csv_path, "w", newline="", encoding="utf-8")
            self.writer = csv.writer(self.csv_file)
            self.writer.writerow(["t_iso", "t_s", "kind", "v1", "v2", "v3", "hex"])

        self.osc = None
        if osc:
            try:
                from pythonosc.udp_client import SimpleUDPClient
            except ImportError:
                sys.exit("Brak python-osc: pip install python-osc")
            host, port = osc.rsplit(":", 1)
            self.osc = SimpleUDPClient(host, int(port))
            print(f"OSC -> {host}:{port}")

        self.plot = None
        if plot:
            self.plot = _make_plot()

    def send_osc(self, path, values):
        if self.osc:
            self.osc.send_message(path, [float(v) for v in values])

    def log(self, kind, values, raw: bytes):
        if self.writer:
            vals = (list(values) + ["", "", ""])[:3]
            self.writer.writerow([rp.now_iso(), f"{time.perf_counter() - self.t0:.3f}",
                                  kind, *vals, raw.hex(" ")])

    def close(self):
        if self.csv_file:
            self.csv_file.close()


def _make_plot():
    """Zwraca funkcje aktualizujaca wykres matplotlib albo None, gdy brak biblioteki."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib nie jest zainstalowany - podglad tylko w terminalu.")
        return None

    plt.ion()
    fig, (ax_a, ax_p) = plt.subplots(2, 1, figsize=(9, 6))
    buf_t, buf_x, buf_y, buf_z, buf_pt, buf_p = ([] for _ in range(6))
    lines = [ax_a.plot([], [], label=n)[0] for n in ("x", "y", "z")]
    ax_a.set_ylabel("g")
    ax_a.set_ylim(-2, 2)
    ax_a.legend(loc="upper right")
    line_p, = ax_p.plot([], [], color="crimson")
    ax_p.set_ylabel("PPG")
    ax_p.set_xlabel("s")

    def update(kind, t, values):
        if kind == "acc":
            buf_t.append(t); buf_x.append(values[0])
            buf_y.append(values[1]); buf_z.append(values[2])
            for buf in (buf_t, buf_x, buf_y, buf_z):
                del buf[:-300]
            for ln, data in zip(lines, (buf_x, buf_y, buf_z)):
                ln.set_data(buf_t, data)
            ax_a.set_xlim(max(0, buf_t[-1] - 30), buf_t[-1] + 1)
        elif kind == "ppg":
            buf_pt.append(t); buf_p.append(values[0])
            del buf_pt[:-300]; del buf_p[:-300]
            line_p.set_data(buf_pt, buf_p)
            ax_p.set_xlim(max(0, buf_pt[-1] - 30), buf_pt[-1] + 1)
            ax_p.set_ylim(min(buf_p) - 5, max(buf_p) + 5)
        fig.canvas.draw_idle()
        fig.canvas.flush_events()

    return update


class RingLive:
    def __init__(self, args, sink: Sink):
        self.args = args
        self.sink = sink
        self.hr_est = PpgHeartRate()
        self.state = {"gx": 0.0, "gy": 0.0, "gz": 0.0, "mag": 0.0,
                      "ppg": None, "hr": None, "hr_src": "-", "hr_note": "",
                      "battery": None, "steps": None}
        # None = jeszcze nic nie przyszlo w tej sesji, wiec nie ma od czego
        # liczyc przerwy (inaczej czas laczenia liczylby sie jako urwanie)
        self.last_packet_t = None
        self.last_acc_t = time.perf_counter()
        self.n_packets = 0
        self.n_reconnects = 0
        self.gaps = []
        self.hr_value = None     # ustawiane przez handler w trybie interleave
        self.raw_on = False
        self.rr = rp.RrTracker()

    # --- odbior pakietow ---
    def handle(self, _source, d: bytes):
        parsed = rp.parse_packet(d)
        if not parsed:
            return
        kind, data = parsed
        now = time.perf_counter()
        t = now - self.sink.t0

        if self.last_packet_t is not None:
            gap = now - self.last_packet_t
            if gap > self.args.gap_warn:
                self.gaps.append((t, gap))
        self.last_packet_t = now
        self.n_packets += 1

        if kind == "acc":
            self.last_acc_t = now
            gx, gy, gz = data["gx"], data["gy"], data["gz"]
            mag = math.sqrt(gx * gx + gy * gy + gz * gz)
            self.state.update(gx=gx, gy=gy, gz=gz, mag=mag)
            self.sink.send_osc("/ring/acc", (gx, gy, gz))
            self.sink.send_osc("/ring/mag", (mag,))
            # Kat wychylenia z wektora grawitacji. Wazny tylko wtedy, gdy
            # pierscien sie nie rozpedza (|v| bliskie 1 g) - przy szarpnieciu
            # grawitacji nie da sie odroznic od ruchu. Przypisanie osi do
            # palca jest umowne, bo nie wiadomo, jak czujnik lezy w obudowie.
            pitch = math.degrees(math.atan2(-gx, math.hypot(gy, gz)))
            roll = math.degrees(math.atan2(gy, gz))
            self.sink.send_osc("/ring/tilt", (pitch, roll))
            self.sink.log("acc", (f"{gx:.4f}", f"{gy:.4f}", f"{gz:.4f}"), d)
            if self.sink.plot:
                self.sink.plot("acc", t, (gx, gy, gz))

        elif kind == "ppg":
            v = data["ppg"]
            self.state["ppg"] = v
            self.sink.send_osc("/ring/ppg", (v,))
            self.sink.log("ppg", (v, data["f1"], data["f2"]), d)
            bpm = self.hr_est.add(now, v)
            if bpm and self.args.hr_mode == "ppg":
                self._set_hr(bpm, "ppg")
            if self.sink.plot:
                self.sink.plot("ppg", t, (v,))

        elif kind == "spo2raw":
            self.sink.send_osc("/ring/spo2raw", (data["v"],))
            self.sink.log("spo2raw", (data["v"], data["f1"], data["f2"]), d)

        elif kind == "rr":
            # Odstep miedzy uderzeniami serca. Jedyny kanal powyzej 1 Hz:
            # pierscien nadaje 2 razy na sekunde, a RrTracker odrzuca
            # powtorzenia, zeby jedno uderzenie policzylo sie raz.
            fresh = self.rr.add(t, data["rr"])
            self.sink.send_osc("/ring/rr", (data["rr"],))
            if fresh:
                self.sink.send_osc("/ring/beat", (self.rr.beats,))
                if self.rr.bpm:
                    self._set_hr(self.rr.bpm, "R-R " + data["src"])
                    self.sink.send_osc("/ring/hr_inst", (self.rr.bpm_inst,))
                if self.rr.rmssd is not None:
                    self.state["rmssd"] = self.rr.rmssd
                    self.sink.send_osc("/ring/hrv", (self.rr.rmssd,))
                    self.sink.send_osc("/ring/hrv_sdnn", (self.rr.sdnn,))
            self.sink.log("rr", (data["rr"], data["bpm"], 1 if fresh else 0), d)

        elif kind == "nak":
            # Pierscien odmowil wykonania komendy (odpowiedz 0xEE).
            note = f"komenda 0x{data['cmd']:02x} nieobslugiwana"
            if note != self.state.get("hr_note"):
                print(os.linesep + note + " - to firmware jej nie zna.")
            self.state["hr_note"] = note
            self.sink.log("nak", (data["cmd"],), d)

        elif kind in ("spo2", "hrv", "stress"):
            self.sink.send_osc(f"/ring/{kind}", (data["v"],))
            self.sink.log(kind, (data["v"],), d)

        elif kind == "hr":
            self.hr_value = data["v"]
            self._set_hr(data["v"],
                         "0x1e" if self.args.hr_mode == "realtime" else "0x69")
            self.sink.log("hr", (data["v"],), d)

        elif kind == "hr_err":
            self.state["hr_note"] = f"blad 0x{data['err']:02x}"
            self.sink.log("hr_err", (data["err"],), d)

        elif kind == "hr_wait":
            self.state["hr_note"] = "mierzy..."

        elif kind in ("battery", "battery_hint"):
            self.state["battery"] = data["level"]
            self.sink.send_osc("/ring/battery", (data["level"],))
            self.sink.log(kind, (data["level"],), d)

        elif kind == "steps":
            self.state["steps"] = data["steps"]
            self.sink.send_osc("/ring/steps", (data["steps"],))
            self.sink.send_osc("/ring/calories", (data["calories"],))
            self.sink.send_osc("/ring/distance", (data["distance_m"],))
            self.sink.log("steps", (data["steps"], data["calories"],
                                    data["distance_m"]), d)

        else:
            self.sink.log(kind, (), d)

    def _set_hr(self, bpm, src):
        self.state["hr"] = bpm
        self.state["hr_src"] = src
        self.state["hr_note"] = ""
        self.sink.send_osc("/ring/hr", (bpm,))

    # --- sterowanie pierscieniem ---
    async def _raw(self, client, write_uuid, on: bool):
        await rp.send(client, write_uuid,
                      rp.pkt_raw_enable() if on else rp.pkt_raw_disable())
        self.raw_on = on

    async def _poller(self, client, write_uuid, hz):
        """
        Odpytuje pierscien o surowa probke tak czesto, jak sie da.

        Pierscien sam z siebie nadaje ~1 Hz, ale odpowiada na kazde wyslane
        A1 04, wiec odpytywaniem da sie dostac wiecej probek.

        UWAGA na pulapke: liczba ODEBRANYCH pakietow rosnie az do ~25 Hz, ale
        to w duzej czesci duplikaty tej samej probki. Liczy sie, jak czesto
        wartosc faktycznie sie ZMIENIA. Zmierzone na R12 przy ciaglym ruchu
        reki (zeby powtorzenia nie udawaly braku odswiezenia):

            bez pytania   1.0 Hz realnych odswiezen, PPG zyje
            pytanie 5 Hz  2.6 Hz                     PPG zyje
            pytanie 10 Hz 4.1 Hz                     PPG zyje
            pytanie 20 Hz 0.0 Hz                     PPG martwe

        Powyzej 10 Hz czujnik nie przyspiesza, tylko ZASTYGA - odpytywanie
        przerywa mu cykl pomiarowy. Dlatego 10 Hz to zmierzone optimum,
        a nie "im wiecej, tym lepiej".

        Skutek uboczny: bateria schodzi szybciej niz przy 1 Hz.
        """
        interval = 1.0 / hz
        try:
            while True:
                if self.raw_on:
                    try:
                        await rp.send(client, write_uuid, rp.pkt_raw_enable())
                    except Exception:
                        return
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            pass

    async def hr_realtime(self, client, write_uuid, on: bool):
        """
        Ciagly puls komenda 0x1E - pierscien sam nadaje bpm mniej wiecej raz
        na sekunde. Pomiar gasnie po 60 s, wiec sesja odswieza go przez
        RT2_CONTINUE (patrz petla w session).
        """
        await rp.send(client, write_uuid,
                      rp.pkt_hr_rt(rp.RT2_ENABLE if on else rp.RT2_DISABLE))

    async def measure_hr(self, client, write_uuid):
        """
        Jednorazowy pomiar pulsu komenda 0x69 ("manual heart rate").

        Strumien A1 jest na ten czas wylaczany, bo oba korzystaja z czujnika
        PPG. Uwaga: blad 0x01 w odpowiedzi nie oznacza konfliktu komend -
        wg Gadgetbridge to "pierscien zalozony nieprawidlowo", wiec najpierw
        warto docisnac pierscien na palcu.
        """
        was_on = self.raw_on
        if was_on:
            await self._raw(client, write_uuid, False)
            await asyncio.sleep(0.5)

        self.hr_value = None
        self.state["hr_note"] = "mierzy..."
        await rp.send(client, write_uuid, rp.pkt_rt_start(rp.RT_HEART_RATE))
        t_end = time.monotonic() + self.args.hr_window
        last_ka = time.monotonic()
        try:
            while time.monotonic() < t_end and self.hr_value is None:
                await asyncio.sleep(0.3)
                if time.monotonic() - last_ka > 8:
                    await rp.send(client, write_uuid, rp.pkt_rt_continue(rp.RT_HEART_RATE))
                    last_ka = time.monotonic()
        finally:
            try:
                await rp.send(client, write_uuid, rp.pkt_rt_stop(rp.RT_HEART_RATE))
            except Exception:
                pass
            await asyncio.sleep(0.3)
            if was_on:
                await self._raw(client, write_uuid, True)

        if self.hr_value is None and not self.state["hr_note"].startswith("blad"):
            self.state["hr_note"] = "brak odczytu"

    async def beats_window(self, client, write_uuid):
        """
        Okienko na puls i HRV: wylacza A1 i zbiera odstepy R-R, potem wraca
        do strumienia ruchu.

        Dlaczego tak, a nie oba naraz: pomierzone na R12. Przy wlaczonym A1
        strumien odstepow chodzi w pelnym tempie 2 Hz, ale kazdy odczyt ma
        wartosc 0 - wewnetrzny detektor uderzen nie dziala, bo czujnik PPG
        jest w trybie surowym. Bez A1 ten sam pierscien, ta sama reka i ten
        sam kontakt daly 30 uderzen w 35 s.

        Kluczowy szczegol: samo wylaczenie A1 NIE wystarcza. Detektor uzbraja
        sie dopiero na swieza komende start - w tescie z przelaczaniem A1
        okno z wylaczonym A1, ale odswiezane tylko przez "continue", dalo
        zero uderzen przy nieruchomej rece. Dlatego tu zawsze jest pelny
        cykl stop -> start, a nie continue.
        """
        was_on = self.raw_on
        if was_on:
            await self._raw(client, write_uuid, False)
            await asyncio.sleep(0.6)

        typ = self.args.beats_type
        # Pelny restart pomiaru, zeby detektor uderzen na pewno sie uzbroil.
        try:
            await rp.send(client, write_uuid, rp.pkt_rt_stop(typ))
            await asyncio.sleep(0.4)
        except Exception:
            pass
        beats0 = self.rr.beats
        self.state["hr_note"] = "zbieram uderzenia..."
        await rp.send(client, write_uuid, rp.pkt_rt_start(typ))

        t_end = time.monotonic() + self.args.beats_window
        last_ka = time.monotonic()
        try:
            while time.monotonic() < t_end:
                await asyncio.sleep(0.25)
                if time.monotonic() - last_ka > 20:
                    await rp.send(client, write_uuid, rp.pkt_rt_continue(typ))
                    last_ka = time.monotonic()
        finally:
            try:
                await rp.send(client, write_uuid, rp.pkt_rt_stop(typ))
                await asyncio.sleep(0.3)
            except Exception:
                pass
            if was_on:
                await self._raw(client, write_uuid, True)

        nowe = self.rr.beats - beats0
        if nowe:
            self.state["hr_note"] = f"{nowe} uderzen"
        else:
            self.state["hr_note"] = "brak uderzen - docisnij pierscien"

    # --- jedna sesja polaczenia ---
    async def session(self, dev, t_end):
        async with BleakClient(dev) as client:
            print(f"\nPolaczono: {dev.name} {dev.address}")
            write_uuid = await rp.subscribe(client, self.handle)
            await rp.send(client, write_uuid, rp.packet(rp.CMD_BATTERY))
            await asyncio.sleep(0.4)
            await self._raw(client, write_uuid, True)

            if self.args.hr_mode == "realtime":
                await self.hr_realtime(client, write_uuid, True)
            # Tryb "beats" nie startuje tu nic: okienka na uderzenia odpala
            # petla nizej, bo kazde z nich musi wylaczyc A1 i zrobic pelny
            # restart pomiaru (patrz beats_window).

            # Odpytywanie zamiast czekania: bez niego pierscien daje ~1 Hz.
            poller = None
            if self.args.poll_hz > 0:
                poller = asyncio.create_task(
                    self._poller(client, write_uuid, self.args.poll_hz))

            self.last_packet_t = None
            self.last_acc_t = time.perf_counter()
            last_ka = last_hr = last_hr_ka = time.monotonic()
            # pierwszy pomiar pulsu po chwili, nie od razu
            if self.args.hr_mode == "interleave":
                last_hr = time.monotonic() - self.args.hr_every + 10

            while time.monotonic() < t_end:
                await asyncio.sleep(0.2)
                if not self.args.quiet:
                    self._draw_status()
                now = time.monotonic()

                # keepalive: odswiezamy A1 04, bo strumien potrafi zamilknac
                if self.raw_on and now - last_ka > self.args.keepalive:
                    await self._raw(client, write_uuid, True)
                    last_ka = now

                # watchdog: brak acc dluzej niz stream_timeout -> wlacz ponownie
                quiet = time.perf_counter() - self.last_acc_t
                if self.raw_on and quiet > self.args.stream_timeout:
                    print(f"\nStrumien milczy {quiet:.0f} s - wysylam A1 04 ponownie.")
                    await self._raw(client, write_uuid, True)
                    self.last_acc_t = time.perf_counter()
                    last_ka = now
                if quiet > self.args.stream_timeout * 3:
                    print(f"\nStrumien martwy {quiet:.0f} s - przelaczam polaczenie.")
                    return  # wyjscie z sesji -> petla zewnetrzna polaczy ponownie

                # ciagly puls gasnie po 60 s - odswiezamy z zapasem
                if self.args.hr_mode == "realtime" and now - last_hr_ka > 25:
                    await rp.send(client, write_uuid, rp.pkt_hr_rt(rp.RT2_CONTINUE))
                    last_hr_ka = now

                # okienko na puls i HRV - przerywa strumien ruchu na chwile
                if (self.args.hr_mode == "beats"
                        and now - last_hr > self.args.hr_every):
                    await self.beats_window(client, write_uuid)
                    last_hr = time.monotonic()
                    last_ka = time.monotonic()
                    self.last_acc_t = time.perf_counter()

                if (self.args.hr_mode == "interleave"
                        and now - last_hr > self.args.hr_every):
                    await self.measure_hr(client, write_uuid)
                    last_hr = time.monotonic()
                    last_ka = time.monotonic()

            if poller:
                poller.cancel()
                try:
                    await poller
                except asyncio.CancelledError:
                    pass
            try:
                if self.args.hr_mode == "realtime":
                    await self.hr_realtime(client, write_uuid, False)
                elif self.args.hr_mode == "beats":
                    # na wypadek przerwania w trakcie okienka
                    await rp.send(client, write_uuid, rp.pkt_rt_stop(self.args.beats_type))
                await self._raw(client, write_uuid, False)
                await asyncio.sleep(0.3)
            except Exception:
                pass

    def _draw_status(self):
        s = self.state
        bars = "#" * min(20, int(s["mag"] * 10))
        hr = f"{s['hr']:.0f}" if s["hr"] else "--"
        note = f" ({s['hr_note']})" if s["hr_note"] else ""
        ppg = s["ppg"] if s["ppg"] is not None else "--"
        bat = f"{s['battery']}%" if s["battery"] is not None else "--"
        steps = s["steps"] if s["steps"] is not None else "--"
        t = time.perf_counter() - self.sink.t0
        print(f"\r{t:7.1f}s  g:{s['gx']:+.2f} {s['gy']:+.2f} {s['gz']:+.2f} "
              f"|v|={s['mag']:.2f} {bars:<20} ppg={ppg:<6} hr={hr:>3}{note:<16} "
              f"bat={bat:<5} kroki={steps:<6} n={self.n_packets}",
              end="", flush=True)

    # --- petla z ponownym laczeniem ---
    async def run(self):
        t_end = time.monotonic() + self.args.seconds
        backoff = 2.0
        bylo_polaczenie = False
        nieudane = 0
        while time.monotonic() < t_end:
            try:
                dev = await rp.find_device(self.args.address, self.args.name)
                await self.session(dev, t_end)
                bylo_polaczenie = True
                nieudane = 0
                if time.monotonic() >= t_end:
                    break
            except rp.RingNotFound:
                nieudane += 1
                print("\nPierscien niewidoczny w skanowaniu.")
            except Exception as e:
                nieudane += 1
                print(f"\nPolaczenie padlo: {type(e).__name__}: {e}")
            if time.monotonic() >= t_end:
                break
            if not bylo_polaczenie and nieudane >= self.args.max_prob:
                self._poddaj_sie(nieudane)
                return
            self.n_reconnects += 1
            print(f"Ponowna proba za {backoff:.0f} s "
                  f"(nr {self.n_reconnects})...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 1.6, 20.0)

    def _poddaj_sie(self, prob):
        """
        Komunikat na wyjscie, gdy polaczenie nie udalo sie ANI RAZU.

        Bez tego program mielilby godzine (--seconds) napis 'Pierscien
        niewidoczny', a przyczyna jest prawie zawsze banalna. Po udanym
        polaczeniu program probuje dalej bez limitu, bo tam zrywanie
        polaczenia to normalne zycie BLE.
        """
        print()
        print('=' * 70)
        print(f'  NIE UDALO SIE POLACZYC ani razu ({prob} proby).')
        print('=' * 70)
        print()
        print('  Najczestsze przyczyny, w kolejnosci:')
        print()
        print('  1. Aplikacja QRing w telefonie trzyma pierscien.')
        print('     Pierscien przyjmuje JEDNO polaczenie naraz i telefon')
        print('     wygrywa. Zamknij aplikacje calkowicie, nie minimalizuj.')
        print('  2. Pierscien lezy na ladowarce - wtedy czesto nie')
        print('     rozglasza sie wcale. Zdejmij go z ladowarki.')
        print('  3. Pierscien zasnal po dluzszym bezruchu. Porusz nim.')
        print('  4. Bluetooth w komputerze wylaczony.')
        print()
        print('  Zeby zobaczyc, co komputer w ogole widzi, uruchom')
        print('  znajdz-pierscien.bat - nic nie wysyla do pierscienia.')
        print()

    def summary(self):
        dur = time.perf_counter() - self.sink.t0
        print("\n" + "=" * 70)
        # Przy zerze pakietow dalsze statystyki klamia: napis
        # 'brak przerw - strumien ciagly' przy zerowym strumieniu
        # brzmi jak sukces, a to byl brak polaczenia.
        if not self.n_packets:
            print(f'Czas: {dur:.1f} s - ani jednego pakietu, polaczenia nie bylo.')
            print('=' * 70)
            return
        print(f"Czas: {dur:.1f} s    pakietow: {self.n_packets} "
              f"({self.n_packets / dur:.2f}/s)    ponownych polaczen: {self.n_reconnects}")
        if self.gaps:
            print(f"Przerwy > {self.args.gap_warn} s: {len(self.gaps)}  "
                  f"najdluzsza {max(g for _t, g in self.gaps):.1f} s")
        else:
            print(f"Brak przerw dluzszych niz {self.args.gap_warn} s - strumien ciagly.")
        if self.hr_est.blocked_reason:
            print(f"Puls z PPG niedostepny: {self.hr_est.blocked_reason}")
        print("=" * 70)


def main():
    p = argparse.ArgumentParser(
        description="Strumien na zywo z pierscienia COLMI R12 -> OSC / CSV.")
    p.add_argument("--address", help="adres MAC pierscienia")
    p.add_argument("--name", default="R12", help="fragment nazwy, gdy brak --address")
    p.add_argument("--osc", help="host:port, np. 127.0.0.1:9000 (OSC In w TouchDesignerze)")
    p.add_argument("--csv", help="plik CSV na dane")
    p.add_argument("--seconds", type=float, default=3600, help="czas pracy (domyslnie 1 h)")
    p.add_argument("--plot", action="store_true", help="podglad w matplotlib, jesli dostepny")
    p.add_argument("--quiet", action="store_true", help="bez podgladu w terminalu")
    p.add_argument("--acc-scale", type=float, default=rp.ACC_COUNTS_PER_G,
                   help=f"jednostek na 1 g (domyslnie {rp.ACC_COUNTS_PER_G:.0f})")
    p.add_argument("--hr-mode",
                   choices=("off", "beats", "realtime", "interleave", "ppg"),
                   default="beats",
                   help="skad puls: beats = okienka na odstepy R-R 0x69 typ 5 "
                        "(2 Hz w okienku, puls + prawdziwe HRV, ZALECANE; "
                        "na czas okienka strumien ruchu jest przerywany, bo "
                        "przy A1 detektor uderzen nie dziala), "
                        "interleave = jednorazowy 0x69 typ 1 z przerwa w strumieniu, "
                        "realtime = ciagly 0x1E - NIE DZIALA na R12, firmware odmawia, "
                        "ppg = liczony z przebiegu PPG (za malo probek przy 1 Hz), "
                        "off = wcale")
    p.add_argument("--beats-window", type=float, default=25,
                   help="ile sekund zbierac uderzenia w jednym okienku "
                        "(25 s to zwykle ~30 uderzen, dosc na puls i RMSSD)")
    p.add_argument("--beats-type", type=lambda v: int(v, 0), default=rp.RT_HRV,
                   help="typ strumienia uderzen: 5 = HRV (domyslny), 8 = stres. "
                        "Oba oddaja te same odstepy R-R")
    p.add_argument("--hr-every", type=float, default=90, help="co ile sekund mierzyc puls")
    p.add_argument("--hr-window", type=float, default=40, help="ile czekac na odczyt pulsu")
    p.add_argument("--poll-hz", type=float, default=10,
                   help="ile razy na sekunde pytac pierscien o probke. "
                        "Zmierzone na R12 przy ruchu: bez pytania 1.0 Hz "
                        "realnych odswiezen, przy 5 Hz pytania 2.6 Hz, przy "
                        "10 Hz pytania 4.1 Hz i PPG dalej zyje. Powyzej 10 Hz "
                        "czujnik ZASTYGA - przy 20 Hz 0.0 Hz odswiezen i "
                        "martwe PPG. 0 = nie odpytuj wcale")
    p.add_argument("--keepalive", type=float, default=20, help="co ile odswiezac A1 04")
    p.add_argument("--stream-timeout", type=float, default=6,
                   help="po ilu sekundach ciszy wlaczyc strumien ponownie")
    p.add_argument("--gap-warn", type=float, default=3.0,
                   help="przerwa powyzej tylu sekund liczy sie jako urwanie")
    p.add_argument("--max-prob", type=int, default=5,
                   help="po ilu nieudanych probach zrezygnowac, gdy "
                        "polaczenie NIGDY sie nie udalo; po udanym "
                        "polaczeniu program probuje dalej bez limitu")
    args = p.parse_args()

    rp.ACC_COUNTS_PER_G = args.acc_scale
    sink = Sink(args.csv, args.osc, args.plot)
    live = RingLive(args, sink)
    try:
        asyncio.run(live.run())
    except KeyboardInterrupt:
        pass
    finally:
        live.summary()
        sink.close()
        if args.csv:
            print(f"Zapisano: {args.csv}")


if __name__ == "__main__":
    main()
