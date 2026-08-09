import assert from 'node:assert/strict';
import test from 'node:test';

import { buildDocument } from '../../../../apps/vendor-docs-generator/js/modules/document-model.js';
import {
  hexToRgb,
  pdfFontFor,
  renderPdf
} from '../../../../apps/vendor-docs-generator/js/modules/pdf-render.js';
import { DOCUMENT_TYPES, VENDORS, findVendor } from '../../../../apps/vendor-docs-generator/js/modules/vendors.js';

import { createFakeJsPdf } from './library-fakes.js';

const TODAY = new Date(2026, 5, 15);

/**
 * Render one document into a recording jsPDF document.
 * @param {Record<string, any>} options - buildDocument options.
 * @returns {{ doc: any, model: any }} The recording document and its model.
 */
function renderInto(options) {
  const { JsPdf } = createFakeJsPdf();
  const model = buildDocument({ today: TODAY, ...options });
  return { doc: renderPdf(model, JsPdf), model };
}

/**
 * Flatten every string a fake document printed or tabulated.
 * @param {Record<string, any>} doc - Recording document.
 * @returns {string} All text, space separated.
 */
function allText(doc) {
  const tableText = doc.tables.flatMap((table) => [
    ...(table.head ?? []).flat(),
    ...(table.body ?? []).flat()
  ]);
  return [...doc.texts.map((entry) => entry.text), ...tableText].join(' ');
}

test('hexToRgb converts with and without the leading hash', () => {
  assert.deepEqual(hexToRgb('#1d4ed8'), [29, 78, 216]);
  assert.deepEqual(hexToRgb('ffffff'), [255, 255, 255]);
  assert.deepEqual(hexToRgb('#000000'), [0, 0, 0]);
});

test('the PDF opens as a portrait A4 page in points', () => {
  const { JsPdf, documents } = createFakeJsPdf();
  renderPdf(buildDocument({ docTypeId: 'invoice', seed: 1, today: TODAY, vendorId: 'apex' }), JsPdf);
  assert.deepEqual(documents[0].constructedWith, ['p', 'pt', 'a4']);
});

test('the letterhead prints the vendor identity and the accent rule', () => {
  const { doc, model } = renderInto({ docTypeId: 'invoice', seed: 2024, vendorId: 'harbor' });
  const printed = doc.texts.map((entry) => entry.text);

  assert.ok(printed.includes(model.vendor.name));
  assert.ok(printed.includes(model.vendor.tagline));
  assert.ok(printed.includes(model.vendor.taxId));
  assert.ok(printed.includes('INVOICE'), 'the title is printed upper-cased');

  const [bar] = doc.calls.filter((call) => call.name === 'rect');
  assert.deepEqual(bar.args.slice(0, 2), [0, 0], 'the accent bar sits at the top of the page');

  const fill = doc.calls.find((call) => call.name === 'setFillColor');
  assert.deepEqual(fill.args, hexToRgb(model.vendor.accent));
});

test('the sample-data footer is centred and wrapped inside the text column', () => {
  for (const vendor of VENDORS) {
    const { doc, model } = renderInto({ docTypeId: 'challan', seed: 5, vendorId: vendor.id });
    const words = model.footer.split(' ');
    const lines = doc.texts.filter((entry) => words.includes(entry.text.split(' ')[0]));
    const printed = doc.texts
      .filter((entry) => model.footer.includes(entry.text) && entry.align === 'center')
      .map((entry) => entry.text);

    assert.ok(lines.length > 0, `${vendor.id} should print a footer`);
    assert.equal(printed.join(' '), model.footer, `${vendor.id} footer should be complete`);

    // Ironwood's name and tagline push this string past the text column, and an
    // unwrapped centred line bleeds into both margins instead of breaking.
    for (const line of printed) {
      assert.ok(
        line.length * 7.5 * 0.5 <= 595 - 2 * 42 + 1,
        `${vendor.id} footer line overflows the text column: ${line}`
      );
    }
  }
});

test('the subtitle is only printed when the document has one', () => {
  const withSubtitle = renderInto({ docTypeId: 'quotation', seed: 6, vendorId: 'apex' });
  assert.ok(allText(withSubtitle.doc).includes('THIS IS NOT A TAX INVOICE'));

  const withoutSubtitle = renderInto({ docTypeId: 'invoice', seed: 6, vendorId: 'apex' });
  assert.equal(withoutSubtitle.model.subtitle, '');
});

test('the invoice writes its parties, line items, and totals into the text layer', () => {
  const { doc, model } = renderInto({ docTypeId: 'invoice', seed: 31_337, vendorId: 'ironwood' });
  const text = allText(doc);
  const parties = model.blocks.find((block) => block.kind === 'parties');
  const table = model.blocks.find((block) => block.kind === 'table');
  const totals = model.blocks.find((block) => block.kind === 'totals');

  assert.ok(text.includes('BILL TO'));
  assert.ok(text.includes(parties.lines[0]), 'the buyer name reaches the text layer');

  for (const row of table.rows) {
    assert.ok(text.includes(row[1]), `line item ${row[1]} is missing`);
    assert.ok(text.includes(row[5]), `line amount ${row[5]} is missing`);
  }

  assert.ok(text.includes(totals.rows[2][1]), 'the grand total is missing');
});

