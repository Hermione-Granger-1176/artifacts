import assert from 'node:assert/strict';
import test from 'node:test';

import { transformBoxes } from '../../../../apps/vendor-docs-generator/js/modules/annotate-boxes.js';
import {
  DEGRADATION_APPLIES_TO,
  DEGRADE_KNOBS,
  DEGRADE_PRESETS,
  IDENTITY_MATRIX,
  applyPixelPass,
  degradeCanvas,
  encodeCanvas,
  findPreset,
  imageEncoding,
  isClean,
  planDegradation,
  project,
  resolveSettings,
  toPixelMatrix
} from '../../../../apps/vendor-docs-generator/js/modules/degrade.js';
import { createSeededRandom } from '../../../../apps/vendor-docs-generator/js/modules/random.js';

import { createFakeCanvas, createFakeCanvasDocument } from './library-fakes.js';

const PAGE = { width: 794, height: 1123 };

/**
 * Plan a degradation over the A4 layout page.
 * @param {string} preset - Preset id.
 * @param {Record<string, any>} [overrides={}] - Custom knob values.
 * @param {number} [seed=4242] - Document seed.
 * @returns {ReturnType<typeof planDegradation>} The plan.
 */
function plan(preset, overrides = {}, seed = 4242) {
  return planDegradation({ ...PAGE, preset, seed, settings: resolveSettings(preset, overrides) });
}

test('the clean preset changes nothing at all', () => {
  const settings = resolveSettings('clean');

  assert.ok(isClean(settings));
  assert.deepEqual(plan('clean').transform, IDENTITY_MATRIX);
  assert.deepEqual(imageEncoding(settings), { extension: 'png', mime: 'image/png', quality: 1 });
});

test('every preset resolves to a complete settings object', () => {
  const keys = Object.keys(resolveSettings('clean')).sort();

  for (const preset of DEGRADE_PRESETS) {
    const settings = resolveSettings(preset.id);
    assert.deepEqual(Object.keys(settings).sort(), keys, `${preset.id} settings shape`);
    assert.ok(Object.values(settings).every((value) => value !== undefined), `${preset.id} has a hole`);
    assert.equal(isClean(settings), preset.id === 'clean', `${preset.id} clean-ness`);
  }

  assert.equal(findPreset('nope').id, 'clean', 'an unknown id falls back rather than throwing');
});

test('every knob names a real setting and brackets its presets', () => {
  const settings = resolveSettings('clean');

  for (const knob of DEGRADE_KNOBS) {
    assert.ok(knob.key in settings, `${knob.key} is not a setting`);
    assert.ok(knob.min < knob.max, `${knob.key} range`);

    for (const preset of DEGRADE_PRESETS) {
      const value = resolveSettings(preset.id)[knob.key];
      assert.ok(
        value >= knob.min && value <= knob.max,
        `${preset.id} sets ${knob.key} to ${value}, outside the slider's ${knob.min}..${knob.max}`
      );
    }
  }
});

test('a seed and a preset always produce the same page', () => {
  assert.deepEqual(plan('copier'), plan('copier'), 'same seed, same everything');
  assert.notDeepEqual(plan('copier').applied.rotation, plan('copier', {}, 777).applied.rotation);
});

test('rotation is jittered and signed, not the preset number repeated', () => {
  const nominal = findPreset('copier').settings.rotation;
  const magnitudes = new Set();
  let sawBothSigns = false;
  let sawNegative = false;
  let sawPositive = false;

  for (let seed = 1_000; seed < 1_060; seed += 1) {
    const { rotation } = plan('copier', {}, seed).applied;
    magnitudes.add(Math.abs(rotation));
    sawNegative = sawNegative || rotation < 0;
    sawPositive = sawPositive || rotation > 0;
    sawBothSigns = sawNegative && sawPositive;
    assert.ok(
      Math.abs(rotation) >= nominal * 0.75 - 1e-4 && Math.abs(rotation) <= nominal * 1.25 + 1e-4,
      `seed ${seed} tilted ${rotation}, outside a quarter either way of ${nominal}`
    );
  }

  assert.ok(sawBothSigns, 'a page should tilt either way, not always clockwise');
  assert.ok(magnitudes.size > 40, 'the magnitude should vary, not snap to a handful of values');
});

