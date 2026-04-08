# Architecture

## Page sections

- Header shell: back button, home logo, and shared theme toggle
- Intro: app title and quick explainer
- Scenario tabs: switches the active token distribution context
- Scenario box: shows the active prompt prefix and scenario type
- Controls: temperature and top-p sliders with live numeric values
- Distribution: token bars, post-cutoff pills, and explanatory insight copy
- Concepts: delegated accordion cards for foundational sampling concepts

## Module map

- `js/app.js`
  - owns DOM caching, event listeners, and the render loop
- `js/modules/scenarios.js`
  - exports the scenario dataset
- `js/modules/sampling.js`
  - exports `softmax()` and top-p selection helpers
- `js/modules/render.js`
  - exports tab rendering, scenario rendering, and distribution rendering
- `js/modules/accordion.js`
  - exports delegated card-toggle behavior for concept cards

## Data flow

1. Active scenario index changes from tab interaction
2. Slider values derive `temperature` and `topP`
3. `buildTopPSelection()` computes probabilities, sorting, and the surviving nucleus
4. Render helpers rebuild tabs, scenario copy, bars, pills, and narrative insight

## Theme model

- `<html>` owns `data-theme="light|dark"`
- Shared shell behavior reads the same `theme` localStorage key as the root gallery
- Theme changes call back into the local render loop so color-derived bars and pills refresh immediately