test('a totals table emphasises the row the model marked', () => {
  const { doc, model } = renderInto({ docTypeId: 'invoice', seed: 77, vendorId: 'apex' });
  const totals = model.blocks.find((block) => block.kind === 'totals');
  const totalsTable = doc.tables.find(
    (table) => table.body?.length === totals.rows.length && table.tableWidth === 230
  );

  assert.ok(totalsTable, 'a right-aligned totals table should be emitted');

  const styled = [];
  for (let index = 0; index < totals.rows.length; index += 1) {
    const cell = { styles: {}, text: [] };
    totalsTable.didParseCell({ cell, column: { index: 0 }, row: { index }, section: 'body' });
    styled.push(cell.styles.fontStyle === 'bold');
  }

  assert.deepEqual(
    styled,
    totals.rows.map((_row, index) => index === totals.emphasisIndex)
  );
});

test('the dense invoice emits the key grid, party pair, and a styled table footer', () => {
  const { doc, model } = renderInto({
    docTypeId: 'invoice',
    seed: 5150,
    style: 'dense',
    vendorId: 'nimbus'
  });

  const text = allText(doc);
  assert.ok(text.includes('TAX INVOICE'));
  assert.ok(text.includes('Supply type'));
  assert.ok(text.includes('Details of receiver (billed to)'));
  assert.ok(text.includes('Grand total (in words):'));
  assert.ok(text.includes(`For ${model.vendor.name} Inc.`));

  // Two side-by-side metadata tables, offset from each other horizontally.
  const gridTables = doc.tables.filter((table) => table.columnStyles?.[0]?.fontStyle === 'bold');
  assert.equal(gridTables.length, 2);
  assert.notEqual(gridTables[0].margin.left, gridTables[1].margin.left);

  const itemTable = model.blocks.find((block) => block.kind === 'table');
  const emitted = doc.tables.find((table) => table.body?.length === itemTable.rows.length + 1);
  assert.ok(emitted, 'the footer row should be appended to the table body');

  const footerCell = { styles: {}, text: [] };
  emitted.didParseCell({
    cell: footerCell,
    column: { index: 0 },
    row: { index: itemTable.rows.length },
    section: 'body'
  });
  assert.equal(footerCell.styles.fontStyle, 'bold');

  const bodyCell = { styles: {}, text: [] };
  emitted.didParseCell({ cell: bodyCell, column: { index: 0 }, row: { index: 0 }, section: 'body' });
  assert.equal(bodyCell.styles.fontStyle, undefined, 'ordinary rows stay unstyled');
});

test('the receipt stamps PAID and the challan draws two signature rules', () => {
  const receipt = renderInto({ docTypeId: 'receipt', seed: 606, vendorId: 'lumen' });
  const stamp = receipt.doc.texts.find((entry) => entry.text === 'PAID');
  assert.ok(stamp);
  assert.equal(stamp.align, 'center');

  const challan = renderInto({ docTypeId: 'challan', seed: 909, vendorId: 'harbor' });
  const text = allText(challan.doc);
  assert.ok(text.includes('Dispatched by'));
  assert.ok(text.includes('Received by (sign and date)'));
  assert.equal(
    challan.doc.calls.filter((call) => call.name === 'rect').length,
    3,
    'one accent bar plus two signature rules'
  );
  assert.ok(text.includes('Total packages: '), 'the chip summary becomes a text line');
});

test('the credit note renders its callout and the statement its balance banner', () => {
  const credit = renderInto({ docTypeId: 'creditnote', seed: 100, vendorId: 'apex' });
  assert.ok(allText(credit.doc).includes('reduces the amount you owe'));

  const statement = renderInto({ docTypeId: 'statement', seed: 1357, vendorId: 'verde' });
  const banner = statement.doc.tables.find((table) => table.body?.[0]?.[0] === 'Balance due');
  assert.ok(banner, 'the statement should emit a balance banner');

  // The fill has to sit in bodyStyles. Declared in `styles` it loses to the
  // theme's body styling, and this banner then printed white text on a flat
  // rgb(245, 245, 245): the balance due, the one number a statement of account
  // exists to communicate, was invisible in every exported PDF.
  assert.deepEqual(banner.bodyStyles.fillColor, hexToRgb(findVendor('verde').accent));
  assert.equal(banner.bodyStyles.textColor, 255);
  assert.equal(banner.styles.fillColor, undefined, 'a styles fill would be overridden');
  // Under the default striped theme, alternateRowStyles resolves to 245 on row
  // index 0 and beats both styles and bodyStyles, so this is the load-bearing
  // part of the fix, not the bodyStyles move.
  assert.equal(banner.theme, 'plain');

  const callout = credit.doc.tables.find((table) =>
    String(table.body?.[0]?.[0]).includes('reduces the amount you owe')
  );
  assert.deepEqual(callout.bodyStyles.fillColor, hexToRgb(findVendor('apex').accentSoft));
  assert.equal(callout.styles.fillColor, undefined);
  assert.equal(callout.theme, 'plain');
});

