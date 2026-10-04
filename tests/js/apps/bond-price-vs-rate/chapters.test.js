import assert from 'node:assert/strict';
import test from 'node:test';

import {
  CHAPTER_BAND_MARGIN,
  initChapterTracking
} from '../../../../apps/bond-price-vs-rate/js/modules/chapters.js';

function makeNode(name) {
  const classes = new Set();
  return {
    name,
    parentElement: null,
    classList: {
      add(cls) { classes.add(cls); },
      toggle(cls, force) { if (force) classes.add(cls); else classes.delete(cls); },
      contains(cls) { return classes.has(cls); }
    }
  };
}

function makeStory(count) {
  const story = makeNode('story');
  const chapters = Array.from({ length: count }, (_unused, index) => {
    const chapter = makeNode(`chapter-${index + 1}`);
    chapter.parentElement = story;
    return chapter;
  });
  const documentObj = {
    querySelectorAll(selector) {
      assert.equal(selector, '.br-chapter');
      return chapters;
    }
  };
  return { story, chapters, documentObj };
}

function withFakeObserver(run) {
  const original = globalThis.IntersectionObserver;
  const observers = [];
  globalThis.IntersectionObserver = class {
    constructor(callback, options) {
      this.callback = callback;
      this.options = options;
      this.targets = [];
      observers.push(this);
    }

    observe(target) { this.targets.push(target); }
  };
  try {
    run(observers);
  } finally {
    if (original) globalThis.IntersectionObserver = original;
    else delete globalThis.IntersectionObserver;
  }
}

function currentNames(chapters) {
  return chapters.filter((chapter) => chapter.classList.contains('is-current')).map((chapter) => chapter.name);
}

test('chapter tracking starts on chapter one and turns muting on for the story', () => {
  withFakeObserver(() => {
    const { story, chapters, documentObj } = makeStory(3);
    initChapterTracking(documentObj);

    assert.equal(story.classList.contains('is-tracking'), true);
    assert.deepEqual(currentNames(chapters), ['chapter-1']);
  });
});

test('chapter tracking observes every chapter through the band and the last one in full', () => {
  withFakeObserver((observers) => {
    const { chapters, documentObj } = makeStory(3);
    initChapterTracking(documentObj);

    const [band, tail] = observers;
    assert.equal(band.options.rootMargin, CHAPTER_BAND_MARGIN);
    assert.deepEqual(band.targets, chapters);
    assert.equal(tail.options.threshold, 1);
    assert.deepEqual(tail.targets, [chapters[2]]);
  });
});

test('the chapter crossing the band becomes the only current chapter', () => {
  withFakeObserver((observers) => {
    const { chapters, documentObj } = makeStory(3);
    initChapterTracking(documentObj);
    const [band] = observers;

    band.callback([
      { target: chapters[1], isIntersecting: true },
      { target: chapters[0], isIntersecting: false }
    ]);
    assert.deepEqual(currentNames(chapters), ['chapter-2']);

    band.callback([{ target: chapters[1], isIntersecting: false }]);
    assert.deepEqual(currentNames(chapters), ['chapter-2'], 'leaving the band alone changes nothing');

    band.callback([{ target: chapters[0], isIntersecting: true }]);
    assert.deepEqual(currentNames(chapters), ['chapter-1']);
  });
});

test('a fully visible last chapter wins even if it never reaches the band', () => {
  withFakeObserver((observers) => {
    const { chapters, documentObj } = makeStory(3);
    initChapterTracking(documentObj);
    const [, tail] = observers;

    tail.callback([{ target: chapters[2], intersectionRatio: 0.6 }]);
    assert.deepEqual(currentNames(chapters), ['chapter-1'], 'a partly visible tail is ignored');

    tail.callback([{ target: chapters[2], intersectionRatio: 1 }]);
    assert.deepEqual(currentNames(chapters), ['chapter-3']);
  });
});

test('chapter tracking does nothing on a page without chapters', () => {
  withFakeObserver((observers) => {
    initChapterTracking({ querySelectorAll: () => [] });
    assert.equal(observers.length, 0);
  });
});

test('chapter tracking leaves every chapter at full strength without IntersectionObserver', () => {
  const original = globalThis.IntersectionObserver;
  delete globalThis.IntersectionObserver;
  try {
    const { story, chapters, documentObj } = makeStory(2);
    initChapterTracking(documentObj);
    assert.equal(story.classList.contains('is-tracking'), false);
    assert.deepEqual(currentNames(chapters), []);
  } finally {
    if (original) globalThis.IntersectionObserver = original;
  }
});

test('chapter tracking tolerates a chapter with no parent element', () => {
  withFakeObserver(() => {
    const { chapters, documentObj } = makeStory(1);
    chapters[0].parentElement = null;
    assert.doesNotThrow(() => initChapterTracking(documentObj));
    assert.deepEqual(currentNames(chapters), ['chapter-1']);
  });
});
