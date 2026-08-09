/**
 * Turns a clean render into something that looks like it came off a scanner.
 *
 * A corpus where every page is a pixel-perfect 2x raster on pure white cannot
 * tell you where an extractor breaks, because nothing in it is hard. This module
 * is the axis that makes the "how much accuracy do I lose to scan quality"
 * measurement possible at all: the same seed, rendered clean and rendered
 * degraded, differing only in the pixels.
 *
 * Two contracts hold, and both matter more than any individual effect.
 *
 * **Degradation is seeded.** Every stochastic choice is drawn from the document
 * seed, in a fixed order, so a given seed plus a given preset always produces
 * the same page. A dataset that cannot be regenerated is not a dataset.
 *
 * **Degradation reports the geometry it applied.** Skew, rotation, and keystone
 * move the ink; noise, blur, and JPEG do not. `planDegradation` returns the
 * projective transform it is about to apply, in normalised page coordinates, so
 * the annotation payload can run every box through it before serialising.
 * Without that, this module would quietly corrupt the boxes, which is exactly
 * the kind of bug that ships because both halves test fine in isolation.
 *
 * Planning is deliberately split from painting. `planDegradation` is pure
 * arithmetic over a seed and a page size, so the JSON-only batch path can
 * transform its boxes without ever rasterising anything.
 *
 * @module degrade
 */

import { createSeededRandom } from "./random.js";

/**
 * @typedef {[[number, number, number], [number, number, number], [number, number, number]]} Matrix3
 * @typedef {{
 *   banding: number,
 *   bleed: number,
 *   blur: number,
 *   brightness: number,
 *   coffee: boolean,
 *   contrast: number,
 *   dust: number,
 *   edgeShadow: number,
 *   fold: boolean,
 *   jpeg: number,
 *   keystone: number,
 *   mono: number,
 *   noise: number,
 *   punch: boolean,
 *   rotation: number,
 *   skew: number,
 *   staple: boolean,
 *   threshold: number,
 *   vignette: number
 * }} DegradeSettings
 * @typedef {DegradeSettings & {
 *   bandPeriod: number,
 *   bandPhase: number,
 *   lightCenter: [number, number]
 * }} AppliedSettings
 * @typedef {{
 *   applied: AppliedSettings,
 *   preset: string,
 *   seed: number,
 *   transform: Matrix3,
 *   transformPx: Matrix3
 * }} DegradePlan
 */

/** Offset mixed into the document seed, so degradation draws its own stream. */
const SEED_OFFSET = 9_001;

/** Identity in both coordinate spaces; the transform a clean page reports. */
export const IDENTITY_MATRIX = /** @type {Matrix3} */ ([
  [1, 0, 0],
  [0, 1, 0],
  [0, 0, 1]
]);

/** Where a degraded rendering exists at all, recorded on the payload. */
export const DEGRADATION_APPLIES_TO = ["png", "pdf_raster"];

/** Settings a clean page runs under, and the base every preset overrides. */
const CLEAN = /** @type {DegradeSettings} */ ({
  banding: 0,
  bleed: 0,
  blur: 0,
  brightness: 0,
  coffee: false,
  contrast: 1,
  dust: 0,
  edgeShadow: 0,
  fold: false,
  jpeg: 1,
  keystone: 0,
  mono: 0,
  noise: 0,
  punch: false,
  rotation: 0,
  skew: 0,
  staple: false,
  threshold: 0,
  vignette: 0
});

/**
 * The presets, in the order the rail lists them.
 *
 * Each is a rough physical story rather than a set of numbers picked to look
 * pretty: a desk scanner that is basically fine, a shared office copier with a
 * dirty platen, a thermal fax that has thrown away most of the greyscale, and a
 * phone held at an angle under a ceiling light.
 */
