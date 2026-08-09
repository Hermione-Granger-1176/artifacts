/**
 * Recording stand-ins for the three vendored export libraries.
 *
 * They record the calls the renderers and exporters make rather than
 * producing real files, which is what lets the PDF and batch paths be tested
 * under Node without a browser or a 700KB UMD bundle.
 */

/** Average glyph advance as a fraction of the point size, for measurement. */
const AVERAGE_ADVANCE = 0.5;

/**
 * A jsPDF document that logs every drawing call.
 * @param {{ pageWidth?: number, pageHeight?: number }} [options={}] - Page geometry.
 * @returns {Record<string, any>} A recording document.
 */
function createFakeJsPdfDocument({ pageWidth = 595, pageHeight = 842 } = {}) {
  const calls = [];
  const texts = [];
  const tables = [];
  let finalY = 0;

  const record = (name) => (...args) => {
    calls.push({ name, args });
    return doc;
  };

  const doc = {
    calls,
    texts,
    tables,
    pages: 1,
    saved: null,
    images: [],
    internal: { pageSize: { getWidth: () => pageWidth, getHeight: () => pageHeight } },
    get lastAutoTable() {
      return { finalY };
    },
    fontSize: 10,
    fontFamily: 'helvetica',
    fontWeight: 'normal',
    setFont(family, weight) {
      doc.fontFamily = family;
      doc.fontWeight = weight;
      calls.push({ name: 'setFont', args: [family, weight] });
      return doc;
    },
    setFontSize(size) {
      doc.fontSize = size;
      calls.push({ name: 'setFontSize', args: [size] });
      return doc;
    },
    // Real jsPDF measures against embedded metrics. An average advance width of
    // half the point size is close enough for Helvetica that the fitting and
    // wrapping branches behave the way they do in the browser, which is what
    // these tests are here to exercise.
    getTextWidth(text) {
      return String(text).length * doc.fontSize * AVERAGE_ADVANCE;
    },
    getFontSize() {
      return doc.fontSize;
    },
    setTextColor: record('setTextColor'),
    setFillColor: record('setFillColor'),
    setDrawColor: record('setDrawColor'),
    setLineWidth: record('setLineWidth'),
    rect: record('rect'),
    addPage(...args) {
      doc.pages += 1;
      calls.push({ name: 'addPage', args });
      return doc;
    },
    addImage(...args) {
      doc.images.push(args);
      calls.push({ name: 'addImage', args });
      return doc;
    },
    splitTextToSize(text, maxWidth) {
      const perChar = doc.fontSize * AVERAGE_ADVANCE;
      const limit = Math.max(1, Math.floor((maxWidth ?? pageWidth) / perChar));

      return String(text)
        .split('\n')
        .flatMap((paragraph) => {
          const words = paragraph.split(' ');
          const lines = [''];

          for (const word of words) {
            const candidate = lines[lines.length - 1] ? `${lines[lines.length - 1]} ${word}` : word;

            if (candidate.length <= limit || !lines[lines.length - 1]) {
              lines[lines.length - 1] = candidate;
            } else {
              lines.push(word);
            }
          }

          return lines;
        });
    },
    text(value, x, y, options) {
      const lines = Array.isArray(value) ? value : [value];
      for (const line of lines) {
        texts.push({
          text: String(line),
          x,
          y,
          align: options?.align ?? 'left',
          size: doc.fontSize,
          family: doc.fontFamily,
          // Recorded so a test can reconstruct the drawn box exactly rather than
          // assuming the nominal point size, which the header fitter changes.
          width: String(line).length * doc.fontSize * AVERAGE_ADVANCE
        });
      }
      calls.push({ name: 'text', args: [value, x, y, options] });
      return doc;
    },
    autoTable(options) {
      tables.push(options);
      // Exercise the didParseCell hook the way autotable does, so styling
      // branches are covered rather than merely defined.
      if (typeof options.didParseCell === 'function') {
        (options.body ?? []).forEach((row, rowIndex) => {
          row.forEach((_cell, columnIndex) => {
            options.didParseCell({
              cell: { styles: {}, text: [] },
              column: { index: columnIndex },
              row: { index: rowIndex },
              section: 'body'
            });
          });
        });
      }
      finalY = (options.startY ?? 0) + 24 + (options.body?.length ?? 0) * 12;
      calls.push({ name: 'autoTable', args: [options] });
      return doc;
    },
    output() {
      return { type: 'blob', size: 1024 };
    },
    save(filename) {
      doc.saved = filename;
      return doc;
    }
  };

  return doc;
}

/**
 * Build a jsPDF constructor that hands back recording documents.
 * @param {{ pageWidth?: number, pageHeight?: number }} [options={}] - Page geometry.
 * @returns {{ JsPdf: Function, documents: Record<string, any>[] }} Constructor and the log.
 */
