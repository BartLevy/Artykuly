// Budowa rozdzial.docx z narzedzia/build/rozdzial.json (wynik tex2json.py).
// Formatowanie wg wytycznych Wydawnictwa Naukowego UMK:
//   Times New Roman 12 pt, interlinia 1,5, wyjustowanie, wcięcie 0,75 cm,
//   marginesy 2,5 cm; przypisy i bibliografia 10 pt z wysunięciem 0,25 cm.
// Użycie: node narzedzia/json2docx.js  (z katalogu projektu)
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, FootnoteReferenceRun, Table, TableRow,
  TableCell, WidthType, BorderStyle, AlignmentType, HeadingLevel, LevelFormat,
  Footer, PageNumber, TableLayoutType,
} = require("docx");

const ROOT = path.resolve(__dirname, "..");
const data = JSON.parse(fs.readFileSync(path.join(__dirname, "build", "rozdzial.json"), "utf8"));

const FONT = "Times New Roman";
const CM = 567;                      // 1 cm w DXA
const INDENT = Math.round(0.75 * CM); // wcięcie akapitu / śródtytułu
const HANG = Math.round(0.25 * CM);   // wysunięcie przypisów i bibliografii
const LINE_15 = 360;                  // interlinia 1,5
const LINE_1 = 240;
const TEXT_WIDTH = Math.round(16 * CM);

// ---------------------------------------------------------------------
//  Runy
// ---------------------------------------------------------------------
function runs(list, opts = {}) {
  const out = [];
  for (const r of list) {
    if (r.fn !== undefined) {
      out.push(new FootnoteReferenceRun(r.fn));
    } else if (r.br) {
      out.push(new TextRun({ break: 1 }));
    } else {
      out.push(new TextRun({
        text: opts.upper ? r.t.toUpperCase() : r.t,
        // tylko wartości „true”: jawne „false” nadpisałoby styl (np. nagłówka)
        italics: r.i || undefined,
        bold: r.b || opts.bold || undefined,
        size: opts.size,
      }));
    }
  }
  return out;
}

const bodyPara = (children, extra = {}) => new Paragraph({
  children,
  alignment: AlignmentType.JUSTIFIED,
  indent: { firstLine: INDENT },
  spacing: { line: LINE_15, before: 0, after: 0 },
  ...extra,
});

// ---------------------------------------------------------------------
//  Pierwsza strona
// ---------------------------------------------------------------------
const children = [];
const { meta } = data;

children.push(new Paragraph({
  children: runs(meta.authors, { bold: true }),
  spacing: { line: LINE_1, after: 0 },
}));
meta.affiliation.forEach((a, k) => children.push(new Paragraph({
  children: runs(a),
  spacing: { line: LINE_1, after: k === meta.affiliation.length - 1 ? 720 : 0 },
})));
children.push(new Paragraph({
  children: runs(meta.titlePL, { bold: true, upper: true }),
  alignment: AlignmentType.CENTER,
  spacing: { line: LINE_1, after: 160 },
}));
children.push(new Paragraph({
  children: runs(meta.titleEN, { bold: true, upper: true }),
  alignment: AlignmentType.CENTER,
  spacing: { line: LINE_1, after: 600 },
}));

for (const a of data.abstracts) {
  children.push(new Paragraph({
    children: [new TextRun({ text: a.label + ": ", bold: true, size: 20 }), ...runs(a.runs, { size: 20 })],
    alignment: AlignmentType.JUSTIFIED,
    spacing: { line: LINE_1, after: 80 },
  }));
  children.push(new Paragraph({
    children: [new TextRun({ text: a.kwLabel + ": ", bold: true, size: 20 }), ...runs(a.kwRuns, { size: 20 })],
    alignment: AlignmentType.JUSTIFIED,
    spacing: { line: LINE_1, after: 360 },
  }));
}

// ---------------------------------------------------------------------
//  Tabele (linie poziome jak w booktabs)
// ---------------------------------------------------------------------
const NONE = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const RULE = (size) => ({ style: BorderStyle.SINGLE, size, color: "000000" });
let tableNo = 0;

