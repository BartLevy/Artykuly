# Kompilacja rozdziału: make | make docx | make znaki | make clean
DOC = rozdzial
SHELL := /bin/bash

all: $(DOC).pdf

$(DOC).pdf: $(DOC).tex bibliografia.bib
	pdflatex -interaction=nonstopmode $(DOC)
	biber $(DOC)
	pdflatex -interaction=nonstopmode $(DOC)
	pdflatex -interaction=nonstopmode $(DOC)

# Wersja Word (przypisy i bibliografia generowane przez biblatex)
docx: $(DOC).docx

$(DOC).docx: $(DOC).tex bibliografia.bib narzedzia/tex2json.py narzedzia/json2docx.js
	python3 narzedzia/tex2json.py
	node narzedzia/json2docx.js

# Przybliżona objętość (znaki ze spacjami) – wymagane 20 000–50 000
znaki: $(DOC).pdf
	@pdftotext -nopgbrk $(DOC).pdf - | tr -s ' \n' ' ' | wc -m

clean:
	rm -f $(DOC).{aux,bbl,bcf,blg,log,out,run.xml,toc}

.PHONY: all docx znaki clean
