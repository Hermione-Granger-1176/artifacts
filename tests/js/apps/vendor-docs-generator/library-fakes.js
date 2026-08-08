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
 * Build an html2canvas stand-in returning a fixed-size canvas.
 * @returns {{ captures: any[], html2canvas: Function }} Fake and its call log.
 */
export function createFakeHtml2Canvas() {
  const captures = [];

  return {
    captures,
    html2canvas: async (element, options) => {
      captures.push({ element, options });
      return {
        width: 1588,
        height: 2246,
        toDataURL: () => 'data:image/png;base64,ZmFrZQ=='
      };
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
export function createExportDeps(overrides = {}) {
  const pdf = createFakeJsPdf();
  const canvas = createFakeHtml2Canvas();
  const zip = createFakeJsZip();

  return {
    pdf,
    canvas,
    zip,
    deps: {
      getJsPdf: () => pdf.JsPdf,
      getHtml2Canvas: () => canvas.html2canvas,
      getJsZip: () => zip.JsZip,
      ...overrides
    }
  };
}