test('turning one effect off does not move the others', () => {
  // Every stochastic value is drawn up front in a fixed order, so a run with
  // grain disabled tilts by exactly as much as the same run with grain on.
  const withGrain = plan('copier');
  const withoutGrain = plan('copier', { noise: 0 });

  assert.equal(withGrain.applied.rotation, withoutGrain.applied.rotation);
  assert.deepEqual(withGrain.transform, withoutGrain.transform);
});

test('a rotated page is scaled to stay inside its own sheet', () => {
  const { transform } = plan('fax');
  const corners = [[0, 0], [1, 0], [1, 1], [0, 1]].map(([x, y]) => project(transform, x, y));

  for (const [x, y] of corners) {
    assert.ok(x >= -1e-9 && x <= 1 + 1e-9, `corner ran off the sheet horizontally: ${x}`);
    assert.ok(y >= -1e-9 && y <= 1 + 1e-9, `corner ran off the sheet vertically: ${y}`);
  }

  // The centre is a fixed point of a rotation about the centre, whatever the
  // fit scale turns out to be.
  const [centreX, centreY] = project(transform, 0.5, 0.5);
  assert.ok(Math.abs(centreX - 0.5) < 1e-6, `centre drifted to ${centreX}`);
  assert.ok(Math.abs(centreY - 0.5) < 1e-6, `centre drifted to ${centreY}`);
});

test('keystone narrows the far edge and foreshortens it', () => {
  const { transform } = plan('phone', { rotation: 0, skew: 0 });
  const topWidth = project(transform, 1, 0)[0] - project(transform, 0, 0)[0];
  const bottomWidth = project(transform, 1, 1)[0] - project(transform, 0, 1)[0];

  assert.ok(bottomWidth > topWidth, 'the near edge should be the wider one');
  assert.ok(transform[2][1] !== 0, 'a keystone is projective, so the bottom row is not [0, 0, 1]');

  const upperHalf = project(transform, 0.5, 0.5)[1] - project(transform, 0.5, 0)[1];
  const lowerHalf = project(transform, 0.5, 1)[1] - project(transform, 0.5, 0.5)[1];
  assert.ok(lowerHalf > upperHalf, 'the far half should be squashed, not merely narrowed');
});

test('combined phone geometry keeps every page corner inside the sheet', () => {
  // Pure centred keystone fits even with the old scale-only implementation.
  // Rotation and skew expose its missing translation; seed 1131 is a known
  // witness, and the sweep guards the full jittered preset rather than one
  // hand-picked transform.
  const tolerance = 1e-6;

  for (let seed = 1_000; seed < 1_200; seed += 1) {
    const { transform } = plan('phone', {}, seed);
    const corners = [[0, 0], [1, 0], [1, 1], [0, 1]].map(([x, y]) => project(transform, x, y));

    for (const [x, y] of corners) {
      assert.ok(
        x >= -tolerance && x <= 1 + tolerance,
        `seed ${seed} ran off the sheet horizontally: ${x}`
      );
      assert.ok(
        y >= -tolerance && y <= 1 + tolerance,
        `seed ${seed} ran off the sheet vertically: ${y}`
      );
    }
  }
});