export const DEGRADE_PRESETS = [
  {
    id: "clean",
    label: "Clean",
    note: "The render is unchanged. No geometry, no grain, lossless PNG.",
    settings: {}
  },
  {
    id: "light_scan",
    label: "Light scan",
    note: "A desk scanner behaving itself: a hair of skew, mild grain, light JPEG.",
    settings: { rotation: 0.4, blur: 0.3, contrast: 1.08, brightness: -4, noise: 6, edgeShadow: 0.15, dust: 6, jpeg: 0.92 }
  },
  {
    id: "copier",
    label: "Office copier",
    note: "Blown highlights, visible grain, dust on the platen, punched and stapled.",
    settings: {
      rotation: 1.1,
      skew: 0.3,
      blur: 0.6,
      contrast: 1.35,
      brightness: 10,
      noise: 14,
      banding: 0.05,
      vignette: 0.12,
      edgeShadow: 0.45,
      dust: 40,
      punch: true,
      staple: true,
      jpeg: 0.82
    }
  },
  {
    id: "fax",
    label: "Bad fax",
    note: "Monochrome, most of the greyscale gone. Strokes bleed, bands run across.",
    settings: {
      mono: 1,
      rotation: 1.8,
      skew: 0.8,
      blur: 0.9,
      contrast: 1.9,
      brightness: -6,
      noise: 10,
      bleed: 0.55,
      threshold: 0.22,
      banding: 0.14,
      edgeShadow: 0.3,
      dust: 25,
      fold: true,
      jpeg: 0.6
    }
  },
  {
    id: "phone",
    label: "Phone photo",
    note: "Held at an angle under one light: keystone, uneven exposure, heavy JPEG.",
    settings: {
      rotation: 2.4,
      keystone: 0.09,
      blur: 0.8,
      contrast: 1.15,
      brightness: -8,
      noise: 12,
      banding: 0.04,
      vignette: 0.5,
      edgeShadow: 0.2,
      dust: 10,
      coffee: true,
      jpeg: 0.7
    }
  }
];

/**
 * The subset of settings the custom panel exposes as sliders.
 *
 * Not every knob: a rail with eighteen sliders in it is a rail nobody reads.
 * These are the ones that change what an extractor sees the most, and anything
 * left out still moves when the preset changes.
 */
export const DEGRADE_KNOBS = [
  { key: "rotation", label: "Rotation", min: 0, max: 5, step: 0.1, unit: "°" },
  { key: "skew", label: "Skew", min: 0, max: 3, step: 0.1, unit: "°" },
  { key: "keystone", label: "Keystone", min: 0, max: 0.2, step: 0.01, unit: "" },
  { key: "blur", label: "Blur", min: 0, max: 3, step: 0.1, unit: "px" },
  { key: "contrast", label: "Contrast", min: 0.6, max: 2.2, step: 0.05, unit: "x" },
  { key: "mono", label: "Greyscale", min: 0, max: 1, step: 0.05, unit: "" },
  { key: "noise", label: "Grain", min: 0, max: 40, step: 1, unit: "" },
  { key: "bleed", label: "Ink bleed", min: 0, max: 1, step: 0.05, unit: "" },
  { key: "jpeg", label: "JPEG quality", min: 0.3, max: 1, step: 0.05, unit: "" }
];

/**
 * Look up a preset by id, falling back to clean.
 * @param {string} id - Preset id.
 * @returns {(typeof DEGRADE_PRESETS)[number]} The preset.
 */
export function findPreset(id) {
  return DEGRADE_PRESETS.find((preset) => preset.id === id) ?? DEGRADE_PRESETS[0];
}

/**
 * Resolve a preset id plus any overrides into a complete settings object.
 * @param {string} presetId - Preset to start from.
 * @param {Partial<DegradeSettings>} [overrides={}] - Custom knob values.
 * @returns {DegradeSettings} Every setting, with nothing left undefined.
 */
export function resolveSettings(presetId, overrides = {}) {
  return { ...CLEAN, ...findPreset(presetId).settings, ...overrides };
}

/**
 * Whether a settings object would change a single pixel.
 * @param {DegradeSettings} settings - Resolved settings.
 * @returns {boolean} True when the page would come out untouched.
 */
