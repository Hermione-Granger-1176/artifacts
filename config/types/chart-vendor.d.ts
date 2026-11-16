// Ambient types for the Chart.js UMD globals the artifact apps load from
// js/vendor/. The runtime code reads them through chartGlobal() in
// js/modules/chart-theme.js. The types come from the exact-pinned chart.js,
// chartjs-plugin-annotation, and chartjs-plugin-datalabels devDependencies.
import type { Chart, ChartConfiguration, Plugin } from "chart.js";
// Importing the plugin type packages registers the "datalabels" and
// "annotation" plugin option keys on chart.js.
import type {} from "chartjs-plugin-datalabels";
import type {} from "chartjs-plugin-annotation";

// The loan-amortization doughnut chart stashes render state on the Chart
// instance so its center-text plugin and datalabels callbacks can read it.
declare module "chart.js" {
  interface Chart {
    $artifactsInterestTotal?: number;
    $artifactsFormatCurrency?: (value: number) => string;
    $artifactsPalette?: { redEmphasis: string; greenEmphasis: string };
  }
}

declare global {
  /**
   * Constructor view of the vendored Chart.js UMD global. The config generic is
   * broad, and the per-controller options (cutout, datalabels, annotation) are
   * not typed here. Callback parameters are typed at each call site.
   */
  interface ChartConstructorLike {
    new (
      item: HTMLCanvasElement | CanvasRenderingContext2D,
      config: ChartConfiguration<any>,
    ): Chart;
    register(...items: unknown[]): void;
  }

  /** The vendor chart globals exposed on window. */
  interface ChartVendorGlobals {
    Chart: ChartConstructorLike;
    ChartDataLabels: Plugin;
    ChartAnnotation: Plugin;
  }
}

export {};