test('the transform is expressed in page fractions, not pixels', () => {
  // The plan is made against the 794 x 1123 layout page and applied to the 2x
  // capture. Same aspect ratio, so one normalised matrix has to serve both.
  const layout = planDegradation({ ...PAGE, preset: 'fax', seed: 99, settings: resolveSettings('fax') });
  const capture = planDegradation({
    width: PAGE.width * 2,
    height: PAGE.height * 2,
    preset: 'fax',
    seed: 99,
    settings: resolveSettings('fax')
  });

  assert.deepEqual(layout.transform, capture.transform);
  assert.notDeepEqual(layout.transformPx, capture.transformPx, 'the pixel matrices differ, as they must');

  const scaled = toPixelMatrix(layout.transform, PAGE.width * 2, PAGE.height * 2);
  for (let row = 0; row < 3; row += 1) {
    for (let column = 0; column < 3; column += 1) {
      assert.ok(
        // The normalised matrix is stored to eight places, so scaling it back
        // up by the page size lands within a thousandth of a pixel.
        Math.abs(scaled[row][column] - capture.transformPx[row][column]) < 1e-3,
        `matrix cell ${row},${column} disagrees`
      );
    }
  }
});

test('boxes follow the ink through the transform', () => {
  const { transform } = plan('fax');
  const boxes = {
    page: { width: 794, height: 1123, unit: 'normalised' },
    regions: [
      { field: 'grand_total', text: '$4,558.14', box: [0.7, 0.6, 0.15, 0.02] },
      { field: 'buyer_name', text: 'Tideline', box: [0.08, 0.2, 0.3, 0.02], words: [{ text: 'Tideline', box: [0.08, 0.2, 0.3, 0.02] }] }
    ]
  };

  const moved = transformBoxes(boxes, transform);
  const total = moved.regions[0];

  assert.notDeepEqual(total.box, boxes.regions[0].box, 'a tilted page moves its ink');
  assert.equal(total.quad.length, 8);
  assert.deepEqual(total.quad.slice(0, 2), project(transform, 0.7, 0.6).map((value) => Math.round(value * 10_000) / 10_000));

  // box stays the axis-aligned hull of quad, which is what keeps a reader
  // written against a clean run working against a degraded one.
  const xs = [total.quad[0], total.quad[2], total.quad[4], total.quad[6]];
  const ys = [total.quad[1], total.quad[3], total.quad[5], total.quad[7]];
  assert.ok(Math.abs(total.box[0] - Math.min(...xs)) < 1e-4);
  assert.ok(Math.abs(total.box[1] - Math.min(...ys)) < 1e-4);
  assert.ok(Math.abs(total.box[2] - (Math.max(...xs) - Math.min(...xs))) < 1e-4);
  assert.ok(Math.abs(total.box[3] - (Math.max(...ys) - Math.min(...ys))) < 1e-4);

  assert.ok(moved.regions[1].words[0].quad, 'word boxes move too, or they point at nothing');
  assert.notDeepEqual(moved.regions[1].words[0].box, boxes.regions[1].words[0].box);
});

test('a clean run leaves the boxes exactly as measured', () => {
  const boxes = { page: { width: 794, height: 1123, unit: 'normalised' }, regions: [{ field: 'x', text: 'x', box: [0.1, 0.1, 0.1, 0.1] }] };

  assert.equal(transformBoxes(boxes, IDENTITY_MATRIX), boxes, 'the identity should not even copy');
  assert.equal(transformBoxes(null, plan('fax').transform), null);
});

test('the pixel pass darkens, brightens, and grains a bitmap', () => {
  const flat = () => new Uint8ClampedArray([200, 200, 200, 255, 100, 100, 100, 255]);
  const settings = { ...resolveSettings('clean'), bandPeriod: 50, bandPhase: 0, lightCenter: [0.5, 0.5] };

  const brightened = flat();
  applyPixelPass(brightened, 2, 1, { ...settings, brightness: 20 }, () => 0.5);
  assert.equal(brightened[0], 220);
  assert.equal(brightened[4], 120);
  assert.equal(brightened[3], 255, 'alpha is left alone');

  const contrasted = flat();
  applyPixelPass(contrasted, 2, 1, { ...settings, contrast: 2 }, () => 0.5);
  assert.equal(contrasted[0], 255, '(200 - 128) * 2 + 128 clamps at white');
  assert.equal(contrasted[4], 72, '(100 - 128) * 2 + 128');

  const bled = flat();
  applyPixelPass(bled, 2, 1, { ...settings, bleed: 0.5 }, () => 0.5);
  assert.ok(bled[4] < 100, 'a near-black pixel is dragged further toward black');
  assert.equal(bled[0], 200, 'a paper-white pixel is above the ink ceiling and left alone');
});

