// A small DOM stand-in for the loan app tests. It implements the tree
// operations the app's in-place updates rely on (append, remove, fragments,
// attributes, class lists) so tests can check node identity.

const toCamel = (name) => name.replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());

export class FakeNode {
  constructor(tagName = '#fragment') {
    this.tagName = tagName;
    this.isFragment = tagName === '#fragment';
    this.children = [];
    this.parentNode = null;
    this.hidden = false;
    this.disabled = false;
    this.value = '';
    this.attributes = {};
    this.classes = new Set();
    this.ownText = '';
    this._listeners = {};
    this.classList = {
      add: (name) => this.classes.add(name),
      remove: (name) => this.classes.delete(name),
      contains: (name) => this.classes.has(name),
      toggle: (name, force) => {
        const on = force ?? !this.classes.has(name);
        if (on) this.classes.add(name);
        else this.classes.delete(name);
        return on;
      }
    };
  }

  get className() {
    return [...this.classes].join(' ');
  }

  set className(value) {
    this.classes = new Set(String(value).split(/\s+/).filter(Boolean));
  }

  get dataset() {
    const data = {};
    for (const [name, value] of Object.entries(this.attributes)) {
      if (name.startsWith('data-')) data[toCamel(name.slice(5))] = value;
    }
    return data;
  }

  get textContent() {
    return this.ownText + this.children.map((child) => child.textContent).join('');
  }

  set textContent(value) {
    for (const child of this.children) child.parentNode = null;
    this.children.length = 0;
    this.ownText = String(value);
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
    if (name === 'value') this.value = String(value);
  }

  getAttribute(name) {
    return this.attributes[name] ?? null;
  }

  removeAttribute(name) {
    delete this.attributes[name];
  }

  addEventListener(type, handler) {
    (this._listeners[type] ??= []).push(handler);
  }

  detach() {
    if (this.parentNode) {
      // Mutate in place: a live HTMLCollection reference must see the removal.
      const siblings = this.parentNode.children;
      siblings.splice(siblings.indexOf(this), 1);
      this.parentNode = null;
    }
  }

  remove() {
    this.detach();
  }

  adopt(node, index = this.children.length) {
    if (node.isFragment) {
      const moved = [...node.children];
      node.children = [];
      moved.forEach((child, offset) => this.adopt(child, index + offset));
      return;
    }
    node.detach();
    this.children.splice(index, 0, node);
    node.parentNode = this;
  }

  append(...nodes) {
    for (const node of nodes) this.adopt(node);
  }

  appendChild(node) {
    this.adopt(node);
    return node;
  }

  replaceChildren(...nodes) {
    for (const child of [...this.children]) child.detach();
    this.append(...nodes);
  }

  descendants() {
    return this.children.flatMap((child) => [child, ...child.descendants()]);
  }

  querySelectorAll(selector) {
    const attribute = /^\[([\w-]+)\]$/.exec(selector)?.[1];
    return this.descendants().filter((node) => attribute && node.getAttribute(attribute) !== null);
  }

  querySelector(selector) {
    return this.querySelectorAll(selector)[0] ?? null;
  }

  closest(selector) {
    const attribute = /^\[([\w-]+)\]$/.exec(selector)?.[1];
    for (let node = this; node; node = node.parentNode) {
      if (attribute && node.getAttribute(attribute) !== null) return node;
    }
    return null;
  }

  click() {
    for (const handler of this._listeners.click ?? []) handler.call(this, { type: 'click' });
  }
}

/**
 * Add the node factories the loan modules need to the current `document` mock.
 * @returns {() => void} Restore function.
 */
export function installFakeDom() {
  const previous = globalThis.document;
  const doc = previous ?? {};
  const saved = {
    createElement: doc.createElement,
    createDocumentFragment: doc.createDocumentFragment
  };
  doc.createElement = (tag) => new FakeNode(tag);
  doc.createDocumentFragment = () => new FakeNode('#fragment');
  globalThis.document = doc;

  return () => {
    if (previous) Object.assign(previous, saved);
    else delete globalThis.document;
  };
}
