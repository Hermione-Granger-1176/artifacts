/**
 * Chapter tracking for the bonds vs interest rates explainer.
 *
 * The story column is a run of numbered chapters. An IntersectionObserver
 * watches a thin band a little above the middle of the viewport and marks the
 * chapter crossing it as current, so the reader always has one chapter at full
 * strength while the others sit slightly muted. A second observer covers the
 * last chapter, which can be too short to ever reach the band before the page
 * runs out of scroll. The muting is a CSS rule gated on `.is-tracking`, so a
 * browser without IntersectionObserver leaves every chapter at full strength.
 * @module chapters
 */

/** Root margin that shrinks the viewport to a band 10% tall, 30% from the top. */
export const CHAPTER_BAND_MARGIN = "-30% 0px -60% 0px";

/**
 * Mark exactly one chapter as current.
 * @param {Element[]} chapters - Every chapter, in document order.
 * @param {Element} current - The chapter to highlight.
 * @returns {void}
 */
function markCurrent(chapters, current) {
  for (const chapter of chapters) {
    chapter.classList.toggle("is-current", chapter === current);
  }
}

/**
 * Start tracking which chapter is in view. Safe to call on a page with no
 * chapters or without IntersectionObserver support.
 * @param {Document} [documentObj] - Document to query for `.br-chapter` nodes.
 * @returns {void}
 */
export function initChapterTracking(documentObj = document) {
  const chapters = Array.from(documentObj.querySelectorAll(".br-chapter"));
  if (chapters.length === 0 || typeof IntersectionObserver !== "function") {
    return;
  }

  chapters[0].parentElement?.classList.add("is-tracking");
  markCurrent(chapters, chapters[0]);

  const band = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          markCurrent(chapters, entry.target);
        }
      }
    },
    { rootMargin: CHAPTER_BAND_MARGIN }
  );

  const tail = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.intersectionRatio >= 1) {
          markCurrent(chapters, entry.target);
        }
      }
    },
    { threshold: 1 }
  );

  for (const chapter of chapters) {
    band.observe(chapter);
  }
  tail.observe(chapters[chapters.length - 1]);
}
