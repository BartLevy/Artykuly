#!/usr/bin/env python3
"""Angielska wersja artykułu: status tłumaczeń, kontrola zgodności, scalenie do main-en.tex i kompilacja.

Układ plików (katalog artykułu, domyślnie wyniki_naukowe/artykul):
  main.tex, sekcja-*.tex, suplement.tex   źródła polskie (edytowane ręcznie)
  en/<plik>.tex                           tłumaczenia tych plików (pisze je Claude, skill tlumaczenie-en)
  en/.zrodla/<plik>.tex                   kopia polskiego źródła, z którego powstało tłumaczenie
                                          (służy do wykrywania zmian i pokazywania diffu)
  definicje-en.tex, tabele/*-en.csv,      materiały angielskie generowane przez analiza_odpowiedzi_naukowa.py
  rysunki/*-en.pdf
  main-en.tex, suplement-en.tex           WYNIK: jeden plik na dokument (sekcje, definicje i tabele wstawione
                                          dosłownie; rysunki rysunki/*-en.pdf; bibliografia references.bib)

Polecenia:
  [--suplement] status [--diff]
                           stan tłumaczeń (NOWY / ZMIENIONY / AKTUALNY) i materiałów -en; --diff pokazuje zmiany
                           polskiego źródła od ostatniego tłumaczenia
  sprawdz [PLIK ...]       zgodność tłumaczenia ze źródłem: makra liczbowe, cytowania, etykiety, odsyłacze,
                           rysunki, tabele, środowiska
  zatwierdz PLIK ...       zapisuje bieżące polskie źródło jako podstawę tłumaczenia (po przetłumaczeniu pliku)
  buduj [--bez-kompilacji] [--wymus]
                           scala main-en.tex (i suplement-en.tex, jeśli istnieje en/suplement.tex) i kompiluje
"""

import argparse
import difflib
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

ARTYKUL = Path(__file__).resolve().parents[3] / "wyniki_naukowe" / "artykul"
DOKUMENTY = ["main.tex", "suplement.tex"]  # dokumenty główne; sekcje wynikają z \input w main.tex
SUPLEMENT = False  # suplement jest opcjonalny (--suplement), dopóki nie ma en/suplement.tex
NAGLOWEK = ("% Wygenerowano przez scal_en.py (skill tlumaczenie-en) z en/{zrodlo} i definicje-en.tex.\n"
            "% Plik jest NADPISYWANY: poprawki tłumaczenia wprowadzaj w en/*.tex, liczby w skrypcie analizy.\n")


# ------------------------------------------------------------------ narzędzia LaTeX

def bez_komentarzy(tekst, takze_koncowe=False):
    """Usuwa linie będące w całości komentarzem; opcjonalnie także komentarze końcowe (po niepoprzedzonym \\ %)."""
    wynik = []
    for linia in tekst.splitlines():
        if linia.lstrip().startswith("%"):
            continue
        if takze_koncowe:
            linia = re.sub(r"(?<!\\)%.*$", "", linia)
        wynik.append(linia)
    return "\n".join(wynik) + "\n"


def argument(tekst, i):
    """Zawartość argumentu {...} zaczynającego się na pozycji i oraz pozycja za nim."""
    if i >= len(tekst) or tekst[i] != "{":
        raise ValueError(f"oczekiwano '{{' na pozycji {i}: {tekst[i:i + 40]!r}")
    glebokosc = 0
    for j in range(i, len(tekst)):
        c = tekst[j]
        if c == "\\":
            continue
        if c == "{" and tekst[j - 1] != "\\":
            glebokosc += 1
        elif c == "}" and tekst[j - 1] != "\\":
            glebokosc -= 1
            if glebokosc == 0:
                return tekst[i + 1:j], j + 1
    raise ValueError(f"niezamknięty nawias od pozycji {i}")


def komorki(wiersz):
    """Dzieli wiersz CSV (separator ';') poza klamrami; zdejmuje klamry obejmujące całą komórkę."""
    wynik, biezaca, glebokosc, poprz = [], "", 0, ""
    for c in wiersz:
        if c == "{" and poprz != "\\":
            glebokosc += 1
        elif c == "}" and poprz != "\\":
            glebokosc -= 1
        if c == ";" and glebokosc == 0:
            wynik.append(biezaca)
            biezaca = ""
        else:
            biezaca += c
        poprz = c
    wynik.append(biezaca)
    out = []
    for k in wynik:
        k = k.strip()
        if k.startswith("{") and k.endswith("}"):
            try:
                srodek, koniec = argument(k, 0)
                if koniec == len(k):
                    k = srodek
            except ValueError:
                pass
        out.append(k)
    return out


