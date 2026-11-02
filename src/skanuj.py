#!/usr/bin/env python3
"""
skanuj.py - pokazuje pierscienie widoczne w poblizu i ich adresy MAC.

Przydaje sie w dwoch sytuacjach:
  - gdy trzeba wpisac adres do ustawienia.txt (wiecej niz jeden pierscien
    w zasiegu, np. cala grupa na zajeciach),
  - gdy START.bat mowi, ze nie widzi pierscienia, i trzeba sprawdzic,
    czy Bluetooth w ogole go lapie.

Skanowanie jest BIERNE - tylko nasluchuje rozglaszania. Nie laczy sie
z pierscieniem i nie wysyla do niego ani jednej komendy.
"""

import argparse
import asyncio
import sys

from bleak import BleakScanner

# Nazwy, pod jakimi rozglaszaja sie pierscienie COLMI i pokrewne.
WZORCE = ("R12", "R02", "R03", "R04", "R06", "R10", "COLMI", "RING", "QRING")


async def main_async(sekund, wszystko):
    print(f"Skanuje {sekund:.0f} s... (Bluetooth musi byc wlaczony)")
    print("Poruszaj pierscieniem - po bezruchu rzadziej sie rozglasza.")
    print()
    znalezione = await BleakScanner.discover(timeout=sekund, return_adv=True)

    rows = []
    for adres, (dev, adv) in znalezione.items():
        nazwa = dev.name or adv.local_name or ""
        pasuje = any(w in nazwa.upper() for w in WZORCE)
        if pasuje or wszystko:
            rows.append((0 if pasuje else 1, -(adv.rssi or -999),
                         nazwa or "(bez nazwy)", adres, adv.rssi))
    rows.sort()

    if not rows:
        print("Nic nie znalazlem.")
        print()
        print("Co sprawdzic:")
        print("  - czy Bluetooth w komputerze jest wlaczony,")
        print("  - czy pierscien nie siedzi na ladowarce (wtedy czesto nie")
        print("    rozglasza sie wcale),")
        print("  - czy aplikacja QRing w telefonie nie trzyma polaczenia -")
        print("    pierscien przyjmuje tylko jedno naraz, zamknij aplikacje,")
        print("  - poruszaj pierscieniem; po dluzszym bezruchu zasypia.")
        print("  - uruchom ponownie z opcja --wszystko, zeby zobaczyc, czy")
        print("    Bluetooth widzi JAKIEKOLWIEK urzadzenia.")
        return 1

    print(f"{'nazwa':<24} {'adres MAC':<20} {'sila':>6}   odleglosc")
    print("-" * 70)
    for _, _, nazwa, adres, rssi in rows:
        if rssi is None:
            opis = "?"
        elif rssi > -60:
            opis = "bardzo blisko"
        elif rssi > -75:
            opis = "blisko"
        elif rssi > -88:
            opis = "daleko"
        else:
            opis = "na granicy zasiegu"
        print(f"{nazwa:<24} {adres:<20} {rssi if rssi is not None else 0:>4} dBm   {opis}")

    pierscienie = [r for r in rows if r[0] == 0]
    print()
    if len(pierscienie) == 1:
        print("Jeden pierscien w zasiegu - nie trzeba nic wpisywac do")
        print("ustawienia.txt, START.bat sam go znajdzie.")
    elif len(pierscienie) > 1:
        print(f"Widze {len(pierscienie)} pierscienie. Zeby program wiedzial,")
        print("ktory jest Twoj, wpisz jego adres do ustawienia.txt w linii:")
        print(f"    adres = {pierscienie[0][3]}")
        print("(ten z gory listy jest najblizej, czyli najpewniej na Twojej rece)")
    else:
        print("Zadne z tych urzadzen nie wyglada na pierscien. Jesli znasz")
        print("jego nazwe, wpisz jej fragment do ustawienia.txt w linii 'nazwa ='.")
    return 0


def main():
    p = argparse.ArgumentParser(description="Pokazuje pierscienie w poblizu.")
    # 12 s, nie mniej: po rozlaczeniu pierscien milczy kilka sekund,
    # zanim zacznie sie znowu rozglaszac. Przy 8 s wychodzilo "nic nie
    # znalazlem" mimo dzialajacego pierscienia.
    p.add_argument("--sekund", type=float, default=12.0)
    p.add_argument("--wszystko", action="store_true",
                   help="pokaz wszystkie urzadzenia BLE, nie tylko pierscienie")
    a = p.parse_args()
    try:
        return asyncio.run(main_async(a.sekund, a.wszystko))
    except KeyboardInterrupt:
        return 0
    except Exception as e:
        print()
        print(f"Skanowanie sie nie udalo: {type(e).__name__}: {e}")
        print("Najczestsza przyczyna: wylaczony Bluetooth w komputerze.")
        return 2


if __name__ == "__main__":
    sys.exit(main())
