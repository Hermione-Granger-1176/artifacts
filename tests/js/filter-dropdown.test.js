import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { createFilterDropdown } from '../../js/modules/filter-dropdown.js';

function createFakeControl() {
  const classes = new Set();
  const attrs = {};
  return {
    root: {
      classList: {
        add(c) { classes.add(c); },
        remove(c) { classes.delete(c); },
        has(c) { return classes.has(c); }
      },
      _classes: classes
    },
    toggle: {
      setAttribute(name, value) { attrs[`toggle:${name}`] = value; },
      _attrs: attrs
    },
    panel: {
      setAttribute(name, value) { attrs[`panel:${name}`] = value; },
      _attrs: attrs
    },
    _attrs: attrs
  };
}

function makeControls() {
  return {
    tool: createFakeControl(),
    tag: createFakeControl()
  };
}

describe('createFilterDropdown', () => {
  it('starts with no open dropdown', () => {
    const dropdown = createFilterDropdown(makeControls());
    assert.equal(dropdown.isOpen(), false);
    assert.equal(dropdown.getOpenKey(), null);
  });

  it('open sets the dropdown to open state', () => {
    const controls = makeControls();
    const dropdown = createFilterDropdown(controls);
    dropdown.open('tool');
    assert.equal(dropdown.isOpen(), true);
    assert.equal(dropdown.getOpenKey(), 'tool');
    assert.equal(controls.tool.root._classes.has('open'), true);
    assert.equal(controls.tool._attrs['toggle:aria-expanded'], 'true');
    assert.equal(controls.tool._attrs['panel:aria-hidden'], 'false');
  });

  it('open closes previously open dropdown first', () => {
    const controls = makeControls();
    const dropdown = createFilterDropdown(controls);
    dropdown.open('tool');
    dropdown.open('tag');
    assert.equal(dropdown.getOpenKey(), 'tag');
    assert.equal(controls.tool.root._classes.has('open'), false);
    assert.equal(controls.tool._attrs['toggle:aria-expanded'], 'false');
    assert.equal(controls.tag.root._classes.has('open'), true);
  });

  it('close closes the open dropdown', () => {
    const controls = makeControls();
    const dropdown = createFilterDropdown(controls);
    dropdown.open('tool');
    dropdown.close();
    assert.equal(dropdown.isOpen(), false);
    assert.equal(dropdown.getOpenKey(), null);
    assert.equal(controls.tool.root._classes.has('open'), false);
    assert.equal(controls.tool._attrs['toggle:aria-expanded'], 'false');
    assert.equal(controls.tool._attrs['panel:aria-hidden'], 'true');
  });

  it('close is a no-op when nothing is open', () => {
    const dropdown = createFilterDropdown(makeControls());
    dropdown.close();
    assert.equal(dropdown.isOpen(), false);
  });

  it('toggle opens a closed dropdown', () => {
    const controls = makeControls();
    const dropdown = createFilterDropdown(controls);
    dropdown.toggle('tool');
    assert.equal(dropdown.getOpenKey(), 'tool');
  });

  it('toggle closes the same dropdown when already open', () => {
    const controls = makeControls();
    const dropdown = createFilterDropdown(controls);
    dropdown.open('tool');
    dropdown.toggle('tool');
    assert.equal(dropdown.isOpen(), false);
  });

  it('toggle switches to a different dropdown', () => {
    const controls = makeControls();
    const dropdown = createFilterDropdown(controls);
    dropdown.open('tool');
    dropdown.toggle('tag');
    assert.equal(dropdown.getOpenKey(), 'tag');
    assert.equal(controls.tool.root._classes.has('open'), false);
  });
});