def tabela(kolumny, plik):
    """Tabela booktabs z pliku CSV w formacie \\tabelacsv (pierwszy wiersz = nagłówek, prefiks \\midrule)."""
    wiersze = [w for w in plik.read_text(encoding="utf-8").splitlines() if w.strip()]
    linie = [f"\\begin{{tabular}}{{{kolumny}}}", "\\toprule", " & ".join(komorki(wiersze[0])) + " \\\\", "\\midrule"]
    for w in wiersze[1:]:
        k = komorki(w)
        if k[0].startswith("\\midrule"):
            linie.append("\\midrule")
            k[0] = k[0][len("\\midrule"):].strip()
        linie.append(" & ".join(k) + " \\\\")
    linie += ["\\bottomrule", "\\end{tabular}"]
    return "\n".join(linie)


def sekcje(main_tex):
    return [m + ("" if m.endswith(".tex") else ".tex")
            for m in re.findall(r"\\input\{(sekcja-[^}]+)\}", bez_komentarzy(main_tex))]


def pliki_zrodlowe(art):
    """main.tex i jego sekcje; suplement.tex tylko, gdy ma już tłumaczenie albo podano --suplement."""
    pliki = ["main.tex"] + sekcje((art / "main.tex").read_text(encoding="utf-8"))
    return pliki + [p for p in DOKUMENTY[1:] if (art / p).exists() and (SUPLEMENT or (art / "en" / p).exists())]


def makra_danych(art, nazwa="definicje.tex"):
    p = art / nazwa
    if not p.exists():
        return {}
    return dict(re.findall(r"^\\newcommand\{\\(\w+)\}\{(.*)\}$", p.read_text(encoding="utf-8"), re.M))


# ------------------------------------------------------------------ status

def stan(art, plik):
    en, kopia = art / "en" / plik, art / "en" / ".zrodla" / plik
    if not en.exists():
        return "NOWY"
    if not kopia.exists() or kopia.read_bytes() != (art / plik).read_bytes():
        return "ZMIENIONY"
    return "AKTUALNY"


def materialy_en(art):
    """Lista problemów z materiałami -en generowanymi przez skrypt analizy."""
    problemy = []
    pl, en = makra_danych(art), makra_danych(art, "definicje-en.tex")
    if not en:
        problemy.append("brak definicje-en.tex")
    elif set(pl) != set(en):
        problemy.append(f"definicje.tex i definicje-en.tex mają różne makra: {sorted(set(pl) ^ set(en))[:10]}")
    elif (art / "definicje.tex").stat().st_mtime > (art / "definicje-en.tex").stat().st_mtime + 60:
        problemy.append("definicje.tex jest nowszy niż definicje-en.tex")
    tekst = "".join(bez_komentarzy((art / p).read_text(encoding="utf-8")) for p in pliki_zrodlowe(art))
    for r in sorted(set(re.findall(r"\\FigDir\s*([\w-]+)", tekst))):
        if not (art / "rysunki" / f"{r}-en.pdf").exists():
            problemy.append(f"brak rysunki/{r}-en.pdf")
    for t in sorted(set(tabele_w(tekst))):
        if not (art / "tabele" / f"{t}-en.csv").exists():
            problemy.append(f"brak tabele/{t}-en.csv")
    return problemy


def tabele_w(tekst):
    nazwy, i = [], 0
    while (i := tekst.find("\\tabelacsv{", i)) >= 0:
        _, j = argument(tekst, i + len("\\tabelacsv"))
        nazwa, i = argument(tekst, j)
        nazwy.append(nazwa)
    return nazwy


def polecenie_status(art, args):
    print(f"Katalog artykułu: {art}")
    for p in pliki_zrodlowe(art):
        s = stan(art, p)
        print(f"  {s:10} {p}")
        if args.diff and s == "ZMIENIONY":
            kopia = art / "en" / ".zrodla" / p
            stare = kopia.read_text(encoding="utf-8").splitlines() if kopia.exists() else []
            nowe = (art / p).read_text(encoding="utf-8").splitlines()
            sys.stdout.writelines(l + "\n" for l in difflib.unified_diff(
                stare, nowe, f"en/.zrodla/{p} (podstawa tłumaczenia)", f"{p} (obecnie)", n=1, lineterm=""))
    problemy = materialy_en(art)
    print("Materiały -en (skrypt analizy): " + ("OK" if not problemy else "DO ODŚWIEŻENIA"))
    for pr in problemy:
        print(f"  - {pr}")


# ------------------------------------------------------------------ kontrola zgodności

