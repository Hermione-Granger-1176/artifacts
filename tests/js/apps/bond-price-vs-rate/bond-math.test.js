import assert from 'node:assert/strict';
import test from 'node:test';

import {
  YIELD_CURVES,
  bondAnalytics,
  bondPrice,
  bondSchedule,
  curveYieldPct,
  priceRegime
} from '../../../../apps/bond-price-vs-rate/js/modules/bond-math.js';

// The canonical bond used across the fixtures: 10-year, 5% annual coupon, $1000 face.
const PAR = { faceValue: 1000, couponRatePct: 5, years: 10, frequency: 1 };
const ZERO = { faceValue: 1000, couponRatePct: 0, years: 10, frequency: 1 };

function priceAt(bond, annualYieldPct) {
  return bondPrice({ ...bond, annualYieldPct });
}

// --- prices ---

test('prices the coupon bond across rates to within a cent', () => {
  assert.ok(Math.abs(priceAt(PAR, 3) - 1170.60) < 0.01);
  assert.ok(Math.abs(priceAt(PAR, 4) - 1081.11) < 0.01);
  assert.ok(Math.abs(priceAt(PAR, 5) - 1000.00) < 0.01);
  assert.ok(Math.abs(priceAt(PAR, 6) - 926.40) < 0.01);
  assert.ok(Math.abs(priceAt(PAR, 7) - 859.53) < 0.01);
});

test('prices the zero-coupon bond across rates to within a cent', () => {
  assert.ok(Math.abs(priceAt(ZERO, 3) - 744.09) < 0.01);
  assert.ok(Math.abs(priceAt(ZERO, 5) - 613.91) < 0.01);
  assert.ok(Math.abs(priceAt(ZERO, 7) - 508.35) < 0.01);
});

test('price falls as the market rate rises (the inverse relationship)', () => {
  assert.ok(priceAt(PAR, 3) > priceAt(PAR, 5));
  assert.ok(priceAt(PAR, 5) > priceAt(PAR, 7));
});

test('a par bond prices to exactly its face value when rate equals coupon', () => {
  assert.ok(Math.abs(priceAt(PAR, 5) - PAR.faceValue) < 1e-9);
});

test('a one-year bond prices to (coupon + face) discounted once', () => {
  const price = bondPrice({ faceValue: 1000, couponRatePct: 5, years: 1, frequency: 1, annualYieldPct: 8 });
  assert.ok(Math.abs(price - 1050 / 1.08) < 1e-9);
});

// --- schedule ---

test('bondSchedule returns one discounted row per coupon period', () => {
  const schedule = bondSchedule({ ...PAR, annualYieldPct: 5 });
  assert.equal(schedule.length, PAR.years);
  assert.equal(schedule[0].period, 1);
  assert.equal(schedule[0].timeYears, 1);
});

test('bondSchedule merges the face repayment into the final period amount', () => {
  const schedule = bondSchedule({ ...PAR, annualYieldPct: 6 });
  // Every coupon period pays 50; only the last also returns the 1000 face.
  assert.equal(schedule[0].amount, 50);
  assert.equal(schedule[schedule.length - 1].amount, 1050);
});

test('bondSchedule discount factors are 1/(1+r)^t and the first 5% factor is 0.9524', () => {
  const schedule = bondSchedule({ ...PAR, annualYieldPct: 5 });
  for (const row of schedule) {
    assert.ok(Math.abs(row.discountFactor - 1 / 1.05 ** row.period) < 1e-12);
    assert.ok(Math.abs(row.presentValue - row.amount * row.discountFactor) < 1e-12);
  }
  assert.equal(schedule[0].discountFactor.toFixed(4), '0.9524');
});

test('bondSchedule present values sum to the bond price', () => {
  const bond = { ...PAR, annualYieldPct: 6 };
  const total = bondSchedule(bond).reduce((sum, row) => sum + row.presentValue, 0);
  assert.ok(Math.abs(total - bondPrice(bond)) < 1e-9);
});

// --- analytics ---

test('a zero-coupon bond has Macaulay duration equal to its maturity', () => {
  const analytics = bondAnalytics({ ...ZERO, annualYieldPct: 5 });
  assert.ok(Math.abs(analytics.macaulayYears - 10) < 1e-9);
  assert.ok(Math.abs(analytics.modifiedYears - 10 / 1.05) < 1e-9);
  // Zero-coupon convexity closed form: n(n+1)/(1+y)^2.
  assert.ok(Math.abs(analytics.convexity - 110 / 1.05 ** 2) < 1e-9);
  assert.ok(Math.abs(analytics.pvCoupons) < 1e-9);
  assert.ok(Math.abs(analytics.pvFace - analytics.price) < 1e-9);
});

test('a par bond matches the closed-form Macaulay duration and coupon current yield', () => {
  const analytics = bondAnalytics({ ...PAR, annualYieldPct: 5 });
  // Par-bond closed form: (1+y)/y * (1 - (1+y)^-n).
  const closedForm = (1.05 / 0.05) * (1 - 1.05 ** -10);
  assert.ok(Math.abs(analytics.macaulayYears - closedForm) < 1e-9);
  assert.ok(Math.abs(analytics.currentYieldPct - 5) < 1e-9);
});