export function isClean(settings) {
  return /** @type {(keyof DegradeSettings)[]} */ (Object.keys(CLEAN)).every(
    (key) => settings[key] === CLEAN[key]
  );
}

/**
 * Multiply two 3x3 matrices.
 * @param {Matrix3} a - Left matrix.
 * @param {Matrix3} b - Right matrix.
 * @returns {Matrix3} The product `a · b`.
 */
function multiply(a, b) {
  return /** @type {Matrix3} */ (
    a.map((row) => b[0].map((_column, index) => row[0] * b[0][index] + row[1] * b[1][index] + row[2] * b[2][index]))
  );
}

/**
 * Map a point through a projective matrix.
 * @param {Matrix3} m - Transform.
 * @param {number} x - Source x.
 * @param {number} y - Source y.
 * @returns {[number, number]} Destination point.
 */
export function project(m, x, y) {
  const w = m[2][0] * x + m[2][1] * y + m[2][2] || 1;
  return [(m[0][0] * x + m[0][1] * y + m[0][2]) / w, (m[1][0] * x + m[1][1] * y + m[1][2]) / w];
}

/**
 * Conjugate a transform so it operates about a point rather than the origin.
 * @param {Matrix3} m - Transform about the origin.
 * @param {number} cx - Centre x.
 * @param {number} cy - Centre y.
 * @returns {Matrix3} The same transform, about `(cx, cy)`.
 */
function about(m, cx, cy) {
  const to = /** @type {Matrix3} */ ([[1, 0, cx], [0, 1, cy], [0, 0, 1]]);
  const from = /** @type {Matrix3} */ ([[1, 0, -cx], [0, 1, -cy], [0, 0, 1]]);
  return multiply(to, multiply(m, from));
}

/**
 * Jitter a nominal magnitude and give it a sign.
 *
 * A preset that always tilted 1.1 degrees clockwise would teach a model the
 * preset rather than the effect, so the magnitude varies by a quarter either way
 * and the direction is a coin flip off the document's own seed.
 * @param {number} nominal - Preset magnitude.
 * @param {() => number} random - Seeded stream.
 * @returns {number} Signed, jittered magnitude.
 */
function jitter(nominal, random) {
  const magnitude = nominal * (0.75 + random() * 0.5);
  return random() < 0.5 ? -magnitude : magnitude;
}

/**
 * Work out the geometry and the seeded choices for one degraded page.
 *
 * Pure: no canvas, no DOM. The JSON-only batch path calls this and nothing else,
 * which is what lets a labels-only run transform its boxes correctly without
 * rasterising a single page.
 * @param {{
 *   height: number,
 *   preset?: string,
 *   seed: number,
 *   settings: DegradeSettings,
 *   width: number
 * }} options - Page size, seed, and resolved settings.
 * @returns {DegradePlan} The transform, plus every value actually used.
 */
