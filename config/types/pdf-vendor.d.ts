// Ambient types for the export libraries the vendor-docs-generator app loads
// from apps/vendor-docs-generator/js/vendor/ as classic UMD scripts.
//
// These are hand-written against the exact vendored versions (jspdf 2.5.1,
// jspdf-autotable 3.8.2, html2canvas 1.4.1, jszip 3.10.1) and cover only the
// surface the app actually calls. Declaring them here keeps the typecheck
// honest without pulling four heavyweight packages into devDependencies purely
// to read their bundled .d.ts files. If the app starts using more of an API,
// widen the matching interface below rather than reaching for `any`.

export {};

/** Cell alignment values jspdf-autotable accepts. */
type AutoTableHAlign = "left" | "center" | "right";

/** Style bag shared by autotable's head, body, and per-cell styling hooks. */
interface AutoTableStyles {
  font?: string;
  cellPadding?: number;
  cellWidth?: number | "auto" | "wrap";
  fillColor?: [number, number, number] | number | false;
  fontSize?: number;
  fontStyle?: "normal" | "bold" | "italic" | "bolditalic";
  halign?: AutoTableHAlign;
  lineColor?: [number, number, number] | number;
  lineWidth?: number;
  textColor?: [number, number, number] | number;
  valign?: "top" | "middle" | "bottom";
}

/** The cell view handed to the didParseCell hook. */
interface AutoTableCellHookData {
  cell: { styles: AutoTableStyles; text: string[] };
  column: { index: number };
  row: { index: number };
  section: "head" | "body" | "foot";
}

/** Options accepted by the autotable plugin method. */
interface AutoTableOptions {
  alternateRowStyles?: AutoTableStyles;
  body?: (string | number)[][];
  bodyStyles?: AutoTableStyles;
  columnStyles?: Record<number, AutoTableStyles>;
  didParseCell?: (data: AutoTableCellHookData) => void;
  head?: (string | number)[][];
  headStyles?: AutoTableStyles;
  margin?: { bottom?: number; left?: number; right?: number; top?: number };
  startY?: number;
  styles?: AutoTableStyles;
  tableWidth?: number | "auto" | "wrap";
  theme?: "striped" | "grid" | "plain";
}

/** Text placement options used by the PDF renderer. */
interface TextOptions {
  align?: AutoTableHAlign;
  maxWidth?: number;
}

/** The jsPDF document surface the PDF renderer drives. */
interface JsPdfDocument {
  addImage(
    imageData: string,
    format: string,
    x: number,
    y: number,
    width: number,
    height: number,
  ): JsPdfDocument;
  addPage(): JsPdfDocument;
  autoTable(options: AutoTableOptions): JsPdfDocument;
  internal: { pageSize: { getHeight(): number; getWidth(): number } };
  lastAutoTable: { finalY: number };
  output(type: "blob"): Blob;
  rect(x: number, y: number, width: number, height: number, style?: string): JsPdfDocument;
  save(filename: string): JsPdfDocument;
  setDrawColor(r: number, g: number, b: number): JsPdfDocument;
  setFillColor(r: number, g: number, b: number): JsPdfDocument;
  setFont(family: string, style?: string): JsPdfDocument;
  setFontSize(size: number): JsPdfDocument;
  setLineWidth(width: number): JsPdfDocument;
  setTextColor(r: number, g: number, b: number): JsPdfDocument;
  splitTextToSize(text: string, maxWidth: number): string[];
  getTextWidth(text: string): number;
  getFontSize(): number;
  text(text: string | string[], x: number, y: number, options?: TextOptions): JsPdfDocument;
}

/** Constructor view of the jsPDF UMD global. */
interface JsPdfConstructor {
  new (
    orientation?: "p" | "portrait" | "l" | "landscape",
    unit?: "pt" | "mm" | "cm" | "in" | "px",
    format?: string | number[],
  ): JsPdfDocument;
}

/** Options html2canvas is called with. */
interface Html2CanvasOptions {
  backgroundColor?: string | null;
  logging?: boolean;
  scale?: number;
  useCORS?: boolean;
  windowWidth?: number;
}

/** The JSZip archive surface the batch exporter drives. */
interface JsZipArchive {
  file(path: string, data: Blob | string, options?: { base64?: boolean }): JsZipArchive;
  generateAsync(
    options: {
      compression?: "STORE" | "DEFLATE";
      compressionOptions?: { level: number };
      type: "blob";
    },
    onUpdate?: (metadata: { currentFile: string | null; percent: number }) => void,
  ): Promise<Blob>;
}

/** Constructor view of the JSZip UMD global. */
interface JsZipConstructor {
  new (): JsZipArchive;
}

declare global {
  interface Window {
    html2canvas?: (
      element: HTMLElement,
      options?: Html2CanvasOptions,
    ) => Promise<HTMLCanvasElement>;
    jspdf?: { jsPDF: JsPdfConstructor };
    JSZip?: JsZipConstructor;
  }

  type ArtifactsJsPdfConstructor = JsPdfConstructor;
  type ArtifactsJsPdfDocument = JsPdfDocument;
  type ArtifactsJsZipArchive = JsZipArchive;
  type ArtifactsJsZipConstructor = JsZipConstructor;
  type ArtifactsAutoTableOptions = AutoTableOptions;
  type ArtifactsHtml2Canvas = (
    element: HTMLElement,
    options?: Html2CanvasOptions,
  ) => Promise<HTMLCanvasElement>;
}
