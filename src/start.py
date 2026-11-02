#!/usr/bin/env python3
"""
start.py - jedno wejscie dla studenta: czyta ustawienia.txt z korzenia
paczki i odpala strumien z pierscienia do TouchDesignera.

Nie trzeba go uruchamiac recznie - robi to URUCHOM.bat. Samodzielnie
przydaje sie tylko wtedy, gdy ktos chce podmienic ustawienie z linii
polecen, np.:
    URUCHOM.bat --osc 192.168.1.50:9000 --seconds 300
Argumenty podane w linii polecen maja pierwszenstwo nad ustawienia.txt.
"""

import os
import subprocess
import sys

TU = os.path.dirname(os.path.abspath(__file__))        # .../src
KORZEN = os.path.dirname(TU)                           # korzen paczki
PLIK_USTAWIEN = os.path.join(KORZEN, "ustawienia.txt")

DOMYSLNE = {
    "adres": "",
    "nazwa": "R12",
    "osc": "127.0.0.1:9000",
    "czas_minut": "60",
    "poll_hz": "10",
    "puls": "beats",
    "puls_co_sekund": "90",
    "csv": "dane_z_pierscienia.csv",
}

TRYBY_PULSU = ("off", "beats", "realtime", "interleave", "ppg")


def czytaj_ustawienia(sciezka):
    """Prosty parser 'nazwa = wartosc'. Nieznane klucze zglasza, nie milczy."""
    u = dict(DOMYSLNE)
    if not os.path.exists(sciezka):
        print("Nie ma pliku ustawienia.txt - jada wartosci domyslne.")
        return u
    # utf-8-sig, nie utf-8: Notatnik zapisuje plik z BOM-em, a wtedy
    # pierwsza linia zaczyna sie od niewidzialnego znaku i parser
    # zglaszalby ja jako bledna.
    with open(sciezka, encoding="utf-8-sig") as f:
        for nr, linia in enumerate(f, 1):
            linia = linia.split("#", 1)[0].strip()
            if not linia:
                continue
            if "=" not in linia:
                print(f"  ustawienia.txt linia {nr}: pomijam '{linia}' (brak znaku =)")
                continue
            k, v = linia.split("=", 1)
            k, v = k.strip().lower(), v.strip()
            if k not in DOMYSLNE:
                print(f"  ustawienia.txt linia {nr}: nieznane ustawienie '{k}' - pomijam")
                continue
            u[k] = v
    return u


def licz(wartosc, nazwa, domyslna):
    try:
        return float(wartosc)
    except ValueError:
        print(f"  '{nazwa} = {wartosc}' to nie liczba - biore {domyslna}")
        return float(domyslna)


def naglowek(u):
    print()
    print("=" * 70)
    print("  PIERSCIEN COLMI R12  ->  TOUCHDESIGNER")
    print("=" * 70)
    print()
    print("  CO ZROBIC TERAZ, zanim ruszy pomiar:")
    print()
    print("  1. Zaloz pierscien na palec. Czujnik (dwie diody) ma dotykac")
    print("     skory po WEWNETRZNEJ stronie palca.")
    print("  2. Dosun go tak, zeby nie obracal sie luzno. Luzny pierscien")
    print("     daje ruch, ale nie da pulsu.")
    print("  3. Zamknij aplikacje QRing w telefonie, jesli jest wlaczona.")
    print("     Pierscien przyjmuje tylko JEDNO polaczenie naraz.")
    print("  4. Otworz td\\RING_START.toe (albo wrzuc td\\ring_osc.tox do")
    print("     wlasnego projektu). Port w OSC In CHOP musi byc taki sam")
    print("     jak tutaj: " + (u["osc"] or "(OSC wylaczony)"))
    print()
    print("  Zatrzymanie programu: Ctrl+C w tym okienku.")
    print("=" * 70)
    print()
    # Bez tego naglowek wylatuje dopiero PO zakonczeniu pomiaru: stdout
    # jest buforowany, bo idzie do potoku, a nie wprost do konsoli.
    sys.stdout.flush()


def main():
    u = czytaj_ustawienia(PLIK_USTAWIEN)
    naglowek(u)

    cmd = [sys.executable, os.path.join(TU, "ring_live.py")]
    if u["adres"]:
        cmd += ["--address", u["adres"]]
    cmd += ["--name", u["nazwa"] or "R12"]
    if u["osc"]:
        cmd += ["--osc", u["osc"]]
    cmd += ["--seconds", str(licz(u["czas_minut"], "czas_minut", 60) * 60)]
    cmd += ["--poll-hz", str(licz(u["poll_hz"], "poll_hz", 10))]
    if u["puls"] not in TRYBY_PULSU:
        print(f"  'puls = {u['puls']}' nie jest znanym trybem - biore beats")
        u["puls"] = "beats"
    cmd += ["--hr-mode", u["puls"]]
    cmd += ["--hr-every", str(licz(u["puls_co_sekund"], "puls_co_sekund", 90))]
    if u["csv"]:
        # CSV lezy w korzeniu paczki, zeby student nie musial szukac go w src
        cmd += ["--csv", os.path.join(KORZEN, u["csv"])]
    # Argumenty z linii polecen dopisane na koncu - argparse bierze ostatni,
    # wiec nadpisuja to, co przyszlo z ustawienia.txt.
    cmd += sys.argv[1:]

    srodowisko = dict(os.environ, PYTHONIOENCODING="utf-8")
    try:
        return subprocess.call(cmd, cwd=KORZEN, env=srodowisko)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