export function createFakeJsPdf(options = {}) {
  const documents = [];

  function JsPdf(...args) {
    const doc = createFakeJsPdfDocument(options);
    doc.constructedWith = args;
    documents.push(doc);
    return doc;
  }

  return { JsPdf, documents };
}

/**
 * A canvas that records every 2D drawing call and owns a real pixel buffer.
 *
 * The buffer is genuine, so the degradation pixel pass can be run over it and
 * asserted on byte by byte; everything geometric is recorded rather than
 * rasterised, because reproducing a browser's compositor under Node would test
 * the reproduction rather than the code.
 * @param {number} [width=1588] - Canvas width.
 * @param {number} [height=2246] - Canvas height.
 * @returns {Record<string, any>} The canvas, with `ctx` and `encodings` exposed.
 */
export function createFakeCanvas(width = 1588, height = 2246) {
  const calls = [];
  const encodings = [];
  let imageData = null;
  const record = (name) => (...args) => {
    calls.push({ name, args });
  };

  const ctx = {
    calls,
    filter: 'none',
    fillStyle: '',
    strokeStyle: '',
    lineWidth: 1,
    save: record('save'),
    restore: record('restore'),
    beginPath: record('beginPath'),
    moveTo: record('moveTo'),
    lineTo: record('lineTo'),
    arc: record('arc'),
    fill: record('fill'),
    stroke: record('stroke'),
    fillRect: record('fillRect'),
    drawImage: record('drawImage'),
    setTransform: record('setTransform'),
    putImageData: record('putImageData'),
    createLinearGradient(...args) {
      calls.push({ name: 'createLinearGradient', args });
      return { stops: [], addColorStop(offset, color) { this.stops.push([offset, color]); } };
    },
    // Allocated at the size actually asked for, so a canvas resized after
    // construction still hands back a buffer the pixel pass can walk.
    getImageData(_x, _y, dataWidth, dataHeight) {
      calls.push({ name: 'getImageData', args: [_x, _y, dataWidth, dataHeight] });
      imageData = {
        data: new Uint8ClampedArray(dataWidth * dataHeight * 4).fill(255),
        width: dataWidth,
        height: dataHeight
      };
      return imageData;
    }
  };

  return {
    width,
    height,
    ctx,
    encodings,
    get imageData() {
      return imageData;
    },
    getContext: () => ctx,
    toDataURL(mime = 'image/png', quality) {
      encodings.push({ mime, quality });
      return `data:${mime};base64,ZmFrZQ==`;
    }
  };
}

/**
 * Build an html2canvas stand-in returning a fixed-size canvas.
 * @param {{ height?: number, width?: number }} [size={}] - Capture size.
 * @returns {{ captures: any[], html2canvas: Function }} Fake and its call log.
 */
export function createFakeHtml2Canvas({ height = 2246, width = 1588 } = {}) {
  const captures = [];

  return {
    captures,
    html2canvas: async (element, options) => {
      const canvas = createFakeCanvas(width, height);
      captures.push({ canvas, element, options });
      return canvas;
    }
  };
}

/**
 * A document stand-in whose only job is to hand out fake canvases.
 * @returns {{ canvases: Record<string, any>[], documentObj: Record<string, any> }} Fake and its log.
 */
export function createFakeCanvasDocument() {
  const canvases = [];

  return {
    canvases,
    documentObj: {
      createElement(tag) {
        if (tag !== 'canvas') {
          throw new Error(`unexpected createElement(${tag})`);
        }

        const canvas = createFakeCanvas(0, 0);
        canvases.push(canvas);
        return canvas;
      }
    }
  };
}

/**
 * Build a JSZip stand-in that records the files written into it.
 * @returns {{ JsZip: Function, archives: Record<string, any>[] }} Constructor and the log.
 */
export function createFakeJsZip() {
  const archives = [];

  function JsZip() {
    const files = new Map();
    const archive = {
      files,
      file(path, data, options) {
        files.set(path, { data, options });
        return archive;
      },
      async generateAsync(_options, onUpdate) {
        onUpdate?.({ currentFile: null, percent: 50 });
        onUpdate?.({ currentFile: null, percent: 100 });
        return { type: 'zip', size: files.size };
      }
    };
    archives.push(archive);
    return archive;
  }

  return { JsZip, archives };
}

/**
 * Assemble an ExportDeps bag over fresh fakes.
 * @param {{ documentObj?: any, windowObj?: any }} [overrides={}] - DOM injection points.
 * @returns {Record<string, any>} Deps plus handles on every underlying fake.
 */
export function createExportDeps(overrides = {}, captureSize = {}) {
  const pdf = createFakeJsPdf();
  const canvas = createFakeHtml2Canvas(captureSize);
  const zip = createFakeJsZip();
  const scratch = createFakeCanvasDocument();

  return {
    pdf,
    canvas,
    scratch,
    zip,
    deps: {
      getJsPdf: () => pdf.JsPdf,
      getHtml2Canvas: () => canvas.html2canvas,
      getJsZip: () => zip.JsZip,
      ...overrides
    }
  };
}