export function planDegradation({ height, preset = "custom", seed, settings, width }) {
  const random = createSeededRandom(seed + SEED_OFFSET);
  // Drawn unconditionally and in a fixed order, so turning one effect off never
  // shifts the stream underneath the others.
  const rotation = jitter(settings.rotation, random);
  const skew = jitter(settings.skew, random);
  const bandPhase = random() * Math.PI * 2;
  const bandPeriod = 40 + random() * 90;
  const lightCenter = /** @type {[number, number]} */ ([0.3 + random() * 0.4, 0.25 + random() * 0.4]);
  const applied = /** @type {AppliedSettings} */ ({
    ...settings,
    rotation: round4(rotation),
    skew: round4(skew),
    bandPhase: round4(bandPhase),
    bandPeriod: round4(bandPeriod),
    lightCenter: [round4(lightCenter[0]), round4(lightCenter[1])]
  });

  const centreX = width / 2;
  const centreY = height / 2;
  const radians = (applied.rotation * Math.PI) / 180;
  const shearRadians = (applied.skew * Math.PI) / 180;
  const cos = Math.cos(radians);
  const sin = Math.sin(radians);
  // Keystone as a real projective map rather than a horizontal squeeze: tilting
  // a page away from the lens narrows the far edge *and* foreshortens it, and a
  // model trained on a squeeze alone would not have seen the second half.
  const gradient = centreY ? settings.keystone / centreY : 0;
  const base = multiply(
    /** @type {Matrix3} */ ([[1, 0, 0], [0, 1, 0], [0, -gradient, 1]]),
    multiply(
      /** @type {Matrix3} */ ([[cos, -sin, 0], [sin, cos, 0], [0, 0, 1]]),
      /** @type {Matrix3} */ ([[1, Math.tan(shearRadians), 0], [0, 1, 0], [0, 0, 1]])
    )
  );
  const centred = about(base, centreX, centreY);
  const fit = fitTransform(centred, width, height);
  const transformPx = multiply(fit, centred);

  return {
    applied,
    preset,
    seed,
    transform: toNormalised(transformPx, width, height),
    transformPx
  };
}

/**
 * Scale and centre the transformed page so it still fits its own frame.
 *
 * Rotating a page inside a fixed canvas would otherwise slice the corners off.
 * A projective transform also moves the bounding box away from the page centre,
 * so scaling about the old centre is not sufficient for a keystoned page.
 * @param {Matrix3} m - Transform before fitting.
 * @param {number} width - Page width.
 * @param {number} height - Page height.
 * @returns {Matrix3} Scale and translation that centre the transformed page.
 */
function fitTransform(m, width, height) {
  const corners = [[0, 0], [width, 0], [width, height], [0, height]].map(([x, y]) => project(m, x, y));
  const xs = corners.map((point) => point[0]);
  const ys = corners.map((point) => point[1]);
  const minX = Math.min(...xs);
  const minY = Math.min(...ys);
  const spanX = Math.max(...xs) - minX;
  const spanY = Math.max(...ys) - minY;
  // A page with no measurable size has nothing to overflow, so it needs no
  // shrinking; guarding here keeps a detached preview out of 0/0.
  const scale = Math.min(1, spanX ? width / spanX : 1, spanY ? height / spanY : 1);
  const left = (width - spanX * scale) / 2;
  const top = (height - spanY * scale) / 2;

  return /** @type {Matrix3} */ ([[scale, 0, left - minX * scale], [0, scale, top - minY * scale], [0, 0, 1]]);
}

/**
 * Re-express a pixel-space transform in 0..1 page coordinates.
 *
 * The boxes are normalised, so the matrix that moves them has to be too.
 * Conjugating by the page size is what keeps the two in the same units.
 * @param {Matrix3} m - Transform in pixels.
 * @param {number} width - Page width.
 * @param {number} height - Page height.
 * @returns {Matrix3} The same transform over normalised coordinates.
 */
function toNormalised(m, width, height) {
  const scale = /** @type {Matrix3} */ ([[width, 0, 0], [0, height, 0], [0, 0, 1]]);
  const inverse = /** @type {Matrix3} */ ([[1 / (width || 1), 0, 0], [0, 1 / (height || 1), 0], [0, 0, 1]]);
  return /** @type {Matrix3} */ (
    multiply(inverse, multiply(m, scale)).map((row) => row.map(round8))
  );
}

/**
 * Re-express a normalised transform in the pixels of a given bitmap.
 *
 * The plan is made against the layout page (794 x 1123) but applied to the 2x
 * capture (1588 x 2246). Normalised coordinates are what let one plan serve
 * both: the matrix is scaled into whatever bitmap is actually in hand at draw
 * time, so nothing has to know the capture scale.
 * @param {Matrix3} m - Transform over normalised coordinates.
 * @param {number} width - Bitmap width.
 * @param {number} height - Bitmap height.
 * @returns {Matrix3} The same transform in pixels.
 */
