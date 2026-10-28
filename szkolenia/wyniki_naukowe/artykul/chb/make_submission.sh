#!/usr/bin/env bash
# Builds the Computers in Human Behavior (Elsevier) submission package from manuscript.tex (elsarticle).
#
# CHB uses double-anonymized review: manuscript.tex contains no author details; they are only in
# title_page.tex. Elsevier requires all LaTeX files in ONE folder level, so the package is flat
# (Figure_1..N next to the manuscript). The package is compiled in place to prove it builds on its own,
# then checked against the Guide for Authors.
#
# Usage: ./make_submission.sh [output_dir]      (default: pakiet)

set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$(realpath -m "${1:-$SRC/pakiet}")"
WARN=0
warn() { echo "  WARNING: $*"; WARN=$((WARN + 1)); }

FILES=(manuscript.tex declarations.tex references.bib title_page.tex cover_letter.tex highlights.txt)
for f in "${FILES[@]}"; do [[ -f "$SRC/$f" ]] || { echo "ERROR: missing $SRC/$f"; exit 1; }; done

rm -rf "$OUT"
mkdir -p "$OUT"
echo "Building package in $OUT"
for f in "${FILES[@]}"; do cp "$SRC/$f" "$OUT/"; done
cp "$SRC"/Figure_* "$OUT/"
# highlights must be a separate editable file with "Highlights" in its name
pandoc -f markdown -t docx -o "$OUT/Highlights.docx" "$SRC/highlights.txt"

# --- compile -----------------------------------------------------------------------------------
echo "Compiling..."
(
    cd "$OUT"
    for doc in manuscript title_page cover_letter; do
        if ! latexmk -pdf -interaction=nonstopmode -halt-on-error "$doc.tex" > "$doc.build.log" 2>&1; then
            echo "ERROR: $doc.tex failed to compile, see $OUT/$doc.build.log"; exit 1
        fi
    done
    undefined=$(grep -c -E "(Reference|Citation).*undefined" manuscript.log || true)
    [[ "$undefined" == "0" ]] || echo "  WARNING: $undefined undefined references/citations in manuscript.log"
    # keep manuscript.bbl (Elsevier asks for it with the .tex); drop the rest of the build output
    latexmk -c > /dev/null 2>&1 || true
    rm -f ./*.build.log ./*.spl
)
[[ -f "$OUT/manuscript.bbl" ]] || warn "manuscript.bbl was not produced"

# --- checks against the Guide for Authors ------------------------------------------------------
echo "Checking Guide for Authors requirements..."

words=$(sed -n '/\\begin{abstract}/,/\\end{abstract}/p' "$OUT/manuscript.tex" | grep -v 'abstract}' \
        | sed -e 's/\\[a-zA-Z]*//g' -e 's/[{}]//g' | wc -w)
(( words <= 250 )) && echo "  abstract: $words words (limit 250)" || warn "abstract has $words words (limit 250)"

kw=$(sed -n '/\\begin{keyword}/,/\\end{keyword}/p' "$OUT/manuscript.tex" | grep -v 'keyword}' \
     | sed 's/\\sep/\n/g' | grep -c '[a-zA-Z]' || true)
(( kw >= 1 && kw <= 6 )) && echo "  keywords: $kw (maximum 6)" || warn "$kw keywords (maximum 6)"

hl=$(grep -c '^- ' "$OUT/highlights.txt" || true)
(( hl >= 3 && hl <= 5 )) && echo "  highlights: $hl bullets (3-5)" || warn "$hl highlights (allowed 3-5)"
while IFS= read -r line; do
    text="${line#- }"
    len=$(printf '%s' "$text" | wc -m)
    (( len <= 85 )) || warn "highlight longer than 85 characters ($len): $text"
done < <(grep '^- ' "$OUT/highlights.txt")

body=$(sed -n '/\\begin{document}/,/\\end{document}/p' "$OUT/manuscript.tex" | grep -v '^\s*%' \
       | sed -e 's/\\[a-zA-Z]*//g' -e 's/[{}$&\\]//g' | wc -w)
echo "  manuscript body: about $body words incl. tables (no fixed limit; 8,000-12,000 typical)"

# double-anonymized review: no author names, affiliations, e-mails or ORCIDs in the reviewed files
ident='Lewandowski|Szerszeń|Dowgalec|Tkacz|Wróbel|Powiślański|Kwidzyn|Atende|Academy of Silesia|akademiaslaska|Collegium Medicum|ORCID|Banking Process Support'
for f in manuscript.tex declarations.tex Figure_*; do
    if grep -a -n -E "$ident" "$OUT/$f" > /dev/null 2>&1; then
        warn "identifying information in $f: $(grep -a -o -E "$ident" "$OUT/$f" | sort -u | tr '\n' ' ')"
    fi
done
pdftotext "$OUT/manuscript.pdf" - | grep -q -E "$ident" && warn "identifying information in manuscript.pdf"

grep -q -E '\\begin\{tabular\}\{[^}]*\|' "$OUT/manuscript.tex" && warn "a table uses vertical rules; the guide asks to avoid them"
while IFS= read -r l; do warn "incomplete author list in references.bib:$l"; done < <(grep -n 'and others' "$OUT/references.bib" || true)

for f in manuscript.tex declarations.tex title_page.tex cover_letter.tex highlights.txt; do
    n=$(grep -v -e '^\s*%' -e 'newcommand{\\fillin}' "$OUT/$f" | grep -c -E '\\fillin\{|TODO' || true)
    (( n == 0 )) || warn "$n unresolved TODO item(s) in $f"
done

# --- archive of the LaTeX source --------------------------------------------------------------
( cd "$OUT" && zip -q manuscript_source.zip manuscript.tex manuscript.bbl references.bib declarations.tex Figure_* )

echo
echo "Package contents:"
ls -1 "$OUT" | sed 's/^/  /'
echo
if (( WARN > 0 )); then
    echo "Done with $WARN warning(s); fix them before submitting. See README_zgloszenie.md."
else
    echo "Done, no warnings."
fi
