import assert from 'node:assert/strict';
import test from 'node:test';

import {
  buildBuyer,
  buildDocument,
  buildItems,
  computeLineTaxes,
  computeTotals,
  productCode,
  shippingCharge,
  vendorSalt
} from '../../../../apps/vendor-docs-generator/js/modules/document-model.js';
import { DOCUMENT_TYPES, TAX_RATE, VENDORS } from '../../../../apps/vendor-docs-generator/js/modules/vendors.js';

const TODAY = new Date(2026, 5, 15);

/**
 * Parse a `$1,234.50` string back into a number, so a test can re-derive the
 * arithmetic from the rendered strings rather than trusting the same helper
 * the model used to produce them.
 * @param {string} text - Money string.
 * @returns {number} Numeric value.
 */
function parseMoney(text) {
  return Number(text.replace(/[$,]/g, ''));
}

/**
 * @param {ReturnType<typeof buildDocument>} model - Document model.
 * @param {string} kind - Block kind to find.
 * @returns {any} The first matching block.
 */
function blockOf(model, kind) {
  return model.blocks.find((block) => block.kind === kind);
}

test('buildItems keeps every row internally consistent', () => {
  for (const vendor of VENDORS) {
    const items = buildItems(vendor.id, 1234, 6);
    assert.ok(items.length > 0);

    for (const item of items) {
      assert.ok(item.qty >= 1, `${vendor.id} produced a non-positive quantity`);
      assert.ok(item.price > 0, `${vendor.id} produced a non-positive price`);
      // The row amount must be exactly quantity times unit price, to the cent.
      assert.equal(
        item.amount,
        Math.round(item.qty * item.price * 100) / 100,
        `${vendor.id}: ${item.qty} x ${item.price} should be ${item.qty * item.price}`
      );
    }
  }
});

test('buildItems jitters prices within four percent of the catalogue', () => {
  const items = buildItems('lumen', 5150, 6);
  const listPrices = new Map([
    ['Ergonomic task chair', 389],
    ['Sit-stand desk 1600mm', 640],
    ['Acoustic panel set', 275],
    ['Meeting table 8-seat', 1180],
    ['Storage credenza', 520],
    ['Installation and assembly', 450]
  ]);

  for (const item of items) {
    const list = listPrices.get(item.desc);
    // Below the $100 threshold prices round to a nickel, above it to the
    // dollar, so allow one rounding step on top of the 4% jitter band.
    assert.ok(
      Math.abs(item.price - list) <= list * 0.04 + 1,
      `${item.desc} priced at ${item.price} strayed from list ${list}`
    );
  }
});

test('buildItems is capped by the catalogue size', () => {
  assert.equal(buildItems('apex', 11, 99).length, 6);
  assert.equal(buildItems('apex', 11, 2).length, 2);
});

test('buildItems prices subscription units by term rather than by pallet', () => {
  // Nimbus sells monthly and yearly units, which are quantified 1-3 rather
  // than the 2-41 range the physical catalogues use.
  const items = buildItems('nimbus', 8080, 6);
  const subscriptions = items.filter((item) => item.unit === 'mo' || item.unit === 'yr');
  assert.ok(subscriptions.length > 0);

  for (const item of subscriptions) {
    assert.ok(item.qty >= 1 && item.qty <= 3, `${item.desc} had quantity ${item.qty}`);
  }
});

test('computeTotals sums the per-line rounded tax, not the rate on the subtotal', () => {
  const items = [
    { desc: 'a', unit: 'ea', price: 10, qty: 3, amount: 30 },
    { desc: 'b', unit: 'ea', price: 2.5, qty: 4, amount: 10 }
  ];
  const totals = computeTotals(items);

  assert.equal(totals.subtotal, 40);
  // 30 * 0.0825 = 2.475 -> 2.48 and 10 * 0.0825 = 0.825 -> 0.83, so 3.31, where
  // the rate applied once to 40 would give 3.30. The dense layout has to print a
  // tax column that adds up, so the sum of the lines is the definition both
  // layouts follow.
  assert.equal(totals.tax, 3.31);
  assert.equal(totals.grand, 43.31);
  assert.equal(totals.taxRate, TAX_RATE);
  assert.deepEqual(computeLineTaxes(items), [2.48, 0.83]);
});