export function toPixelMatrix(m, width, height) {
  const scale = /** @type {Matrix3} */ ([[width, 0, 0], [0, height, 0], [0, 0, 1]]);
  const inverse = /** @type {Matrix3} */ ([[1 / (width || 1), 0, 0], [0, 1 / (height || 1), 0], [0, 0, 1]]);
  return multiply(scale, multiply(m, inverse));
}

/**
 * @param {number} value - Raw number.
 * @returns {number} Rounded to four places.
 */
function round4(value) {
  return Math.round(value * 10_000) / 10_000;
}

/**
 * @param {number} value - Raw number.
 * @returns {number} Rounded to eight places, which is exact enough for a matrix.
 */
function round8(value) {
  return Math.round(value * 100_000_000) / 100_000_000;
}

/** Above this grey, a pixel is paper rather than ink, for the bleed curve. */
const INK_CEILING = 190;

/**
 * Apply every per-pixel effect in one pass over the bitmap.
 *
 * One pass rather than one per effect: this runs over roughly fourteen million
 * bytes for a 2x A4 page, and walking that five times is the difference between
 * a batch you can leave running and a tab that stops responding.
 *
 * Exported separately from the canvas work so it can be tested on a bitmap small
 * enough to assert on by hand.
 * @param {Uint8ClampedArray} data - RGBA bytes, modified in place.
 * @param {number} width - Bitmap width in pixels.
 * @param {number} height - Bitmap height in pixels.
 * @param {AppliedSettings} applied - Resolved settings from `planDegradation`.
 * @param {() => number} random - Seeded stream for the grain.
 * @returns {void}
 */
export function applyPixelPass(data, width, height, applied, random) {
  const { banding, bandPeriod, bandPhase, bleed, brightness, contrast, lightCenter, mono, noise, threshold, vignette } =
    applied;
  const lightX = lightCenter[0] * width;
  const lightY = lightCenter[1] * height;
  const farX = Math.max(lightX, width - lightX);
  const farY = Math.max(lightY, height - lightY);
  const farthest = farX * farX + farY * farY || 1;
  const cut = 255 * (0.45 + threshold * 0.2);

  for (let y = 0; y < height; y += 1) {
    const band = banding ? 1 - banding * (0.5 + 0.5 * Math.sin(bandPhase + y / bandPeriod)) : 1;
    const dy = y - lightY;

    for (let x = 0; x < width; x += 1) {
      const index = (y * width + x) * 4;
      const dx = x - lightX;
      const shade = vignette ? band * (1 - (vignette * (dx * dx + dy * dy)) / farthest) : band;
      // One draw per pixel, shared across the three channels: a scanner adds
      // luminance grain, and drawing per channel would produce colour speckle
      // on what is meant to be a greyscale page.
      const grain = noise ? (random() + random() - 1) * noise : 0;
      // Rec. 601 luma, because a fax has no colour to reproduce and an accent
      // that survives into a monochrome scan is the one thing that gives a
      // synthetic page away.
      const luma = mono ? 0.299 * data[index] + 0.587 * data[index + 1] + 0.114 * data[index + 2] : 0;

      for (let channel = 0; channel < 3; channel += 1) {
        const source = data[index + channel];
        let value = (mono ? source + (luma - source) * mono : source) * shade;
        value = (value - 128) * contrast + 128 + brightness + grain;

        if (bleed && value < INK_CEILING) {
          // Ink spreading into the paper around a stroke: the closer a pixel
          // already is to black, the further this drags it, which thickens
          // strokes instead of merely darkening the whole page.
          value -= bleed * (INK_CEILING - value) * 0.6;
        }

        if (threshold) {
          value = value < cut ? value * (1 - threshold) : value + (255 - value) * threshold;
        }

        data[index + channel] = value;
      }
    }
  }
}

/**
 * How tall each strip is when a keystone forces a piecewise draw.
 *
 * Canvas 2D cannot draw a projective transform in one call. Strips of a few
 * pixels approximate it to well under a pixel of error, which is far below the
 * blur and grain applied immediately afterwards, and the matrix reported to the
 * annotations is the exact projective one either way.
 */
