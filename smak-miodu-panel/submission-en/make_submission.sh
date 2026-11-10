#!/usr/bin/env bash
# Builds the MDPI Foods upload package in upload/:
#   manuscript.pdf            - compiled manuscript (upload as "Manuscript")
#   manuscript_latex.zip      - all LaTeX sources needed to compile (upload as "LaTeX source files")
#   cover_letter.pdf          - cover letter
#   Figure_1.png/.pdf, Figure_2.png/.pdf - figures as separate high-resolution files
#
# Usage: ./make_submission.sh            (run from submission-en/)
#        ./make_submission.sh --rerun    (first regenerate out.tex and figures from data/)

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [[ "${1:-}" == "--rerun" ]]; then
    (cd code && python3 app.py)
fi

latexmk -C main >/dev/null 2>&1 || true
latexmk -pdf -interaction=nonstopmode main.tex >/dev/null
latexmk -pdf -interaction=nonstopmode cover_letter.tex >/dev/null

if grep -q "undefined" main.log; then
    echo "ERROR: undefined references or citations, see main.log"; exit 1
fi

OUT=upload
rm -rf "$OUT"; mkdir -p "$OUT"
cp main.pdf "$OUT/manuscript.pdf"
cp cover_letter.pdf "$OUT/cover_letter.pdf"
cp fig_panel_lab.png "$OUT/Figure_1.png";    cp fig_panel_lab.pdf "$OUT/Figure_1.pdf"
cp fig_contrast_lab.png "$OUT/Figure_2.png"; cp fig_contrast_lab.pdf "$OUT/Figure_2.pdf"

zip -q -r "$OUT/manuscript_latex.zip" \
    main.tex section-introduction.tex section-methods.tex section-discussion.tex \
    appendix-descriptions.tex out.tex bibliography.bib main.bbl \
    fig_panel_lab.pdf fig_contrast_lab.pdf Definitions

echo "Package written to $OUT/:"
ls -1 "$OUT"

TODO=$(grep -c '\\tbc{' main.tex cover_letter.tex | awk -F: '{s+=$2} END {print s}')
if [[ "$TODO" -gt 0 ]]; then
    echo "WARNING: $TODO [TO BE COMPLETED] placeholders remain (grep -n 'tbc{' main.tex cover_letter.tex)."
fi
