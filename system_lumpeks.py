import sqlite3
import os
from datetime import datetime
from google import genai

DOZWOLONE_SUROWCE = ['wełna', 'bawełna', 'jedwab', 'wiskoza', 'poliester', 'nylon', 'len']

def polacz_z_baza():
    polaczenie = sqlite3.connect('lumpeks.db')
    kursor = polaczenie.cursor()
    return polaczenie, kursor

def dodaj_ubranie():
    polaczenie, kursor = polacz_z_baza()
    print("\n=== DODAWANIE UBRANIA ZE SKŁADEM ===")
    opis = input("Podaj nazwę ubrania: ").strip()
    rozmiar = input("Podaj rozmiar (S, M, L, XL): ").strip().upper()
    cena = float(input("Podaj cenę w zł: "))
    sklad_tymczasowy = {}
    suma_procent = 0
    while suma_procent < 100:
        brakuje = 100 - suma_procent
        if len(sklad_tymczasowy) == len(DOZWOLONE_SUROWCE):
            print("BŁĄD LOGICZNY: Wykorzystano wszystkie surowce bez 100%. Reset.")
            sklad_tymczasowy = {}
            suma_procent = 0
            continue
        print(f"Pozostało: {brakuje}% | Skład: {sklad_tymczasowy}")
        surowiec = input(f"Surowiec ({', '.join(DOZWOLONE_SUROWCE)}): ").strip().lower()
        if surowiec not in DOZWOLONE_SUROWCE:
            print("BŁĄD: Nieznany surowiec.")
            continue
        procent = int(input(f"Procent {surowiec}: "))
        if procent <= 0 or suma_procent + procent > 100:
            print(f"BŁĄD: Podaj 1-{brakuje}%.")
        else:
            sklad_tymczasowy[surowiec] = sklad_tymczasowy.get(surowiec, 0) + procent
            suma_procent += procent
    kursor.execute("SELECT MAX(id_towaru) FROM towary")
    maks_id = kursor.fetchone()[0]
    nowe_id = 1 if maks_id is None else maks_id + 1
    kursor.execute("INSERT INTO towary (id_towaru, opis, rozmiar, cena, status) VALUES (?, ?, ?, ?, 'Dostępny')", (nowe_id, opis, rozmiar, cena))
    for s, p in sklad_tymczasowy.items():
        kursor.execute("INSERT INTO sklad_surowcowy (id_towaru, surowiec, procent) VALUES (?, ?, ?)", (nowe_id, s, p))
    polaczenie.commit()
    polaczenie.close()
    print(f"SUKCES! Zapisano '{opis}' (ID: {nowe_id}).")

def pokaz_magazyn():
    polaczenie, kursor = polacz_z_baza()
    kursor.execute("SELECT id_towaru, opis, rozmiar, cena, status FROM towary")
    suma = 0
    print("\n=== STAN MAGAZYNU ===")
    for id_t, opis, rozm, cena, stat in kursor.fetchall():
        kursor.execute("SELECT procent, surowiec FROM sklad_surowcowy WHERE id_towaru = ?", (id_t,))
        sklad = ", ".join([f"{p}% {s}" for p, s in kursor.fetchall()]) or "brak metki"
        print(f"[{id_t}] {opis} ({rozm}) | {cena} zł | {stat} | Skład: {sklad}")
        if stat == 'Dostępny': suma += cena
    print(f"WARTOŚĆ DOSTĘPNEGO TOWARU: {suma} zł")
    polaczenie.close()

def szukaj_po_surowcu():
    polaczenie, kursor = polacz_z_baza()
    szukany = input("Szukany surowiec: ").strip().lower()
    kursor.execute("SELECT t.id_towaru, t.opis, t.rozmiar, t.cena, t.status, s.procent FROM towary t JOIN sklad_surowcowy s ON t.id_towaru = s.id_towaru WHERE s.surowiec = ?", (szukany,))
    for id_t, opis, rozm, cena, stat, proc in kursor.fetchall():
        print(f"ID: {id_t} | {opis} ({rozm}) | {proc}% {szukany} | {cena} zł | [{stat}]")
    polaczenie.close()