test('grain is luminance, not colour speckle, and is reproducible', () => {
  const settings = { ...resolveSettings('clean'), bandPeriod: 50, bandPhase: 0, lightCenter: [0.5, 0.5], noise: 30 };
  const first = new Uint8ClampedArray([128, 128, 128, 255, 128, 128, 128, 255]);
  const second = first.slice();

  applyPixelPass(first, 2, 1, settings, createSeededRandom(7));
  applyPixelPass(second, 2, 1, settings, createSeededRandom(7));

  assert.deepEqual(first, second, 'the same seed must give the same grain');
  assert.equal(first[0], first[1], 'one draw per pixel, shared across channels');
  assert.equal(first[1], first[2]);
  assert.notEqual(first[0], first[4], 'neighbouring pixels get their own draw');
});

test('vignette and banding shade by position rather than uniformly', () => {
  const settings = { ...resolveSettings('clean'), bandPeriod: 50, bandPhase: 0, lightCenter: [0, 0] };
  const wide = new Uint8ClampedArray(4 * 4).fill(255);
  applyPixelPass(wide, 4, 1, { ...settings, vignette: 0.8 }, () => 0.5);
  assert.ok(wide[0] > wide[12], 'the corner furthest from the light should be darkest');

  const tall = new Uint8ClampedArray(4 * 40).fill(200);
  applyPixelPass(tall, 1, 40, { ...settings, banding: 0.4 }, () => 0.5);
  const rows = Array.from({ length: 40 }, (_value, index) => tall[index * 4]);
  assert.ok(Math.max(...rows) - Math.min(...rows) > 20, 'bands should be visible across the page');
});

test('greyscale drains the colour a fax could never carry', () => {
  const settings = { ...resolveSettings('clean'), bandPeriod: 50, bandPhase: 0, lightCenter: [0.5, 0.5] };
  const orange = () => new Uint8ClampedArray([198, 74, 22, 255]);

  const full = orange();
  applyPixelPass(full, 1, 1, { ...settings, mono: 1 }, () => 0.5);
  assert.equal(full[0], full[1], 'a fully desaturated pixel has one value');
  assert.equal(full[1], full[2]);
  // Rec. 601 luma of the vendor accent, rounded by the clamped array.
  assert.equal(full[0], Math.round(0.299 * 198 + 0.587 * 74 + 0.114 * 22));

  const half = orange();
  applyPixelPass(half, 1, 1, { ...settings, mono: 0.5 }, () => 0.5);
  assert.ok(half[0] > half[1] && half[1] > half[2], 'half way keeps the hue, muted');
  assert.ok(half[0] < 198, 'and the accent has moved toward the grey');
});

test('a hard threshold pushes a mid grey to one side or the other', () => {
  const settings = { ...resolveSettings('clean'), bandPeriod: 50, bandPhase: 0, lightCenter: [0.5, 0.5], threshold: 0.5 };
  const data = new Uint8ClampedArray([170, 170, 170, 255, 80, 80, 80, 255]);
  applyPixelPass(data, 2, 1, settings, () => 0.5);

  assert.ok(data[0] > 170, 'above the cut, toward paper');
  assert.ok(data[4] < 80, 'below the cut, toward ink');
});

