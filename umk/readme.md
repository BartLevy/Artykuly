cd /disk/Work/Artykuly/umk
make          # buduje rozdzial.pdf (pdflatex → biber → pdflatex ×2)
make docx     # buduje rozdzial.docx (tex2json.py + json2docx.js)
make znaki    # pokazuje liczbę znaków ze spacjami (wymagane 20 000–50 000)
make clean    # usuwa pliki pomocnicze (.aux, .bbl, .log itd.)
