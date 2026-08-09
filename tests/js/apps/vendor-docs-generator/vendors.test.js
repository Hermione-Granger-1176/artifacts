import assert from 'node:assert/strict';
import test from 'node:test';

import {
  DOCUMENT_TYPES,
  TAX_RATE,
  VENDORS,
  catalogFor,
  findDocumentType,
  findVendor
} from '../../../../apps/vendor-docs-generator/js/modules/vendors.js';

test('every vendor is fully specified and uniquely identified', () => {
  const ids = new Set();

  for (const vendor of VENDORS) {
    assert.ok(!ids.has(vendor.id), `duplicate vendor id ${vendor.id}`);
    ids.add(vendor.id);

    for (const field of ['name', 'tagline', 'addr', 'email', 'phone', 'font', 'taxId']) {
      assert.ok(vendor[field], `${vendor.id} is missing ${field}`);
    }

    for (const field of ['accent', 'accentSoft', 'ink']) {
      assert.match(vendor[field], /^#[0-9a-f]{6}$/, `${vendor.id}.${field} is not a six-digit hex`);
    }

    assert.ok(['left', 'center', 'right'].includes(vendor.layout));
  }

  assert.equal(VENDORS.length, 6);
});

test('vendor contact details stay inside the reserved fiction ranges', () => {
  for (const vendor of VENDORS) {
    // 555-01xx numbers and .example domains are reserved for fiction, which is
    // what keeps generated samples from pointing at a real business.
    assert.match(vendor.phone, /555 01\d{2}$/, `${vendor.id} has a non-fictional phone number`);
    assert.match(vendor.email, /\.example$/, `${vendor.id} has a non-fictional email domain`);
  }
});

/**
 * WCAG relative luminance of an `#rrggbb` colour.
 * @param {string} hex - Six-digit hex colour.
 * @returns {number} Relative luminance in [0, 1].
 */
function luminance(hex) {
  const channels = [1, 3, 5].map((offset) => {
    const value = Number.parseInt(hex.slice(offset, offset + 2), 16) / 255;
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  });

  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

/**
 * WCAG contrast ratio between an `#rrggbb` colour and white.
 * @param {string} hex - Six-digit hex colour.
 * @returns {number} Contrast ratio, at least 1.
 */
function contrastWithWhite(hex) {
  return 1.05 / (luminance(hex) + 0.05);
}

test('vendor accents stay legible under the white text printed on them', () => {
  for (const vendor of VENDORS) {
    // Table headers and stamps print white on the accent, so the accent is
    // load-bearing for contrast, not decoration.
    const ratio = contrastWithWhite(vendor.accent);
    assert.ok(ratio >= 4.5, `${vendor.id} accent ${vendor.accent} is only ${ratio.toFixed(2)}:1`);
  }
});

test('vendor ink stays legible on both paper and its own soft fill', () => {
  for (const vendor of VENDORS) {
    const onPaper = contrastWithWhite(vendor.ink);
    assert.ok(onPaper >= 4.5, `${vendor.id} ink is only ${onPaper.toFixed(2)}:1 on paper`);

    const inkLuminance = luminance(vendor.ink);
    const softLuminance = luminance(vendor.accentSoft);
    const onSoft = (softLuminance + 0.05) / (inkLuminance + 0.05);
    assert.ok(onSoft >= 4.5, `${vendor.id} ink is only ${onSoft.toFixed(2)}:1 on its soft fill`);
  }
});

test('every vendor has a catalogue of priced units', () => {
  for (const vendor of VENDORS) {
    const catalog = catalogFor(vendor.id);
    assert.ok(catalog.length >= 6, `${vendor.id} has too few catalogue entries`);

    for (const entry of catalog) {
      assert.ok(entry.desc.length > 0);
      assert.ok(entry.unit.length > 0);
      assert.ok(entry.basePrice > 0);
    }
  }
});

test('catalogFor falls back for an unknown vendor', () => {
  assert.deepEqual(catalogFor('nope'), catalogFor('apex'));
});

test('document types are unique and labelled', () => {
  const ids = new Set(DOCUMENT_TYPES.map((type) => type.id));
  assert.equal(ids.size, DOCUMENT_TYPES.length);
  assert.equal(DOCUMENT_TYPES.length, 6);

  for (const type of DOCUMENT_TYPES) {
    assert.ok(type.label.length > 0);
  }
});

test('lookups resolve known ids and fall back on unknown ones', () => {
  assert.equal(findVendor('verde').name, 'Verde Organic Foods');
  assert.equal(findVendor('missing'), VENDORS[0]);
  assert.equal(findDocumentType('receipt').label, 'Receipt');
  assert.equal(findDocumentType('missing'), DOCUMENT_TYPES[0]);
});

test('the sales-tax rate is the documented flat rate', () => {
  assert.equal(TAX_RATE, 0.0825);
});