test('the clean and dense invoices of one seed print the same grand total', () => {
  for (const vendor of VENDORS) {
    for (let index = 0; index < 40; index += 1) {
      const seed = 500 + index * 131;
      const options = { docTypeId: 'invoice', seed, today: TODAY, vendorId: vendor.id };
      const clean = buildDocument({ ...options, style: 'clean' });
      const dense = buildDocument({ ...options, style: 'dense' });

      const cleanTotals = blockOf(clean, 'totals').rows;
      const denseTotals = blockOf(dense, 'totals').rows;
      const cleanGrand = parseMoney(cleanTotals[cleanTotals.length - 1][1]);
      const denseAssessable = parseMoney(denseTotals[0][1]);
      const denseTax = parseMoney(denseTotals[1][1]);

      // The dense invoice adds shipping on top, so the comparable quantity is
      // its line-item total. Harbor at one seed used to print $53,484.92 clean
      // and $53,484.93 dense off the very same five lines.
      assert.equal(
        Math.round((denseAssessable + denseTax) * 100) / 100,
        cleanGrand,
        `${vendor.id} seed ${seed} disagrees between layouts`
      );
    }
  }
});

test('computeTotals handles an empty document', () => {
  assert.deepEqual(computeTotals([]), { subtotal: 0, tax: 0, grand: 0, taxRate: TAX_RATE });
});

test('buildBuyer produces a complete, seed-stable buying party', () => {
  const buyer = buildBuyer(4711);
  assert.deepEqual(buyer, buildBuyer(4711));
  assert.ok(buyer.name.length > 0);
  assert.equal(buyer.lines.length, 2);
  assert.match(buyer.lines[1], /^[A-Za-z ]+, [A-Z]{2} \d{5}$/);
  assert.match(buyer.phone, /^\(720\) 555-0\d{3}$/);
});

test('every document type builds, for every vendor, with a stable filename', () => {
  for (const vendor of VENDORS) {
    for (const type of DOCUMENT_TYPES) {
      const model = buildDocument({
        docTypeId: type.id,
        seed: 2024,
        today: TODAY,
        vendorId: vendor.id
      });

      assert.ok(model.blocks.length > 0, `${vendor.id}/${type.id} produced no blocks`);
      assert.ok(model.title.length > 0);
      assert.equal(model.filenameBase, `${vendor.id}_${model.docVariantId}_2024`);
      assert.match(model.footer, /Not a valid tax record/);
    }
  }
});

test('the filename says which adjustment note the page actually is', () => {
  const credit = buildDocument({ docTypeId: 'creditnote', seed: 100, today: TODAY, vendorId: 'apex' });
  const debit = buildDocument({ docTypeId: 'creditnote', seed: 101, today: TODAY, vendorId: 'apex' });

  // Half of these pages print DEBIT NOTE, and every one of them used to be
  // filed as `creditnote`, so the label contradicted the image.
  assert.equal(credit.title, 'Credit note');
  assert.equal(credit.docVariantId, 'creditnote');
  assert.equal(credit.filenameBase, 'apex_creditnote_100');

  assert.equal(debit.title, 'Debit note');
  assert.equal(debit.docVariantId, 'debitnote');
  assert.equal(debit.filenameBase, 'apex_debitnote_101');
});

test('one seed gives every vendor its own paperwork but the same customer', () => {
  const seed = 4242;
  const models = VENDORS.map((vendor) =>
    buildDocument({ docTypeId: 'invoice', seed, today: TODAY, vendorId: vendor.id })
  );
  const metaOf = (model) => Object.fromEntries(blockOf(model, 'parties').meta);

  // The seed owns the commercial event, so the buyer and the dates are shared.
  // That is what makes the side-by-side comparison in the About section real.
  for (const model of models) {
    assert.deepEqual(blockOf(model, 'parties').lines, blockOf(models[0], 'parties').lines);
    assert.equal(metaOf(model).Date, metaOf(models[0]).Date);
  }

  // The vendor owns its own series and its own catalogue draw. All six used to
  // print INV-213257 and the identical quantity vector 17, 34, 14, 7, 8.
  const numbers = new Set(models.map((model) => metaOf(model)['Invoice #']));
  assert.equal(numbers.size, VENDORS.length, `document numbers collided: ${[...numbers]}`);

  const quantities = new Set(
    models.map((model) => blockOf(model, 'table').rows.map((row) => row[2]).join(','))
  );
  assert.equal(quantities.size, VENDORS.length, `quantity vectors collided: ${[...quantities]}`);

  const registrations = new Set(VENDORS.map((vendor) => vendor.companyReg));
  assert.equal(registrations.size, VENDORS.length, 'a company registration belongs to the seller');
});

