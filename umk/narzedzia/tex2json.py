#!/usr/bin/env python3
"""Eksport rozdzial.tex do JSON (wejście dla json2docx.js).

Tekst główny jest parsowany bezpośrednio ze źródła .tex. Treść przypisów,
bibliografii i źródeł tabel pochodzi z biblatex: kompilowany jest wariant
dokumentu (build/eksport.tex) z bardzo szeroką stroną, w którym kursywa
i granice przypisów są oznaczone znacznikami @@...@@, a następnie tekst
jest wyciągany z PDF przez pdftotext. Dzięki temu „Tamże”, „dz. cyt.”,
kolejność i formatowanie są identyczne jak w wersji PDF.

Użycie: python3 narzedzia/tex2json.py  (z katalogu projektu)
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "narzedzia" / "build"
SRC = ROOT / "rozdzial.tex"
OUT = BUILD / "rozdzial.json"

TEXT_WIDTH_CM = 16.0  # A4 minus 2 x 2,5 cm

INJECT = r"""
% ===== wariant do eksportu DOCX: znaczniki zamiast formatowania =====
\geometry{paperwidth=450cm,paperheight=120cm,margin=1cm}
\hyphenpenalty=10000 \exhyphenpenalty=10000
\renewcommand*{\mkbibemph}[1]{@@I@@#1@@/I@@}
\renewcommand{\emph}[1]{@@I@@#1@@/I@@}
\makeatletter
\renewcommand\@makefntext[1]{@@FN\@thefnmark{}@@#1@@END@@}
\makeatother
\renewcommand{\zrodlo}[1]{@@SRC@@#1@@END@@}
\defbibenvironment{bibliography}{\list{}{}}{\endlist}{\item @@BIB@@}
"""


# ---------------------------------------------------------------------
#  1. Przypisy, bibliografia i źródła tabel z biblatex
# ---------------------------------------------------------------------
def extract_from_biblatex(src_text):
    BUILD.mkdir(parents=True, exist_ok=True)
    tex = src_text.replace(r"\begin{document}", INJECT + r"\begin{document}", 1)
    tex = tex.replace(r"\printbibliography", r"\printbibliography" + "\n@@BIBEND@@\n", 1)
    (BUILD / "eksport.tex").write_text(tex)
    (BUILD / "bibliografia.bib").write_text((ROOT / "bibliografia.bib").read_text())

    def run(*cmd):
        r = subprocess.run(cmd, cwd=BUILD, capture_output=True)
        return r.returncode

    run("pdflatex", "-interaction=nonstopmode", "eksport")
    if run("biber", "eksport") != 0:
        sys.exit("biber: błąd (zob. narzedzia/build/eksport.blg)")
    run("pdflatex", "-interaction=nonstopmode", "eksport")
    run("pdflatex", "-interaction=nonstopmode", "eksport")
    log = (BUILD / "eksport.log").read_text(errors="replace")
    if re.search(r"^! ", log, re.M):
        sys.exit("pdflatex: błąd kompilacji (zob. narzedzia/build/eksport.log)")
    subprocess.run(["pdftotext", "-raw", "eksport.pdf", "eksport.txt"], cwd=BUILD, check=True)
    txt = (BUILD / "eksport.txt").read_text()

    fns = re.findall(r"@@FN(\d+)@@(.*?)@@END@@", txt, re.S)
    if [int(n) for n, _ in fns] != list(range(1, len(fns) + 1)):
        sys.exit("Nieciągła numeracja przypisów w eksporcie")
    footnotes = [marked_runs(x) for _, x in fns]
    sources = [marked_runs(x) for x in re.findall(r"@@SRC@@(.*?)@@END@@", txt, re.S)]
    bib_part = txt[txt.index("@@BIB@@"):txt.index("@@BIBEND@@")]
    bibliography = [marked_runs(x) for x in bib_part.split("@@BIB@@")[1:]]
    return footnotes, sources, bibliography


def marked_runs(s):
    """Tekst ze znacznikami @@I@@…@@/I@@ -> lista runów."""
    s = re.sub(r"\s+", " ", s).strip()
    s = s.replace(". . .", "…")
    for a, b in (("ﬁ", "fi"), ("ﬂ", "fl"), ("ﬀ", "ff"), ("ﬃ", "ffi"), ("ﬄ", "ffl")):
        s = s.replace(a, b)
    s = re.sub(r"\s+@@/I@@", "@@/I@@", s)
    runs, italic = [], False
    for part in re.split(r"(@@/?I@@)", s):
        if part == "@@I@@":
            italic = True
        elif part == "@@/I@@":
            italic = False
        elif part:
            runs.append({"t": part, "i": italic})
    return runs


# ---------------------------------------------------------------------
#  2. Parser tekstu głównego
# ---------------------------------------------------------------------
def strip_comments(s):
    return "\n".join(re.sub(r"(?<!\\)%.*$", "", line) for line in s.split("\n"))


def read_group(s, i, open_="{", close="}"):
    """s[i] == open_; zwraca (zawartość, indeks za zamknięciem)."""
    assert s[i] == open_, s[i:i + 30]
    depth, j = 0, i
    while j < len(s):
        c = s[j]
        if c == "\\":
            j += 2
            continue
        if c == open_:
            depth += 1
        elif c == close:
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    raise ValueError("Niedomknięta grupa: " + s[i:i + 40])


class Inline:
    """Zamiana fragmentu LaTeX na runy {t, i, b} oraz {fn: n}."""

    SIMPLE = {"ldots": "…", "%": "%", "$": "$", "&": "&", "#": "#", "_": "_",
              ",": "\u2009", " ": " "}

    def __init__(self, labels):
        self.labels = labels
        self.fn_count = 0

    def parse(self, s, italic=False, bold=False):
        runs = []

        def add(t):
            if not t:
                return
            if runs and "t" in runs[-1] and runs[-1]["i"] == italic and runs[-1]["b"] == bold:
                runs[-1]["t"] += t
            else:
                runs.append({"t": t, "i": italic, "b": bold})

        i = 0
        while i < len(s):
            c = s[i]
            if c == "\\":
                m = re.match(r"\\([A-Za-z]+)\*?\s*|\\(.)", s[i:])
                name = m.group(1) or m.group(2)
                i += m.end()
                if name in self.SIMPLE:
                    add(self.SIMPLE[name])
                elif name == "\\":
                    runs.append({"br": True})
                elif name in ("emph", "textit"):
                    arg, i = read_group(s, i)
                    runs += self.parse(arg, not italic, bold)
                elif name == "textbf":
                    arg, i = read_group(s, i)
                    runs += self.parse(arg, italic, True)
                elif name == "enquote":
                    arg, i = read_group(s, i)
                    add("„")
                    runs += self.parse(arg, italic, bold)
                    add("”")
                elif name == "footcite":
                    if s[i] == "[":
                        _, i = read_group(s, i, "[", "]")
                    if s[i] == "[":
                        _, i = read_group(s, i, "[", "]")
                    _, i = read_group(s, i)
                    self.fn_count += 1
                    runs.append({"fn": self.fn_count})
                elif name == "ref":
                    arg, i = read_group(s, i)
                    add(str(self.labels[arg]))
                elif name == "label":
                    _, i = read_group(s, i)
                else:
                    raise ValueError(f"Nieobsługiwane polecenie \\{name} w: {s[max(0, i - 60):i + 20]!r}")
                continue
            if c in "{}":
                i += 1
                continue
            if c == "~":
                add("\u00a0")
                i += 1
                continue
            if s.startswith("---", i):
                add("—")
                i += 3
                continue
            if s.startswith("--", i):
                add("–")
                i += 2
                continue
            if c.isspace():
                if not (runs and "t" in runs[-1] and runs[-1]["t"].endswith(" ")):
                    add(" ")
                i += 1
                continue
            add(c)
            i += 1
        return runs


def trim(runs):
    """Usuwa skrajne spacje z listy runów."""
    if runs and "t" in runs[0]:
        runs[0]["t"] = runs[0]["t"].lstrip()
    if runs and "t" in runs[-1]:
        runs[-1]["t"] = runs[-1]["t"].rstrip()
    return [r for r in runs if not ("t" in r and r["t"] == "")]


def command_arg(s, name):
    m = re.search(r"\\" + name + r"\s*\{", s)
    arg, _ = read_group(s, m.end() - 1)
    return arg


def parse_table(body, inline, sources):
    caption = command_arg(body, "caption")
    m = re.search(r"\\begin\{tabularx\}\{[^}]*\}", body)
    spec, j = read_group(body, m.end())
    rows_src = body[j:body.index(r"\end{tabularx}")]
    rows_src = re.sub(r"\\(toprule|midrule|bottomrule)", "", rows_src)
    rows = []
    for row in re.split(r"\\\\", rows_src):
        if not row.strip():
            continue
        cells = re.split(r"(?<!\\)&", row)
        rows.append([trim(inline.parse(c)) for c in cells])
    # szerokości kolumn: P{x cm} / p{x cm} stałe, L/X dzielą resztę
    cols = re.findall(r"[Pp]\{([\d.]+)cm\}|([LX])", spec)
    fixed = sum(float(a) for a, _ in cols if a)
    n_flex = sum(1 for a, b in cols if b)
    widths = [float(a) if a else (TEXT_WIDTH_CM - fixed) / n_flex for a, _ in cols]
    return {
        "type": "table",
        "caption": trim(inline.parse(caption)),
        "widths_cm": widths,
        "header": rows[0],
        "rows": rows[1:],
        "source": sources.pop(0) if r"\zrodlo" in body else None,
    }


def parse_body(doc, inline, sources):
    blocks = []
    pattern = re.compile(
        r"\\(section|subsection)(\*?)\s*\{|\\begin\{(table|enumerate)\}|\\printbibliography")
    sec_no = 0
    pos = 0

    def flush(text):
        for para in re.split(r"\n\s*\n", text):
            if para.strip():
                blocks.append({"type": "para", "runs": trim(inline.parse(para))})

    while True:
        m = pattern.search(doc, pos)
        flush(doc[pos:m.start() if m else len(doc)])
        if not m:
            break
        if m.group(1):
            title, pos = read_group(doc, m.end() - 1)
            level = 1 if m.group(1) == "section" else 2
            numbered = level == 1 and not m.group(2)
            if numbered:
                sec_no += 1
            runs = trim(inline.parse(title))
            if numbered:
                runs.insert(0, {"t": f"{sec_no}. ", "i": False, "b": False})
            blocks.append({"type": "heading", "level": level, "runs": runs})
        elif m.group(3):
            env = m.group(3)
            end = doc.index(r"\end{" + env + "}", m.end())
            body = doc[m.end():end]
            pos = end + len(r"\end{" + env + "}")
            if env == "table":
                blocks.append(parse_table(body, inline, sources))
            else:
                items = [trim(inline.parse(x)) for x in re.split(r"\\item\b", body)[1:]]
                blocks.append({"type": "list", "items": items})
        else:
            blocks.append({"type": "bibliography"})
            pos = m.end()
    return blocks


def main():
    src_text = SRC.read_text()
    footnotes, sources, bibliography = extract_from_biblatex(src_text)

    doc = strip_comments(src_text)
    doc = doc[doc.index(r"\begin{document}") + len(r"\begin{document}"):doc.index(r"\end{document}")]

    # numery tabel/rysunków wg kolejności etykiet w środowiskach float
    labels, counters = {}, {"table": 0, "figure": 0}
    for env, body in re.findall(r"\\begin\{(table|figure)\}(.*?)\\end\{\1\}", doc, re.S):
        counters[env] += 1
        for lab in re.findall(r"\\label\{([^}]*)\}", body):
            labels[lab] = counters[env]
    inline = Inline(labels)

    meta = {
        "authors": trim(inline.parse(command_arg(doc, "autorzy"))),
        "affiliation": [trim(inline.parse(x)) for x in re.split(r"\\\\", command_arg(doc, "afiliacja"))],
        "titlePL": trim(inline.parse(command_arg(doc, "tytulPL"))),
        "titleEN": trim(inline.parse(command_arg(doc, "tytulEN"))),
    }

    abstracts = []
    for m in re.finditer(r"\\begin\{streszczenie\}\{([^}]*)\}\{([^}]*)\}(.*?)\\end\{streszczenie\}", doc, re.S):
        label, kw_label, body = m.groups()
        k = body.index(r"\slowakluczowe")
        kw, _ = read_group(body, body.index("{", k))
        abstracts.append({
            "label": label, "kwLabel": kw_label,
            "runs": trim(inline.parse(body[:k])),
            "kwRuns": trim(inline.parse(kw)),
        })

    start = doc.index(r"\end{streszczenie}", doc.rindex(r"\begin{streszczenie}"))
    rest = doc[start + len(r"\end{streszczenie}"):]
    # nota biograficzna: grupa {\footnotesize\setstretch{1} … \par}
    rest = re.sub(r"\{\\footnotesize\\setstretch\{1\}(.*?)\\par\s*\}", r"\1", rest, flags=re.S)
    blocks = parse_body(rest, inline, sources)

    if inline.fn_count != len(footnotes):
        sys.exit(f"Liczba \\footcite ({inline.fn_count}) ≠ liczba przypisów w PDF ({len(footnotes)})")

    data = {"meta": meta, "abstracts": abstracts, "blocks": blocks,
            "footnotes": footnotes, "bibliography": bibliography}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    print(f"{OUT.relative_to(ROOT)}: {len(blocks)} bloków, {len(footnotes)} przypisów, "
          f"{len(bibliography)} pozycji bibliografii")


if __name__ == "__main__":
    main()