def sprzedaj_ubranie():
    polaczenie, kursor = polacz_z_baza()
    id_s = int(input("ID sprzedawanego ubrania: "))
    kursor.execute("SELECT opis, cena, status FROM towary WHERE id_towaru = ?", (id_s,))
    towar = kursor.fetchone()
    if not towar or towar[2] != 'Dostępny':
        print("BŁĄD: Towar niedostępny lub nie istnieje.")
        polaczenie.close()
        return
    klient = input(f"Klient dla '{towar[0]}' ({towar[1]} zł): ").strip()
    dzisiaj = datetime.now().strftime("%Y-%m-%d")
    kursor.execute("SELECT MAX(id_zamowienia) FROM zamowienia")
    maks_z = kursor.fetchone()[0]
    nowe_z = 1001 if maks_z is None else maks_z + 1
    kursor.execute("UPDATE towary SET status = 'Sprzedany' WHERE id_towaru = ?", (id_s,))
    kursor.execute("INSERT INTO zamowienia (id_zamowienia, id_towaru, data_zakupu, klient) VALUES (?, ?, ?, ?)", (nowe_z, id_s, dzisiaj, klient))
    polaczenie.commit()
    polaczenie.close()
    print(f"ZAKSIĘGOWANO! Zamówienie #{nowe_z}")

def raport_sprzedazy():
    polaczenie, kursor = polacz_z_baza()
    kursor.execute("SELECT z.id_zamowienia, z.data_zakupu, z.klient, t.opis, t.cena FROM zamowienia z JOIN towary t ON z.id_towaru = t.id_towaru")
    utarg = 0
    for id_z, data, klient, opis, cena in kursor.fetchall():
        print(f"#{id_z} ({data}) | {klient} | {opis} | {cena} zł")
        utarg += cena
    print(f"ŁĄCZNY UTARG: {utarg} zł")
    polaczenie.close()

def generuj_opis_ai():
    polaczenie, kursor = polacz_z_baza()
    if os.path.exists("klucz_ai.txt"):
        klucz_api = open("klucz_ai.txt").read().strip()
    else:
        klucz_api = input("Wklej klucz API z Google AI Studio: ").strip()
        open("klucz_ai.txt", "w").write(klucz_api)
    id_t = int(input("Podaj ID ubrania do opisu AI: "))
    kursor.execute("SELECT opis, rozmiar, cena FROM towary WHERE id_towaru = ?", (id_t,))
    towar = kursor.fetchone()
    if not towar:
        print("Brak towaru.")
        return
    kursor.execute("SELECT procent, surowiec FROM sklad_surowcowy WHERE id_towaru = ?", (id_t,))
    sklad = ", ".join([f"{p}% {s}" for p, s in kursor.fetchall()]) or "brak metki"
    print("Łączę z Gemini AI...")
    klient_ai = genai.Client(api_key=klucz_api)
    prompt = f"Napisz krótki, chwytliwy opis na Vinted po polsku: {towar[0]}, rozmiar {towar[1]}, skład: {sklad}, cena {towar[2]} zł. Dodaj 3 hashtagi."
    odp = klient_ai.models.generate_content(model='gemini-3.5-flash-lite', contents=prompt)
    print("\n=== OPIS AI ===\n" + odp.text + "\n===============")
    polaczenie.close()

while True:
    print("\n1. Dodaj | 2. Magazyn | 3. Szukaj surowca | 4. Sprzedaj | 5. Utarg | 6. Opis AI | 7. Wyjdź")
    w = input("Wybierz (1-7): ").strip()
    if w == '1': dodaj_ubranie()
    elif w == '2': pokaz_magazyn()
    elif w == '3': szukaj_po_surowcu()
    elif w == '4': sprzedaj_ubranie()
    elif w == '5': raport_sprzedazy()
    elif w == '6': generuj_opis_ai()
    elif w == '7': break