test('one seed gives every vendor its own statement ledger', () => {
  const ledgers = VENDORS.map((vendor) =>
    JSON.stringify(
      blockOf(
        buildDocument({ docTypeId: 'statement', seed: 8080, today: TODAY, vendorId: vendor.id }),
        'table'
      ).rows
    )
  );

  // buildStatement never touched the vendor, so all six were byte-identical
  // apart from the branding painted around them.
  assert.equal(new Set(ledgers).size, VENDORS.length);
});

test('vendorSalt is stable, bounded, and distinct per vendor', () => {
  const salts = VENDORS.map((vendor) => vendorSalt(vendor.id));
  assert.equal(new Set(salts).size, VENDORS.length);

  for (const salt of salts) {
    assert.ok(Number.isInteger(salt) && salt >= 0 && salt < 99_991);
  }

  assert.equal(vendorSalt('apex'), vendorSalt('apex'));
});

test('productCode is stable per description and not a row index', () => {
  assert.equal(productCode('Anchor bolt kit'), productCode('Anchor bolt kit'));
  assert.notEqual(productCode('Anchor bolt kit'), productCode('Carbide drill bit set'));
  assert.match(productCode('Anchor bolt kit'), /^\d{6}$/);
});

test('shipping is charged on goods and stays zero for pure services', () => {
  const services = [
    { desc: 'Managed hosting', unit: 'mo', price: 420, qty: 1, amount: 420 },
    { desc: 'SSL certificate', unit: 'yr', price: 150, qty: 1, amount: 150 }
  ];
  assert.equal(shippingCharge(services, 12), 0, 'nothing ships on a services invoice');

  const goods = [{ desc: 'Anchor bolt kit', unit: 'kit', price: 40, qty: 5, amount: 200 }];
  const charges = new Set(
    Array.from({ length: 40 }, (_unused, index) => shippingCharge(goods, index * 31))
  );

  // The field used to be a hardcoded $0.00 on every dense invoice, which an
  // extractor can learn without reading the page.
  assert.ok(charges.size > 1, 'shipping should vary');
  assert.ok([...charges].some((value) => value > 0), 'goods should sometimes be charged freight');
  assert.ok([...charges].some((value) => value === 0), 'and sometimes go carriage paid');
});

test('the same seed rebuilds an identical document', () => {
  const options = { docTypeId: 'invoice', seed: 90210, today: TODAY, vendorId: 'harbor' };
  assert.deepEqual(buildDocument(options), buildDocument(options));
});

test('different seeds move the buyer, dates, and amounts', () => {
  const first = buildDocument({ docTypeId: 'invoice', seed: 111, today: TODAY, vendorId: 'apex' });
  const second = buildDocument({ docTypeId: 'invoice', seed: 222, today: TODAY, vendorId: 'apex' });
  assert.notDeepEqual(first.blocks, second.blocks);
});

test('the clean invoice totals match its own printed line items', () => {
  const model = buildDocument({
    docTypeId: 'invoice',
    seed: 31_337,
    today: TODAY,
    vendorId: 'ironwood'
  });

  const rows = blockOf(model, 'table').rows;
  const totals = blockOf(model, 'totals').rows;

  // Re-derive the arithmetic straight from the strings the document prints.
  let expectedSubtotal = 0;

  for (const row of rows) {
    const qty = Number(row[2]);
    const unitPrice = parseMoney(row[4]);
    const amount = parseMoney(row[5]);
    assert.equal(amount, Math.round(qty * unitPrice * 100) / 100, `row ${row[1]} does not multiply out`);
    expectedSubtotal += amount;
  }

  expectedSubtotal = Math.round(expectedSubtotal * 100) / 100;
  // Summed per line, matching what the dense layout has to print in its tax
  // column, so the two treatments of one seed cannot disagree.
  const expectedTax =
    Math.round(
      rows.reduce((sum, row) => sum + Math.round(parseMoney(row[5]) * TAX_RATE * 100) / 100, 0) *
        100
    ) / 100;

  assert.equal(parseMoney(totals[0][1]), expectedSubtotal, 'printed subtotal');
  assert.equal(totals[1][0], 'Sales tax (8.25%)');
  assert.equal(parseMoney(totals[1][1]), expectedTax, 'printed tax');
  assert.equal(
    parseMoney(totals[2][1]),
    Math.round((expectedSubtotal + expectedTax) * 100) / 100,
    'printed grand total'
  );
});

