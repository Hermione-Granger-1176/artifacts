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

/** @param {*} value - Value to check. */
function isPlainObject(value) {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

/**
 * @param {boolean} condition
 * @param {string} message - Error message if assertion fails.
 */
function assertShape(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

/**
 * @param {*} value
 * @param {string} path - Dotted path for error messages.
 */
function validateStringArray(value, path) {
  assertShape(Array.isArray(value), `${path} must be an array`);

  for (const [index, element] of value.entries()) {
    assertShape(typeof element === 'string', `${path}[${index}] must be a string`);
  }
}

/**
 * @param {*} value
 * @param {string} path - Dotted path for error messages.
 */
function validateLabelMap(value, path) {
  assertShape(isPlainObject(value), `${path} must be an object`);

  for (const [key, entry] of Object.entries(value)) {
    assertShape(isPlainObject(entry), `${path}.${key} must be an object`);
    assertShape(typeof entry.label === 'string', `${path}.${key}.label must be a string`);
  }
}

/**
 * @param {Object} value
 * @param {string} key
 * @param {string} path
 */
function validateNullableStringField(value, key, path) {
  if (!(key in value) || value[key] === null) {
    return;
  }

  assertShape(typeof value[key] === 'string', `${path}.${key} must be a string or null`);
}

/** Validate the shape of window.ARTIFACTS_DATA at boot time. */
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

/** Validate the shape of window.ARTIFACTS_CONFIG at boot time. */
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

/** Validate both config and data globals before gallery initialization. */
export function validateGalleryBootstrapData(windowObj = window) {
  validateArtifactsConfig(windowObj.ARTIFACTS_CONFIG);
  validateArtifactsData(windowObj.ARTIFACTS_DATA);
}

/** Merge runtime config from window.ARTIFACTS_CONFIG with built-in defaults. */
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

/** @param {Object} config @param {string} tool - Tool identifier. */
export function getToolLabel(config, tool) {
  return config.tools[tool]?.label || capitalize(tool);
}

/** @param {Object} config @param {string} tag - Tag identifier. */
export function getTagLabel(config, tag) {
  return config.tags[tag]?.label || capitalize(tag).replace(/-/g, ' ');
}

/** @param {string} value */
function capitalize(value) {
  if (!value) {
    return '';
  }

  return value.charAt(0).toUpperCase() + value.slice(1);
}
