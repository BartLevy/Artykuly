#!/usr/bin/env bash
# Builds the Measurement (Elsevier) submission package from main-els.tex (elsarticle class).
#
# Measurement uses double-anonymized review, so manuscript.tex gets the elsarticle "doubleblind"
# option: authors and affiliations stay in the source but are not printed. Author details go only in
# title_page.tex.
#
# Elsevier requires all LaTeX submission files in ONE folder level (no subfolders), so figures are
# copied next to the manuscript as Figure_1..N in order of appearance and \includegraphics paths
# are rewritten. The package is compiled in place to prove it builds on its own.
#
# Usage: ./make_submission.sh [output_dir]      (default: submission_package)

set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCS="$SRC_DIR/submission"
OUT="$(realpath -m "${1:-$SRC_DIR/submission_package}")"
MAIN="$SRC_DIR/main-els.tex"
WARN=0

warn() { echo "  WARNING: $*"; WARN=$((WARN + 1)); }

for f in "$MAIN" "$SRC_DIR/bibliography.bib" "$DOCS/declarations.tex" "$DOCS/highlights.txt" \
         "$DOCS/title_page.tex" "$DOCS/cover_letter.tex"; do
    [[ -f "$f" ]] || { echo "ERROR: missing $f"; exit 1; }
done

rm -rf "$OUT"
mkdir -p "$OUT"
echo "Building package in $OUT"

# --- manuscript and figures -------------------------------------------------------------------
cp "$MAIN" "$OUT/manuscript.tex"

# double-anonymized review: hide author names and affiliations in the manuscript
sed -i '0,/^\\documentclass\[/s//\\documentclass[doubleblind,/' "$OUT/manuscript.tex"
grep -q 'documentclass\[doubleblind,' "$OUT/manuscript.tex" || { echo "ERROR: could not add doubleblind option"; exit 1; }

n=0
while IFS= read -r path; do
    n=$((n + 1))
    ext="${path##*.}"
    fig="Figure_${n}.${ext}"
    cp "$SRC_DIR/$path" "$OUT/$fig"
    # rewrite this exact path only (first occurrence order == numbering order)
    sed -i "s|{${path}}|{${fig}}|" "$OUT/manuscript.tex"
    echo "  $path -> $fig"
done < <(grep -v '^\s*%' "$MAIN" | grep -o '\\includegraphics\(\[[^]]*\]\)\?{[^}]*}' | sed 's/.*{\(.*\)}/\1/')

# declarations go in unnumbered sections directly before the reference list
awk '/^\\bibliography\{/ && !done { print "\\input{declarations}"; print "\\clearpage"; done=1 } { print }' \
    "$OUT/manuscript.tex" > "$OUT/manuscript.tmp" && mv "$OUT/manuscript.tmp" "$OUT/manuscript.tex"

# references: elsarticle-num (numbered in order of first citation) is set in main-els.tex

# bibliography: the Polish access note becomes English in the package copy only
sed 's/Dostęp: \[\([^]]*\)\]/Accessed \1/' "$SRC_DIR/bibliography.bib" > "$OUT/bibliography.bib"

cp "$DOCS/declarations.tex" "$DOCS/highlights.txt" "$DOCS/title_page.tex" "$DOCS/cover_letter.tex" "$OUT/"

# double-anonymized review: the CRediT statement names the authors, so it moves from the
# manuscript declarations to the end of the title page (package copies only)
awk '/^\\section\*\{CRediT/{skip=1; next} skip && /^\\section\*/{skip=0} !skip' \
    "$DOCS/declarations.tex" > "$OUT/declarations.tex"
credit=$(awk '/^\\section\*\{CRediT/{on=1} on && /^\\section\*/ && !/CRediT/{exit} on' "$DOCS/declarations.tex" \
         | grep -v '^%' | sed 's/\\section\*{\(.*\)}/\\vspace{1.5em}\\noindent\\textbf{\1}\\par/')