function table(b) {
  tableNo += 1;
  const widths = b.widths_cm.map((w) => Math.round(w * CM));
  widths[widths.length - 1] += TEXT_WIDTH - widths.reduce((x, y) => x + y, 0);

  const cell = (content, k, borders, bold) => new TableCell({
    width: { size: widths[k], type: WidthType.DXA },
    borders,
    margins: { top: 40, bottom: 40, left: 80, right: 80 },
    children: [new Paragraph({
      children: runs(content, { size: 20, bold }),
      spacing: { line: LINE_1, before: 0, after: 0 },
    })],
  });

  const rows = [new TableRow({
    tableHeader: true,
    cantSplit: true,
    children: b.header.map((c, k) => cell(c, k, { top: RULE(8), bottom: RULE(4), left: NONE, right: NONE }, true)),
  })];
  b.rows.forEach((r, n) => rows.push(new TableRow({
    cantSplit: true,
    children: r.map((c, k) => cell(c, k, {
      top: NONE, left: NONE, right: NONE,
      bottom: n === b.rows.length - 1 ? RULE(8) : NONE,
    })),
  })));

  children.push(new Paragraph({
    children: [new TextRun({ text: `Tabela ${tableNo}. `, bold: true, size: 20 }), ...runs(b.caption, { size: 20 })],
    alignment: AlignmentType.CENTER,
    keepNext: true,
    spacing: { line: LINE_1, before: 240, after: 120 },
  }));
  children.push(new Table({
    width: { size: TEXT_WIDTH, type: WidthType.DXA },
    columnWidths: widths,
    layout: TableLayoutType.FIXED,
    borders: { top: NONE, bottom: NONE, left: NONE, right: NONE, insideHorizontal: NONE, insideVertical: NONE },
    rows,
  }));
  children.push(new Paragraph({
    children: b.source
      ? [new TextRun({ text: "Źródło: ", size: 20 }), ...runs(b.source, { size: 20 }), new TextRun({ text: ".", size: 20 })]
      : [],
    alignment: AlignmentType.CENTER,
    spacing: { line: LINE_1, before: 80, after: 240 },
  }));
}

// ---------------------------------------------------------------------
//  Treść
// ---------------------------------------------------------------------
let listNo = 0;
let inBio = false; // akapity noty biograficznej: 10 pt, interlinia pojedyncza
for (const b of data.blocks) {
  if (b.type === "para") {
    children.push(inBio
      ? bodyPara(runs(b.runs, { size: 20 }), { spacing: { line: LINE_1, before: 0, after: 0 } })
      : bodyPara(runs(b.runs)));
  } else if (b.type === "heading") {
    inBio = b.runs.map((r) => r.t).join("") === "Nota biograficzna";
    children.push(new Paragraph({
      heading: b.level === 1 ? HeadingLevel.HEADING_1 : HeadingLevel.HEADING_2,
      children: runs(b.runs),
    }));
  } else if (b.type === "list") {
    listNo += 1;
    for (const item of b.items) {
      children.push(new Paragraph({
        children: runs(item),
        numbering: { reference: "lista", level: 0, instance: listNo },
        alignment: AlignmentType.JUSTIFIED,
        spacing: { line: LINE_15, before: 0, after: 0 },
      }));
    }
  } else if (b.type === "table") {
    table(b);
  } else if (b.type === "bibliography") {
    children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("Bibliografia")] }));
    for (const entry of data.bibliography) {
      children.push(new Paragraph({
        children: runs(entry, { size: 20 }),
        alignment: AlignmentType.JUSTIFIED,
        indent: { left: HANG, hanging: HANG },
        spacing: { line: LINE_1, before: 0, after: 60 },
      }));
    }
  }
}

// ---------------------------------------------------------------------
//  Przypisy
// ---------------------------------------------------------------------
const footnotes = {};
data.footnotes.forEach((fn, k) => {
  footnotes[k + 1] = {
    children: [new Paragraph({ style: "FootnoteText", children: [new TextRun(" "), ...runs(fn)] })],
  };
});

// ---------------------------------------------------------------------
//  Dokument
// ---------------------------------------------------------------------
const doc = new Document({
  creator: "Bartosz Lewandowski",
  title: meta.titlePL.map((r) => r.t).join("").replace(/ /g, " "),
  styles: {
    default: {
      document: {
        run: { font: FONT, size: 24, language: { value: "pl-PL" } },
        paragraph: { spacing: { line: LINE_15 } },
      },
      heading1: {
        run: { font: FONT, size: 24, bold: true, italics: false, color: "000000" },
        paragraph: { indent: { firstLine: INDENT }, spacing: { line: LINE_15, before: 240, after: 120 }, keepNext: true },
      },
      heading2: {
        run: { font: FONT, size: 24, bold: true, italics: true, color: "000000" },
        paragraph: { indent: { firstLine: INDENT }, spacing: { line: LINE_15, before: 180, after: 60 }, keepNext: true },
      },
      footnoteText: {
        run: { font: FONT, size: 20 },
        paragraph: {
          alignment: AlignmentType.JUSTIFIED,
          indent: { left: HANG, hanging: HANG },
          spacing: { line: LINE_1, before: 0, after: 0 },
        },
      },
    },
  },
  numbering: {
    config: [{
      reference: "lista",
      levels: [{
        level: 0,
        format: LevelFormat.DECIMAL,
        text: "%1.",
        alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: INDENT + 360, hanging: 360 } } },
      }],
    }],
  },
  footnotes,
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 },
        margin: { top: 1417, bottom: 1417, left: 1417, right: 1417 },
      },
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { line: LINE_1 },
          children: [new TextRun({ children: [PageNumber.CURRENT] })],
        })],
      }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  const out = path.join(ROOT, "rozdzial.docx");
  fs.writeFileSync(out, buf);
  console.log(`rozdzial.docx: ${data.footnotes.length} przypisów, ${tableNo} tabel`);
});