test('the invoice dates the document today and thirty days out', () => {
  const model = buildDocument({ docTypeId: 'invoice', seed: 777, today: TODAY, vendorId: 'apex' });
  const meta = Object.fromEntries(blockOf(model, 'parties').meta);
  const issued = new Date(meta.Date);
  const due = new Date(meta['Due date']);

  assert.equal((due - issued) / 86_400_000, 30, 'net-30 terms should be exactly 30 days');
  assert.ok(issued <= TODAY, 'documents are backdated, never postdated');
  assert.ok((TODAY - issued) / 86_400_000 <= 180, 'documents stay within the last 180 days');
  assert.equal(meta.Terms, 'Net 30');
});

test('the dense invoice carries per-line tax that sums to its own footer', () => {
  const model = buildDocument({
    docTypeId: 'invoice',
    seed: 5150,
    style: 'dense',
    today: TODAY,
    vendorId: 'nimbus'
  });

  assert.equal(model.dense, true);
  assert.equal(model.style, 'dense');
  assert.equal(model.title, 'Tax invoice');
  assert.equal(model.filenameBase, 'nimbus_invoice_dense_5150');

  const table = blockOf(model, 'table');
  let assessable = 0;
  let tax = 0;

  for (const row of table.rows) {
    const rowAssessable = parseMoney(row[7]);
    const rowTax = parseMoney(row[9]);
    assert.equal(row[8], '8.25%');
    assert.equal(rowTax, Math.round(rowAssessable * TAX_RATE * 100) / 100, 'per-line tax');
    assert.equal(parseMoney(row[10]), Math.round((rowAssessable + rowTax) * 100) / 100, 'line total');
    assessable += rowAssessable;
    tax += rowTax;
  }

  assessable = Math.round(assessable * 100) / 100;
  tax = Math.round(tax * 100) / 100;

  assert.equal(parseMoney(table.footer[7]), assessable, 'footer assessable');
  assert.equal(parseMoney(table.footer[9]), tax, 'footer tax');
  assert.equal(parseMoney(table.footer[10]), Math.round((assessable + tax) * 100) / 100, 'footer total');

  // And the summary block has to agree with the table footer.
  const totals = blockOf(model, 'totals');
  assert.equal(parseMoney(totals.rows[0][1]), assessable);
  assert.equal(parseMoney(totals.rows[1][1]), tax);
  assert.equal(parseMoney(totals.rows[3][1]), Math.round((assessable + tax) * 100) / 100);
});

test('the dense invoice spells its grand total the way the summary states it', () => {
  const model = buildDocument({
    docTypeId: 'invoice',
    seed: 4242,
    style: 'dense',
    today: TODAY,
    vendorId: 'verde'
  });

  const grand = parseMoney(blockOf(model, 'totals').rows[3][1]);
  const cents = String(Math.round((grand - Math.floor(grand)) * 100)).padStart(2, '0');
  assert.ok(blockOf(model, 'words').text.endsWith(`and ${cents}/100 only`));
});

test('the dense layout is ignored for anything that is not an invoice', () => {
  const model = buildDocument({
    docTypeId: 'receipt',
    seed: 42,
    style: 'dense',
    today: TODAY,
    vendorId: 'apex'
  });

  assert.equal(model.dense, false);
  assert.equal(model.style, 'clean');
  assert.equal(model.filenameBase, 'apex_receipt_42');
});