const KEYSTONE_STRIP = 4;

/**
 * Draw the source through the plan's geometry.
 * @param {CanvasRenderingContext2D} ctx - Destination context.
 * @param {HTMLCanvasElement} source - Clean render.
 * @param {Matrix3} transformPx - Geometry to apply, in the source's own pixels.
 * @returns {void}
 */
function drawGeometry(ctx, source, transformPx) {
  const { height, width } = source;

  if (!transformPx[2][0] && !transformPx[2][1]) {
    ctx.setTransform(transformPx[0][0], transformPx[1][0], transformPx[0][1], transformPx[1][1], transformPx[0][2], transformPx[1][2]);
    ctx.drawImage(source, 0, 0);
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    return;
  }

  for (let top = 0; top < height; top += KEYSTONE_STRIP) {
    const strip = Math.min(KEYSTONE_STRIP, height - top);
    const bottom = top + strip;
    const [leftTopX, leftTopY] = project(transformPx, 0, top);
    const [rightTopX, rightTopY] = project(transformPx, width, top);
    const [leftBottomX, leftBottomY] = project(transformPx, 0, bottom);
    const a = (rightTopX - leftTopX) / width;
    const b = (rightTopY - leftTopY) / width;
    const c = (leftBottomX - leftTopX) / strip;
    const d = (leftBottomY - leftTopY) / strip;

    ctx.setTransform(a, b, c, d, leftTopX - c * top, leftTopY - d * top);
    // One pixel of overlap, so neighbouring strips meet without a hairline of
    // background showing through where the rounding falls badly.
    ctx.drawImage(source, 0, top, width, Math.min(strip + 1, height - top), 0, top, width, Math.min(strip + 1, height - top));
  }

  ctx.setTransform(1, 0, 0, 1, 0, 0);
}

/**
 * Paint the physical marks a page picks up before it reaches a scanner.
 * @param {CanvasRenderingContext2D} ctx - Destination context.
 * @param {AppliedSettings} applied - Resolved settings.
 * @param {number} width - Canvas width.
 * @param {number} height - Canvas height.
 * @param {() => number} random - Seeded stream.
 * @returns {void}
 */
