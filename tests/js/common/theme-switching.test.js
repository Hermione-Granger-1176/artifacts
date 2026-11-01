import test from 'node:test';
import assert from 'node:assert/strict';

import { createThemeSwitchGuard } from '../../../js/modules/theme-switching.js';

function createEnv() {
  const classes = new Set();
  /** @type {Array<() => void>} */
  let frames = [];
  const html = {
    classList: {
      add: (name) => classes.add(name),
      remove: (name) => classes.delete(name)
    }
  };
  const windowObj = {
    requestAnimationFrame: (callback) => {
      frames.push(callback);
      return frames.length;
    }
  };
  const runFrame = () => {
    const due = frames;
    frames = [];
    due.forEach((callback) => callback());
  };
  return { classes, html, windowObj, runFrame };
}

test('the guard holds transitions off for two frames', () => {
  const env = createEnv();
  const suspend = createThemeSwitchGuard(env.html, env.windowObj);

  suspend();
  assert.equal(env.classes.has('theme-switching'), true);
  env.runFrame();
  assert.equal(env.classes.has('theme-switching'), true, 'it stays through the first frame');
  env.runFrame();
  assert.equal(env.classes.has('theme-switching'), false);
});

test('an earlier switch does not lift the class for a later one', () => {
  const env = createEnv();
  const suspend = createThemeSwitchGuard(env.html, env.windowObj);

  suspend();
  env.runFrame();
  suspend();
  env.runFrame();
  assert.equal(env.classes.has('theme-switching'), true);
  env.runFrame();
  assert.equal(env.classes.has('theme-switching'), false);
});