test('the receipt shows the tax it charged and closes at a zero balance', () => {
  const model = buildDocument({ docTypeId: 'receipt', seed: 606, today: TODAY, vendorId: 'lumen' });
  assert.equal(blockOf(model, 'stamp').text, 'PAID');

  const rows = Object.fromEntries(blockOf(model, 'totals').rows);
  const lineSum =
    Math.round(
      blockOf(model, 'table').rows.reduce((sum, row) => sum + parseMoney(row[5]), 0) * 100
    ) / 100;

  // The receipt used to jump from the item table straight to an amount due that
  // silently included 8.25%, so the printed lines never summed to the printed
  // total and nothing on the page explained the gap.
  assert.equal(parseMoney(rows.Subtotal), lineSum, 'the subtotal must equal the printed lines');
  assert.equal(
    Math.round((parseMoney(rows.Subtotal) + parseMoney(rows['Sales tax (8.25%)'])) * 100) / 100,
    parseMoney(rows['Amount due']),
    'subtotal plus tax must equal the amount due'
  );
  assert.equal(rows['Amount due'], rows['AMOUNT PAID'], 'amount paid should clear the amount due');
  assert.equal(parseMoney(rows['Balance due']), 0, 'balance due should be zero');
  assert.equal(blockOf(model, 'totals').emphasisIndex, 3);
});

test('a receipt settles the invoice its own seed produces', () => {
  for (const vendor of VENDORS) {
    const options = { seed: 24_680, today: TODAY, vendorId: vendor.id };
    const invoice = buildDocument({ ...options, docTypeId: 'invoice' });
    const receipt = buildDocument({ ...options, docTypeId: 'receipt' });
    const note = buildDocument({ ...options, docTypeId: 'creditnote' });

    const invoiceNumber = Object.fromEntries(blockOf(invoice, 'parties').meta)['Invoice #'];
    const settled = Object.fromEntries(blockOf(receipt, 'parties').meta)['Against invoice'];
    const adjusted = Object.fromEntries(blockOf(note, 'parties').meta)['Against invoice'];

    // One seed is one commercial event. These used to be three unrelated
    // derivations, so no receipt or note in the corpus could be matched to any
    // invoice in the corpus.
    assert.equal(settled, invoiceNumber, `${vendor.id} receipt points elsewhere`);
    assert.equal(adjusted, invoiceNumber, `${vendor.id} note points elsewhere`);
  }
});

test('the quotation is valid for fourteen days and disclaims being an invoice', () => {
  const model = buildDocument({ docTypeId: 'quotation', seed: 808, today: TODAY, vendorId: 'apex' });
  const meta = Object.fromEntries(blockOf(model, 'parties').meta);
  const issued = new Date(meta.Date);
  const valid = new Date(meta['Valid until']);

  assert.equal((valid - issued) / 86_400_000, 14);
  assert.equal(model.subtitle, 'THIS IS NOT A TAX INVOICE');
  assert.match(blockOf(model, 'note').text, /not a tax invoice/);
});

test('the delivery challan withholds prices and counts the shipment', () => {
  const model = buildDocument({ docTypeId: 'challan', seed: 909, today: TODAY, vendorId: 'harbor' });
  const table = blockOf(model, 'table');

  assert.deepEqual(
    table.columns.map((column) => column.label),
    ['#', 'Description', 'Qty', 'Unit', 'Remarks']
  );
  assert.equal(blockOf(model, 'totals'), undefined, 'a challan must not price the goods');

  const chips = Object.fromEntries(blockOf(model, 'chips').items);
  // Packages are how the goods are crated, not the row count. Those used to be
  // the same number on every challan the generator had ever produced.
  assert.ok(
    Number(chips['Total packages']) >= table.rows.length,
    'every line needs at least one package'
  );
  assert.equal(
    Number(chips['Total qty']),
    table.rows.reduce((sum, row) => sum + Number(row[2]), 0)
  );

  // The remarks column used to read "Goods only" on every row of every challan.
  const remarks = new Set(table.rows.map((row) => row[4]));
  assert.equal(remarks.size, table.rows.length, 'each row needs its own remark');

  for (const remark of remarks) {
    assert.match(remark, /^Lot \d{4}-\d{2}/);
  }
  assert.deepEqual(blockOf(model, 'signatures').labels, [
    'Dispatched by',
    'Received by (sign and date)'
  ]);
});

