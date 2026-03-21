const DEFAULT_CONFIG = {
  toolDisplayOrder: ['claude', 'chatgpt', 'gemini'],
  tagDisplayOrder: [],
  tools: {
    claude: { label: 'Claude' },
    chatgpt: { label: 'ChatGPT' },
    gemini: { label: 'Gemini' }
  },
  tags: {}
};

/**
 * @typedef {{ label: string }} LabelEntry
 * @typedef {{
 *   toolDisplayOrder?: string[],
 *   tagDisplayOrder?: string[],
 *   tools?: Record<string, LabelEntry>,
 *   tags?: Record<string, LabelEntry>
 * }} GalleryConfig
 * @typedef {{
 *   id: string,
 *   name: string,
 *   url: string,
 *   description?: string | null,
 *   thumbnail?: string | null,
 *   tags: string[],
 *   tools: string[]
 * }} ArtifactRecord
 */

/**
 * Return whether a value is a plain object.
 * @param {*} value - Value to check.
 * @returns {boolean} Whether the value is a plain object.
 */
function isPlainObject(value) {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

/**
 * Throw when a runtime bootstrap validation check fails.
 * @param {boolean} condition - Condition to enforce.
 * @param {string} message - Error message if assertion fails.
 * @returns {void}
 */
function assertShape(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

/**
 * Validate that a runtime config field is an array of strings.
 * @param {*} value - Value to validate.
 * @param {string} path - Dotted path for error messages.
 * @returns {void}
 */
function validateStringArray(value, path) {
  assertShape(Array.isArray(value), `${path} must be an array`);

  for (const [index, element] of value.entries()) {
    assertShape(typeof element === 'string', `${path}[${index}] must be a string`);
  }
}

/**
 * Validate that a runtime config label map has string labels.
 * @param {*} value - Value to validate.
 * @param {string} path - Dotted path for error messages.
 * @returns {void}
 */
function validateLabelMap(value, path) {
  assertShape(isPlainObject(value), `${path} must be an object`);

  for (const [key, entry] of Object.entries(value)) {
    assertShape(isPlainObject(entry), `${path}.${key} must be an object`);
    assertShape(typeof entry.label === 'string', `${path}.${key}.label must be a string`);
  }
}

/**
 * Validate one optional string-or-null field on a record.
 * @param {Record<string, *>} value - Record containing the field.
 * @param {string} key - Field name.
 * @param {string} path - Dotted path for error messages.
 * @returns {void}
 */
function validateNullableStringField(value, key, path) {
  if (!(key in value) || value[key] === null) {
    return;
  }

  assertShape(typeof value[key] === 'string', `${path}.${key} must be a string or null`);
}

/**
 * Validate the shape of `window.ARTIFACTS_DATA` at boot time.
 * @param {*} value - Runtime bootstrap data to validate.
 * @returns {ArtifactRecord[]} Validated artifact data.
 */
export function validateArtifactsData(value) {
  assertShape(Array.isArray(value), 'window.ARTIFACTS_DATA must be an array');

  value.forEach((item, index) => {
    const path = `window.ARTIFACTS_DATA[${index}]`;
    assertShape(isPlainObject(item), `${path} must be an object`);
    assertShape(typeof item.id === 'string', `${path}.id must be a string`);
    assertShape(typeof item.name === 'string', `${path}.name must be a string`);
    assertShape(typeof item.url === 'string', `${path}.url must be a string`);

    ['description', 'thumbnail'].forEach((key) => {
      validateNullableStringField(item, key, path);
    });

    assertShape(Array.isArray(item.tags), `${path}.tags must be an array`);
    item.tags.forEach((tag, tagIndex) => {
      assertShape(typeof tag === 'string', `${path}.tags[${tagIndex}] must be a string`);
    });

    assertShape(Array.isArray(item.tools), `${path}.tools must be an array`);
    item.tools.forEach((tool, toolIndex) => {
      assertShape(typeof tool === 'string', `${path}.tools[${toolIndex}] must be a string`);
    });
  });

  return value;
}

/**
 * Validate the shape of `window.ARTIFACTS_CONFIG` at boot time.
 * @param {*} value - Runtime config object to validate.
 * @returns {GalleryConfig} Validated gallery config.
 */
export function validateArtifactsConfig(value) {
  assertShape(isPlainObject(value), 'window.ARTIFACTS_CONFIG must be an object');

  [
    ['toolDisplayOrder', validateStringArray],
    ['tagDisplayOrder', validateStringArray],
    ['tools', validateLabelMap],
    ['tags', validateLabelMap]
  ].forEach(([key, validator]) => {
    if (!(key in value)) {
      return;
    }

    validator(value[key], `window.ARTIFACTS_CONFIG.${key}`);
  });

  return value;
}

/**
 * Validate both generated globals before gallery initialization.
 * @param {Window} [windowObj=window] - Runtime window object containing bootstrap globals.
 * @returns {void}
 */
export function validateGalleryBootstrapData(windowObj = window) {
  validateArtifactsConfig(windowObj.ARTIFACTS_CONFIG);
  validateArtifactsData(windowObj.ARTIFACTS_DATA);
}

/**
 * Merge runtime config from `window.ARTIFACTS_CONFIG` with built-in defaults.
 * @param {Window} [windowObj=window] - Runtime window object containing bootstrap globals.
 * @returns {Required<GalleryConfig>} Merged gallery config.
 */
export function getGalleryConfig(windowObj = window) {
  const runtimeConfig = windowObj.ARTIFACTS_CONFIG || {};
  return {
    toolDisplayOrder: runtimeConfig.toolDisplayOrder || DEFAULT_CONFIG.toolDisplayOrder,
    tagDisplayOrder: runtimeConfig.tagDisplayOrder || DEFAULT_CONFIG.tagDisplayOrder,
    tools: {
      ...DEFAULT_CONFIG.tools,
      ...(runtimeConfig.tools || {})
    },
    tags: {
      ...DEFAULT_CONFIG.tags,
      ...(runtimeConfig.tags || {})
    }
  };
}

/**
 * Return the display label for one tool identifier.
 * @param {Required<GalleryConfig>} config - Gallery config object.
 * @param {string} tool - Tool identifier.
 * @returns {string} Display label.
 */
export function getToolLabel(config, tool) {
  return config.tools[tool]?.label || capitalize(tool);
}

/**
 * Return the display label for one tag identifier.
 * @param {Required<GalleryConfig>} config - Gallery config object.
 * @param {string} tag - Tag identifier.
 * @returns {string} Display label.
 */
export function getTagLabel(config, tag) {
  return config.tags[tag]?.label || capitalize(tag).replace(/-/g, ' ');
}

/**
 * Capitalize the first letter of a string.
 * @param {string} value - Input string.
 * @returns {string} Capitalized string.
 */
function capitalize(value) {
  if (!value) {
    return '';
  }

  return value.charAt(0).toUpperCase() + value.slice(1);
}