def znaczniki(tekst, makra):
    t = bez_komentarzy(tekst, takze_koncowe=True)
    cyt = Counter(k.strip() for grupa in re.findall(r"\\cite[tp]?\*?(?:\[[^\]]*\])*\{([^}]*)\}", t)
                  for k in grupa.split(","))
    return {
        "makra liczbowe": Counter(m for m in re.findall(r"\\([A-Za-z]+)", t) if m in makra),
        "cytowania": cyt,
        "etykiety": Counter(re.findall(r"\\label\{([^}]*)\}", t)),
        "odsyłacze": Counter(re.findall(r"\\(?:eq|auto|page)?ref\{([^}]*)\}", t)),
        "rysunki": Counter(re.findall(r"\\FigDir\s*([\w-]+)", t)),
        "tabele CSV": Counter(tabele_w(t)),
        "środowiska": Counter(re.findall(r"\\begin\{(\w+\*?)\}", t)),
        "przypisy tabel": Counter({"uwagatabeli": t.count("\\uwagatabeli")}),
    }


def porownaj(art, plik, makra):
    pl = znaczniki((art / plik).read_text(encoding="utf-8"), makra)
    en = znaczniki((art / "en" / plik).read_text(encoding="utf-8"), makra)
    roznice = []
    for rodzaj in pl:
        a, b = pl[rodzaj], en[rodzaj]
        if set(a) != set(b):
            braki, nadmiar = sorted(set(a) - set(b)), sorted(set(b) - set(a))
            roznice.append(f"{rodzaj}: " + "; ".join(x for x in (
                f"brak w EN {braki}" if braki else "", f"tylko w EN {nadmiar}" if nadmiar else "") if x))
        elif rodzaj not in ("makra liczbowe", "cytowania", "odsyłacze") and a != b:
            # makra, cytowania i odsyłacze mogą wystąpić inną liczbę razy po przeredagowaniu zdania
            roznice.append(f"{rodzaj}: inna liczba wystąpień {dict(a)} -> {dict(b)}")
    return roznice


def polecenie_sprawdz(art, args):
    makra = makra_danych(art)
    pliki = args.pliki or [p for p in pliki_zrodlowe(art) if (art / "en" / p).exists()]
    bledy = 0
    for p in pliki:
        if not (art / "en" / p).exists():
            print(f"  BRAK       en/{p}")
            bledy += 1
            continue
        r = porownaj(art, p, makra)
        print(f"  {'OK' if not r else 'NIEZGODNY':10} {p}")
        for x in r:
            print(f"      {x}")
        bledy += bool(r)
    return 1 if bledy else 0


def polecenie_zatwierdz(art, args):
    (art / "en" / ".zrodla").mkdir(parents=True, exist_ok=True)
    makra = makra_danych(art)
    for p in args.pliki:
        if not (art / "en" / p).exists():
            sys.exit(f"Brak tłumaczenia en/{p}")
        shutil.copyfile(art / p, art / "en" / ".zrodla" / p)
        r = porownaj(art, p, makra)
        print(f"zatwierdzono {p}" + ("" if not r else " (UWAGA, niezgodności: " + " | ".join(r) + ")"))


# ------------------------------------------------------------------ scalanie i kompilacja

def wstaw_inputy(tekst, art, poziom=0):
    def zamien(m):
        nazwa = m.group(1).removesuffix(".tex")
        if nazwa == "definicje":
            plik = art / "definicje-en.tex"
        else:
            plik = art / "en" / f"{nazwa}.tex"
        if not plik.exists():
            raise FileNotFoundError(f"\\input{{{m.group(1)}}}: brak {plik.relative_to(art)}")
        wnetrze = plik.read_text(encoding="utf-8").rstrip("\n")
        return f"% ---- {plik.relative_to(art)}\n" + (wstaw_inputy(wnetrze, art, poziom + 1) if poziom < 3 else wnetrze)
    return re.sub(r"\\input\{([^}]+)\}", lambda m: zamien(m), tekst)


def rozwin_tabele(tekst, art):
    wynik, i = [], 0
    while (k := tekst.find("\\tabelacsv{", i)) >= 0:
        kolumny, j = argument(tekst, k + len("\\tabelacsv"))
        nazwa, j = argument(tekst, j)
        plik = art / "tabele" / f"{nazwa}-en.csv"
        if not plik.exists():
            raise FileNotFoundError(f"brak tabele/{nazwa}-en.csv (uruchom skrypt analizy)")
        wynik += [tekst[i:k], tabela(kolumny, plik)]
        i = j
    return "".join(wynik + [tekst[i:]])