test('degrading a canvas draws the source once through an affine transform', () => {
  const { canvases, documentObj } = createFakeCanvasDocument();
  const source = createFakeCanvas(40, 56);
  const degradation = plan('light_scan');
  const output = degradeCanvas(source, degradation, { documentObj });

  assert.equal(canvases.length, 1);
  assert.equal(output.width, 40);
  assert.equal(output.height, 56);

  const names = output.ctx.calls.map((call) => call.name);
  assert.ok(names.includes('fillRect'), 'the sheet is filled before the page lands on it');
  assert.equal(output.ctx.calls.filter((call) => call.name === 'drawImage').length, 1);
  assert.ok(names.indexOf('getImageData') < names.indexOf('putImageData'));

  const transform = output.ctx.calls.find((call) => call.name === 'setTransform');
  assert.ok(Math.abs(transform.args[1]) > 0, 'a rotated page has a non-zero shear term');
});

test('a keystoned page is drawn in strips, because canvas cannot warp in one call', () => {
  const { documentObj } = createFakeCanvasDocument();
  const source = createFakeCanvas(40, 56);
  const output = degradeCanvas(source, plan('phone'), { documentObj });
  const draws = output.ctx.calls.filter((call) => call.name === 'drawImage');

  assert.equal(draws.length, Math.ceil(56 / 4), 'one draw per four-pixel strip');
  assert.ok(draws.every((call) => call.args.length === 9), 'strips draw a source rect into a dest rect');
  // Strips march down the page and cover all of it, with no gap between them.
  assert.equal(draws[0].args[2], 0);
  assert.equal(draws.at(-1).args[2] + draws.at(-1).args[4], 56);
});

test('the blur filter is lifted before the artifacts are painted', () => {
  const { documentObj } = createFakeCanvasDocument();
  const output = degradeCanvas(createFakeCanvas(40, 56), plan('copier'), { documentObj });

  // Dust drawn through the page blur would be blurred dust, which is not what a
  // speck on the platen looks like.
  assert.equal(output.ctx.filter, 'none');
  assert.ok(output.ctx.calls.some((call) => call.name === 'arc'), 'copier paper has dust and punch holes');
});

test('each artifact only appears when its preset asks for it', () => {
  const { documentObj } = createFakeCanvasDocument();
  const strokesFor = (preset) =>
    degradeCanvas(createFakeCanvas(40, 56), plan(preset), { documentObj })
      .ctx.calls.map((call) => call.name);

  assert.ok(strokesFor('fax').includes('lineTo'), 'the fax preset creases the page');
  assert.ok(strokesFor('phone').includes('createLinearGradient'), 'an edge shadow is a gradient');
  assert.ok(!strokesFor('clean').includes('arc'), 'a clean page picks up nothing');
});

test('a lossy preset writes a JPEG and says so', () => {
  const { documentObj } = createFakeCanvasDocument();
  const degradation = plan('fax');
  const output = degradeCanvas(createFakeCanvas(20, 28), degradation, { documentObj });
  const encoded = encodeCanvas(output, degradation.applied);

  assert.equal(encoded.extension, 'jpg');
  assert.equal(encoded.mime, 'image/jpeg');
  assert.deepEqual(output.encodings, [{ mime: 'image/jpeg', quality: degradation.applied.jpeg }]);

  const lossless = encodeCanvas(createFakeCanvas(20, 28), resolveSettings('clean'));
  assert.equal(lossless.extension, 'png');
});

test('where a degraded rendering exists is a published constant', () => {
  assert.deepEqual(DEGRADATION_APPLIES_TO, ['png', 'pdf_raster']);
});

test('a zero-sized page still produces finite numbers', () => {
  const degenerate = planDegradation({ width: 0, height: 0, preset: 'fax', seed: 3, settings: resolveSettings('fax') });

  assert.ok(degenerate.transform.every((row) => row.every(Number.isFinite)));
  assert.ok(degenerate.transformPx.every((row) => row.every(Number.isFinite)));
});