test('note polarity follows seed parity and the callout states the direction', () => {
  const credit = buildDocument({ docTypeId: 'creditnote', seed: 100, today: TODAY, vendorId: 'apex' });
  const debit = buildDocument({ docTypeId: 'creditnote', seed: 101, today: TODAY, vendorId: 'apex' });

  assert.equal(credit.title, 'Credit note');
  assert.equal(debit.title, 'Debit note');
  assert.match(blockOf(credit, 'callout').text, /reduces the amount you owe/);
  assert.match(blockOf(debit, 'callout').text, /adds \$/);

  // The callout must quote the same grand total the totals block prints.
  const grand = blockOf(credit, 'totals').rows[2][1];
  assert.ok(blockOf(credit, 'callout').text.includes(grand));
});

test('the statement ledger balance walks the charges and payments', () => {
  const model = buildDocument({ docTypeId: 'statement', seed: 1357, today: TODAY, vendorId: 'verde' });
  const rows = blockOf(model, 'table').rows;
  const [opening, ...movements] = rows;

  assert.equal(opening[2], 'Balance brought forward');
  assert.equal(opening[3], '');
  assert.equal(opening[4], '');

  let balance = parseMoney(opening[5]);
  assert.ok(balance > 0, 'the period should open with something outstanding');

  for (const row of movements) {
    const charge = row[3] ? parseMoney(row[3]) : 0;
    const payment = row[4] ? parseMoney(row[4]) : 0;
    balance = Math.round((balance + charge - payment) * 100) / 100;
    assert.equal(parseMoney(row[5]), balance, `running balance after ${row[1]}`);
  }

  // Asserted against the walked balance directly, with no clamp. An earlier
  // Math.max(0, ...) here is what let a ledger that overpaid its own balance
  // ship: the banner read zero while the rows read negative.
  assert.equal(parseMoney(blockOf(model, 'banner').value), balance);
});

test('a statement never summarises transactions that have not happened yet', () => {
  for (const vendor of VENDORS) {
    for (let index = 0; index < 30; index += 1) {
      const seed = 3 + index * 97;
      const model = buildDocument({
        docTypeId: 'statement',
        seed,
        today: TODAY,
        vendorId: vendor.id
      });
      const meta = Object.fromEntries(blockOf(model, 'parties').meta);
      const generated = new Date(meta.Generated);
      const [periodStart, periodEnd] = meta.Period.split(' - ').map((part) => new Date(part));
      const dates = blockOf(model, 'table').rows.map((row) => new Date(row[0]));

      // The period label used to be `Q${1 + seed % 4}`, drawn from the seed and
      // unrelated to either the rows or the generated date, and the ledger
      // started at month `seed % 6`, so a statement generated in March routinely
      // listed activity running through June.
      assert.ok(periodEnd <= generated, `${vendor.id}/${seed} period ends after it was generated`);

      for (const date of dates) {
        assert.ok(date >= periodStart, `${vendor.id}/${seed} row precedes the stated period`);
        assert.ok(date <= generated, `${vendor.id}/${seed} row is in the future`);
      }

      for (let row = 1; row < dates.length; row += 1) {
        assert.ok(dates[row] >= dates[row - 1], `${vendor.id}/${seed} ledger is out of order`);
      }
    }
  }
});

test('no statement row ever shows a negative balance', () => {
  for (const vendor of ['apex', 'verde', 'nimbus', 'harbor', 'lumen', 'ironwood']) {
    for (let seed = 1; seed < 60; seed += 1) {
      const model = buildDocument({ docTypeId: 'statement', seed, today: TODAY, vendorId: vendor });

      for (const row of blockOf(model, 'table').rows) {
        const shown = parseMoney(row[5]);
        assert.ok(shown >= 0, `${vendor} seed ${seed} row ${row[1]} went to ${row[5]}`);
      }

      // A payment can never exceed what was outstanding when it was made.
      assert.ok(parseMoney(blockOf(model, 'banner').value) >= 0, `${vendor} seed ${seed}`);
    }
  }
});

test('an unknown vendor or type falls back rather than throwing', () => {
  const model = buildDocument({ docTypeId: 'nope', seed: 5, today: TODAY, vendorId: 'nope' });
  assert.equal(model.vendor.id, 'apex');
  assert.equal(model.docTypeId, 'invoice');
});

test('buildDocument defaults to the current date when none is supplied', () => {
  const model = buildDocument({ docTypeId: 'invoice', seed: 12, vendorId: 'apex' });
  const issued = new Date(Object.fromEntries(blockOf(model, 'parties').meta).Date);
  assert.ok(issued <= new Date());
});