def scal(art, dokument):
    zrodlo = art / "en" / dokument
    tekst = wstaw_inputy(zrodlo.read_text(encoding="utf-8"), art)
    tekst = bez_komentarzy(tekst)  # także nagłówki "% ----" i opisy z definicje-en.tex
    tekst = rozwin_tabele(tekst, art)
    tekst = re.sub(r"\\FigDir\s*([\w-]+)", lambda m: f"rysunki/{m.group(1)}-en", tekst)
    tekst = re.sub(r"(\\externaldocument(?:\[[^\]]*\])*)\{main\}", r"\1{main-en}", tekst)
    tekst = re.sub(r"\n{3,}", "\n\n", tekst)
    wynik = art / dokument.replace(".tex", "-en.tex")
    wynik.write_text(NAGLOWEK.format(zrodlo=dokument) + tekst, encoding="utf-8")
    return wynik


def kompiluj(art, plik):
    r = subprocess.run(["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", plik.name],
                       cwd=art, capture_output=True, text=True)
    log = (art / plik.with_suffix(".log").name)
    tresc = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    bledy = re.findall(r"^! .*", tresc, re.M)
    niezdef = sorted(set(re.findall(r"(?:Reference|Citation) `([^']+)' .*undefined", tresc)))
    makra = sorted(set(re.findall(r"^! Undefined control sequence.*\n.*?(\\\w+)\s*$", tresc, re.M)))
    overfull = len(re.findall(r"^Overfull \\hbox", tresc, re.M))
    print(f"  {plik.name}: " + ("OK" if r.returncode == 0 else f"BŁĄD kompilacji (kod {r.returncode})")
          + f", {plik.with_suffix('.pdf').name}")
    for b in bledy[:10]:
        print(f"      {b}")
    if makra:
        print(f"      niezdefiniowane polecenia: {makra}")
    if niezdef:
        print(f"      niezdefiniowane odsyłacze/cytowania: {niezdef}")
    if overfull:
        print(f"      Overfull \\hbox: {overfull}")
    return r.returncode


def polskie_znaki(plik):
    """Linie z polskimi znakami diakrytycznymi (poza autorami i afiliacjami) do przejrzenia."""
    out = []
    for n, linia in enumerate(plik.read_text(encoding="utf-8").splitlines(), 1):
        if re.search(r"[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]", linia) and not re.match(r"\s*(%|\\author|\\affil)", linia):
            out.append(f"      {plik.name}:{n}: {linia.strip()[:110]}")
    return out


def polecenie_buduj(art, args):
    pliki = pliki_zrodlowe(art)
    nieaktualne = [p for p in pliki if stan(art, p) != "AKTUALNY"]
    if nieaktualne and not args.wymus:
        sys.exit(f"Nieaktualne tłumaczenia: {nieaktualne}. Przetłumacz i zatwierdź je albo użyj --wymus.")
    problemy = materialy_en(art)
    if problemy:
        sys.exit("Materiały -en wymagają odświeżenia (uruchom skrypt analizy):\n  " + "\n  ".join(problemy))
    kod = 0
    for dok in DOKUMENTY:  # main przed suplementem: suplement czyta etykiety M- z main-en.aux
        if dok not in pliki:
            continue
        wynik = scal(art, dok)
        print(f"Zapisano {wynik}")
        if not args.bez_kompilacji:
            kod |= kompiluj(art, wynik)
        pz = polskie_znaki(wynik)
        if pz:
            print(f"    linie z polskimi znakami ({len(pz)}), sprawdź, czy to nazwy własne:")
            print("\n".join(pz[:30]))
    return kod


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--artykul", type=Path, default=ARTYKUL, help="katalog artykułu")
    ap.add_argument("--suplement", action="store_true", help="uwzględnij suplement.tex (suplement-en.tex)")
    sub = ap.add_subparsers(dest="polecenie", required=True)
    s = sub.add_parser("status"); s.add_argument("--diff", action="store_true")
    s = sub.add_parser("sprawdz"); s.add_argument("pliki", nargs="*")
    s = sub.add_parser("zatwierdz"); s.add_argument("pliki", nargs="+")
    s = sub.add_parser("buduj"); s.add_argument("--bez-kompilacji", action="store_true")
    s.add_argument("--wymus", action="store_true", help="buduj mimo nieaktualnych tłumaczeń")
    args = ap.parse_args()
    art = args.artykul.resolve()
    global SUPLEMENT
    SUPLEMENT = args.suplement
    akcje = {"status": polecenie_status, "sprawdz": polecenie_sprawdz, "zatwierdz": polecenie_zatwierdz,
             "buduj": polecenie_buduj}
    sys.exit(akcje[args.polecenie](art, args) or 0)


if __name__ == "__main__":
    main()