test('the letterhead and the title never overprint each other', () => {
  // Ironwood plus DELIVERY CHALLAN overlapped by 15pt on every seed, because
  // both halves were drawn at a fixed size from opposite margins with nothing
  // measured in between.
  for (const vendor of VENDORS) {
    for (const type of DOCUMENT_TYPES) {
      for (const style of ['clean', 'dense']) {
        const { doc, model } = renderInto({
          docTypeId: type.id,
          seed: 4242,
          style,
          vendorId: vendor.id
        });
        const name = doc.texts.find((entry) => entry.text === model.vendor.name);
        const title = doc.texts.find((entry) => entry.text === model.title.toUpperCase());

        assert.ok(name && title, `${vendor.id}/${type.id} should print both`);
        assert.equal(title.align, 'right');

        // Reconstructed from the sizes actually used, because the title shrinks
        // to fit and the monogram tile shifts the name right.
        const nameEnd = name.x + name.width;
        const titleStart = title.x - title.width;

        assert.ok(
          nameEnd <= titleStart,
          `${vendor.id}/${type.id}/${style} letterhead runs into the title`
        );
      }
    }
  }
});

test('a long meta value drops to its own line instead of overprinting the label', () => {
  // "Goods returned, damaged in transit" printed straight through "Reason:" on
  // a quarter of all credit notes, because the gutter was a fixed 170pt and the
  // right-aligned value simply grew leftwards into it.
  const seeds = Array.from({ length: 40 }, (_unused, index) => 100 + index * 2);
  let sawWrap = false;

  for (const seed of seeds) {
    const { doc } = renderInto({ docTypeId: 'creditnote', seed, vendorId: 'apex' });
    const labels = doc.texts.filter((entry) => entry.text.endsWith(':'));

    for (const label of labels) {
      const sameLine = doc.texts.filter(
        (entry) => entry !== label && Math.abs(entry.y - label.y) < 1 && entry.align === 'right'
      );

      for (const value of sameLine) {
        const labelEnd = label.x + label.text.length * 9 * 0.5;
        const valueStart = value.x - value.text.length * 9 * 0.5;
        assert.ok(valueStart >= labelEnd, `seed ${seed}: "${value.text}" overprints "${label.text}"`);
      }

      if (sameLine.length === 0) {
        sawWrap = true;
      }
    }
  }

  assert.ok(sawWrap, 'at least one long reason should have wrapped to its own line');
});

test('each vendor letterhead prints in its own font family', () => {
  const families = new Map(
    VENDORS.map((vendor) => {
      const { doc } = renderInto({ docTypeId: 'invoice', seed: 11, vendorId: vendor.id });
      const setFont = doc.calls.find((call) => call.name === 'setFont');
      return [vendor.id, setFont.args[0]];
    })
  );

  // Every vendor used to export in Helvetica regardless of its own `font`, so
  // six deliberately unrelated brands produced one identical letterhead.
  assert.equal(families.get('ironwood'), 'courier');
  assert.equal(families.get('verde'), 'times');
  assert.equal(families.get('apex'), 'helvetica');
  assert.ok(new Set(families.values()).size >= 3, 'the corpus needs more than one typeface');
});

test('each vendor font family reaches every autotable block', () => {
  for (const vendor of VENDORS) {
    for (const style of ['clean', 'dense']) {
      const { doc } = renderInto({ docTypeId: 'invoice', seed: 5150, style, vendorId: vendor.id });
      const family = pdfFontFor(vendor.font);

      for (const table of doc.tables) {
        assert.equal(table.styles.font, family, `${vendor.id}/${style} table should use ${family}`);
      }
    }
  }
});

test('pdfFontFor maps CSS stacks onto the jsPDF core fonts', () => {
  assert.equal(pdfFontFor("'SFMono-Regular', Menlo, monospace"), 'courier');
  assert.equal(pdfFontFor("Georgia, 'Times New Roman', serif"), 'times');
  assert.equal(pdfFontFor("'Helvetica Neue', Arial, sans-serif"), 'helvetica');
  assert.equal(pdfFontFor('Inter, system-ui, sans-serif'), 'helvetica');
});

test('a long document spills onto a second page rather than off the first', () => {
  // The dense invoice is the tallest layout; forcing a short page makes the
  // overflow guard fire without depending on a particular seed's item count.
  const { JsPdf, documents } = createFakeJsPdf({ pageHeight: 400 });
  renderPdf(
    buildDocument({ docTypeId: 'invoice', seed: 5150, style: 'dense', today: TODAY, vendorId: 'nimbus' }),
    JsPdf
  );

  assert.ok(documents[0].pages > 1, 'the cursor should have started a new page');
});

test('every vendor and type combination renders a PDF without throwing', () => {
  for (const vendor of VENDORS) {
    for (const type of DOCUMENT_TYPES) {
      const { doc } = renderInto({ docTypeId: type.id, seed: 4321, vendorId: vendor.id });
      assert.ok(
        allText(doc).length > 200,
        `${vendor.id}/${type.id} produced suspiciously little text`
      );
    }
  }
});