function drawArtifacts(ctx, applied, width, height, random) {
  ctx.save();

  for (let index = 0; index < applied.dust; index += 1) {
    const radius = 0.6 + random() * 2.4;
    ctx.fillStyle = `rgba(30, 30, 30, ${0.15 + random() * 0.45})`;
    ctx.beginPath();
    ctx.arc(random() * width, random() * height, radius, 0, Math.PI * 2);
    ctx.fill();
  }

  if (applied.fold) {
    const y = height * (0.32 + random() * 0.36);
    ctx.strokeStyle = "rgba(0, 0, 0, 0.16)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y + (random() - 0.5) * 6);
    ctx.stroke();
  }

  if (applied.punch) {
    const x = width * 0.035;
    for (const fraction of [0.28, 0.5, 0.72]) {
      ctx.fillStyle = "rgba(24, 24, 24, 0.82)";
      ctx.beginPath();
      ctx.arc(x, height * fraction, width * 0.011, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  if (applied.staple) {
    ctx.strokeStyle = "rgba(40, 40, 40, 0.55)";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(width * 0.05, height * 0.045);
    ctx.lineTo(width * 0.085, height * 0.028);
    ctx.stroke();
  }

  if (applied.coffee) {
    const cx = width * (0.55 + random() * 0.3);
    const cy = height * (0.55 + random() * 0.3);
    const radius = width * (0.07 + random() * 0.05);
    ctx.strokeStyle = "rgba(120, 82, 40, 0.22)";
    ctx.lineWidth = width * 0.008;
    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.stroke();
    ctx.fillStyle = "rgba(120, 82, 40, 0.06)";
    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.fill();
  }

  ctx.restore();
}

/**
 * Darken the page edges the way a lid that does not quite close does.
 * @param {CanvasRenderingContext2D} ctx - Destination context.
 * @param {number} strength - Shadow strength, 0 to 1.
 * @param {number} width - Canvas width.
 * @param {number} height - Canvas height.
 * @returns {void}
 */
function drawEdgeShadow(ctx, strength, width, height) {
  const depth = Math.max(width, height) * 0.05;
  /** @type {[number, number, number, number][]} */
  const edges = [
    [0, 0, depth, 0],
    [width, 0, width - depth, 0],
    [0, 0, 0, depth],
    [0, height, 0, height - depth]
  ];

  ctx.save();

  for (const [x0, y0, x1, y1] of edges) {
    const gradient = ctx.createLinearGradient(x0, y0, x1, y1);
    gradient.addColorStop(0, `rgba(0, 0, 0, ${strength * 0.55})`);
    gradient.addColorStop(1, "rgba(0, 0, 0, 0)");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, width, height);
  }

  ctx.restore();
}

/**
 * Render a degraded copy of a clean page capture.
 *
 * The source canvas is never modified, because pair mode writes both.
 * @param {HTMLCanvasElement} source - Clean 2x render from `capturePaper`.
 * @param {DegradePlan} plan - Output of `planDegradation` for the same page.
 * @param {{ documentObj?: Document }} [options={}] - DOM injection point.
 * @returns {HTMLCanvasElement} A new canvas holding the degraded page.
 */
export function degradeCanvas(source, plan, { documentObj = document } = {}) {
  const { applied } = plan;
  const random = createSeededRandom(plan.seed + SEED_OFFSET);
  const canvas = documentObj.createElement("canvas");
  canvas.width = source.width;
  canvas.height = source.height;
  const ctx = /** @type {CanvasRenderingContext2D} */ (canvas.getContext("2d"));

  // The page is smaller than the sheet once it has been rotated to fit, so the
  // background is what shows in the corners. Scanner white, not pure white.
  ctx.fillStyle = "rgb(246, 245, 242)";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  if (applied.blur) {
    ctx.filter = `blur(${applied.blur}px)`;
  }

  drawGeometry(ctx, source, toPixelMatrix(plan.transform, source.width, source.height));
  ctx.filter = "none";
  drawArtifacts(ctx, applied, canvas.width, canvas.height, random);

  if (applied.edgeShadow) {
    drawEdgeShadow(ctx, applied.edgeShadow, canvas.width, canvas.height);
  }

  const image = ctx.getImageData(0, 0, canvas.width, canvas.height);
  applyPixelPass(image.data, canvas.width, canvas.height, applied, random);
  ctx.putImageData(image, 0, 0);

  return canvas;
}

/**
 * Choose the image encoding a set of settings implies.
 *
 * JPEG loss is not painted onto the bitmap, it is the encoding: asking a canvas
 * for a lossy JPEG is the same compression a real scanner applies, and baking it
 * into a PNG would mean an async round-trip through an `Image` for a worse
 * result.
 * @param {DegradeSettings | AppliedSettings} settings - Resolved settings.
 * @returns {{ extension: string, mime: string, quality: number }} Encoding to use.
 */
export function imageEncoding(settings) {
  return settings.jpeg < 1
    ? { extension: "jpg", mime: "image/jpeg", quality: settings.jpeg }
    : { extension: "png", mime: "image/png", quality: 1 };
}

/**
 * Encode a canvas under the encoding its settings imply.
 * @param {HTMLCanvasElement} canvas - Canvas to encode.
 * @param {DegradeSettings | AppliedSettings} settings - Resolved settings.
 * @returns {{ dataUrl: string, extension: string, mime: string }} Encoded image.
 */
export function encodeCanvas(canvas, settings) {
  const { extension, mime, quality } = imageEncoding(settings);
  return { dataUrl: canvas.toDataURL(mime, quality), extension, mime };
}