test('the discount-bond analytics match the reference fixtures', () => {
  const analytics = bondAnalytics({ ...PAR, annualYieldPct: 6 });
  assert.ok(Math.abs(analytics.price - 926.40) < 0.01);
  assert.ok(Math.abs(analytics.pvFace - 558.39) < 0.01);
  assert.ok(Math.abs(analytics.pvCoupons - 368.00) < 0.01);
  assert.ok(Math.abs(analytics.currentYieldPct - 5.397) < 0.001);
  assert.ok(Math.abs(analytics.macaulayYears - 8.02) < 0.01);
  assert.ok(Math.abs(analytics.modifiedYears - 7.57) < 0.01);
  assert.ok(Math.abs(analytics.convexity - 72.57) < 0.01);
  assert.ok(Math.abs(analytics.dv01 - 0.70) < 0.01);
});

test('the price decomposition sums to the price', () => {
  const analytics = bondAnalytics({ ...PAR, annualYieldPct: 7 });
  assert.ok(Math.abs(analytics.pvCoupons + analytics.pvFace - analytics.price) < 1e-9);
});

test('DV01 approximates the exact one-basis-point reprice', () => {
  const bond = { ...PAR, annualYieldPct: 6 };
  const exact = bondPrice(bond) - bondPrice({ ...bond, annualYieldPct: 6.01 });
  assert.ok(Math.abs(bondAnalytics(bond).dv01 - exact) < 0.001);
});

test('modified duration matches a numeric derivative for a semiannual bond', () => {
  const bond = { faceValue: 1000, couponRatePct: 6, years: 5, annualYieldPct: 8, frequency: 2 };
  const bump = 0.0001;
  const numeric =
    -(bondPrice({ ...bond, annualYieldPct: 8 + bump }) -
      bondPrice({ ...bond, annualYieldPct: 8 - bump })) /
    (2 * (bump / 100) * bondPrice(bond));
  assert.ok(Math.abs(bondAnalytics(bond).modifiedYears - numeric) < 1e-4);
});

test('duration plus convexity reproduces the exact one-point move to second order', () => {
  const bond = { ...PAR, annualYieldPct: 6 };
  const analytics = bondAnalytics(bond);
  const exactPct = bondPrice({ ...bond, annualYieldPct: 7 }) / bondPrice(bond) - 1;
  const taylorPct = -analytics.modifiedYears * 0.01 + 0.5 * analytics.convexity * 0.0001;
  // The Taylor estimate lands within a few hundredths of a percent; duration alone is ~0.35% off.
  assert.ok(Math.abs(taylorPct - exactPct) < 0.0005);
});

// --- yield curves ---

test('the normal curve rises with maturity and stays between its anchors', () => {
  const normal = YIELD_CURVES.normal;
  assert.ok(curveYieldPct(normal, 1) < curveYieldPct(normal, 10));
  assert.ok(curveYieldPct(normal, 10) < curveYieldPct(normal, 30));
  assert.ok(curveYieldPct(normal, 1) > normal.shortPct);
  assert.ok(curveYieldPct(normal, 30) < normal.longPct);
});

test('the inverted curve falls with maturity', () => {
  const inverted = YIELD_CURVES.inverted;
  assert.ok(curveYieldPct(inverted, 1) > curveYieldPct(inverted, 10));
  assert.ok(curveYieldPct(inverted, 10) > curveYieldPct(inverted, 30));
});

test('the flat curve pays the same yield at every maturity', () => {
  const flat = YIELD_CURVES.flat;
  assert.ok(Math.abs(curveYieldPct(flat, 1) - curveYieldPct(flat, 30)) < 1e-9);
  assert.ok(Math.abs(curveYieldPct(flat, 10) - 4.5) < 1e-9);
});

test('curve yields match the exponential blend fixture', () => {
  // normal at 10 years: 5.5 + (3 - 5.5) * exp(-10/8) = 4.7837...
  assert.ok(Math.abs(curveYieldPct(YIELD_CURVES.normal, 10) - 4.7837) < 0.0001);
});

test('every curve preset stays inside the 1-12 rate slider range over 1-30 years', () => {
  for (const curve of Object.values(YIELD_CURVES)) {
    for (let years = 1; years <= 30; years += 1) {
      const yieldPct = curveYieldPct(curve, years);
      assert.ok(yieldPct >= 1 && yieldPct <= 12);
    }
  }
});

// --- price regime ---

test('price regime classifies premium, par, and discount bonds', () => {
  assert.equal(priceRegime(6, 5), 'premium');
  assert.equal(priceRegime(5, 5), 'par');
  assert.equal(priceRegime(4, 5), 'discount');
});

test('price regime treats a hair-thin difference as par', () => {
  assert.equal(priceRegime(5, 5 + 1e-12), 'par');
});
