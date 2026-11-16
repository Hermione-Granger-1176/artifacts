# Bonds and interest rates

This interactive explainer shows why bond prices fall when interest rates rise. A left rail holds the price, its curve, and three sliders while seven chapters explain the price change and its wider effects.

## Features

- A sticky left rail with the price, a premium, par, or discount badge, the price-vs-rate curve, and the market rate, coupon, and years sliders. Below 760px the rail stacks above the chapters.
- Seven numbered chapters: the inverse move, why it happens, how hard it swings, the yield curve, the maths, the analyst readout, and the ripple.
- A discounting formula and a worked cash-flow table whose present values sum to the price.
- A bar chart of the dollar loss from a one-point rate rise at each maturity.
- An analyst readout with current yield, Macaulay duration, modified duration, convexity, and DV01.

## Use the app

- Drag the market rate, coupon, and years sliders in the left rail. The price, the badge, and the curve update on each move.
- Scroll the chapters to read the story. The chapter in view has a filled number badge and full-strength charts. The other chapters are dimmed.
- In chapter 4, click one of the yield curve shapes (normal, flat, or inverted). Then click the apply button to set the market rate slider to that curve's rate at the bond's maturity.

## Made with

- Claude
- Chart.js 4.4.1 (vendored)

## Documentation

The app documentation covers [architecture](docs/architecture.md), [verification](docs/verification.md), and [implementation decisions](docs/decisions.md).