[[ -n "$credit" ]] || warn "no CRediT statement found in declarations.tex"
CREDIT="$credit" awk '/^\\end\{document\}/{print ENVIRON["CREDIT"]; print ""} {print}' \
    "$DOCS/title_page.tex" > "$OUT/title_page.tex"

# --- compile everything inside the flat folder ------------------------------------------------
echo "Compiling..."
(
    cd "$OUT"
    for doc in manuscript title_page cover_letter; do
        if ! latexmk -pdf -interaction=nonstopmode -halt-on-error "$doc.tex" > "$doc.build.log" 2>&1; then
            echo "ERROR: $doc.tex failed to compile, see $OUT/$doc.build.log"; exit 1
        fi
    done
    undefined=$(grep -c 'undefined' manuscript.log || true)
    [[ "$undefined" == "0" ]] || echo "  WARNING: $undefined undefined references/citations in manuscript.log"
    # keep manuscript.bbl (Elsevier asks for it with the .tex); drop the rest of the build output
    latexmk -c > /dev/null 2>&1 || true
    rm -f ./*.build.log ./*.bak ./*.spl
)
[[ -f "$OUT/manuscript.bbl" ]] || warn "manuscript.bbl was not produced"

# --- checks against the Guide for Authors -----------------------------------------------------
echo "Checking Guide for Authors limits..."

words=$(sed -n '/\\begin{abstract}/,/\\end{abstract}/p' "$OUT/manuscript.tex" \
        | sed -e 's/\$[^$]*\$/X/g' -e 's/\\[a-zA-Z]*//g' | wc -w)
words=$((words - 0))
(( words <= 250 )) && echo "  abstract: $words words (limit 250)" || warn "abstract has $words words (limit 250)"

kw=$(sed -n '/\\begin{keyword}/,/\\end{keyword}/p' "$OUT/manuscript.tex" | grep -v 'keyword}' \
     | sed 's/\\sep/\n/g' | grep -c '[a-zA-Z]' || true)
(( kw >= 1 && kw <= 7 )) && echo "  keywords: $kw (allowed 1-7)" || warn "$kw keywords (allowed 1-7)"

hl=$(grep -c '^- ' "$OUT/highlights.txt" || true)
(( hl >= 3 && hl <= 5 )) && echo "  highlights: $hl bullets (allowed 3-5)" || warn "$hl highlights (allowed 3-5)"
while IFS= read -r line; do
    text="${line#- }"
    len=$(printf '%s' "$text" | wc -m)
    (( len <= 85 )) || warn "highlight longer than 85 characters ($len): $text"
done < <(grep '^- ' "$OUT/highlights.txt")

for fig in "$OUT"/Figure_*; do
    width=$(identify -format '%w' "$fig[0]" 2>/dev/null || echo 0)
    (( width >= 1063 )) || warn "$(basename "$fig") is $width px wide; minimum 1063 px (300 dpi, single column)"
done

grep -q '|c|' "$OUT/manuscript.tex" && warn "a table uses vertical rules; the guide asks to avoid them"
while IFS= read -r l; do warn "incomplete author list in bibliography.bib:$l"; done < <(grep -n 'and others' "$OUT/bibliography.bib" || true)

todo=$( { grep -l 'TODO' "$OUT"/*.tex "$OUT"/*.txt 2>/dev/null || true; } | xargs -r -n1 basename | tr '\n' ' ')
[[ -z "$todo" ]] || warn "unresolved [TODO] markers in: $todo"

# --- archive of the source files --------------------------------------------------------------
(
    cd "$OUT"
    zip -q -j manuscript_source.zip manuscript.tex manuscript.bbl bibliography.bib declarations.tex Figure_*
)

echo
echo "Package contents:"
ls -1 "$OUT" | sed 's/^/  /'
echo
if (( WARN > 0 )); then
    echo "Done with $WARN warning(s); fix them before submitting. See submission/README_zgloszenie.md."
else
    echo "Done, no warnings."
fi
