/**
 * @typedef {{ label: string }} LabelEntry
 * @typedef {{
 *   toolDisplayOrder?: string[],
 *   tagDisplayOrder?: string[],
 *   artifactContract?: ArtifactContract,
 *   tools?: Record<string, LabelEntry>,
 *   tags?: Record<string, LabelEntry>
 * }} GalleryConfig
 * @typedef {{
 *   artifactIdPattern: string,
 *   artifactBasePath: string,
 *   thumbnailFile: string
 * }} ArtifactContract
 * @typedef {{
 *   id: string,
 *   name: string,
 *   url: string,
 *   description?: string | null,
 *   thumbnail?: string | null,
 *   tags: string[],
 *   tools: string[]
 * }} ArtifactRecord
 * @typedef {Window & {
 *   ARTIFACTS_CONFIG?: GalleryConfig,
 *   ARTIFACTS_DATA?: ArtifactRecord[]
 * }} GalleryWindow
 */

/** @type {Required<GalleryConfig>} */
const DEFAULT_CONFIG = {
  artifactContract: {
    artifactIdPattern: '^[a-z0-9]+(?:-[a-z0-9]+)*$',
    artifactBasePath: 'apps',
    thumbnailFile: 'thumbnail.webp'
  },
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
 * Decode a URI component, returning the original value on failure.
 * @param {string} value - Possibly percent-encoded value.
 * @returns {string} The decoded value, or the original on failure.
 */
function decodeUriComponentSafely(value) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

/**
 * Return the provided artifact contract or fall back to the default.
 * @param {ArtifactContract | null | undefined} value - Candidate contract.
 * @returns {ArtifactContract} The resolved contract.
 */
function getArtifactContract(value) {
  return value || DEFAULT_CONFIG.artifactContract;
}

/**
 * Compile the contract's artifact ID pattern into a RegExp.
 * @param {ArtifactContract} contract - Artifact contract.
 * @returns {RegExp} Compiled artifact id pattern.
 */
function compileArtifactIdRegex(contract) {
  return new RegExp(contract.artifactIdPattern);
}

/**
 * Return whether a value is a full match for the artifact ID pattern.
 * @param {string} value - Candidate artifact id.
 * @param {ArtifactContract} contract - Artifact contract.
 * @param {RegExp | null | undefined} compiledRegex - Optional precompiled pattern.
 * @returns {boolean} Whether the value fully matches the pattern.
 */
function matchesArtifactId(value, contract, compiledRegex) {
  const regex = compiledRegex || compileArtifactIdRegex(contract);
  const match = regex.exec(value);
  return match !== null && match.index === 0 && match[0] === value;
}

/**
 * Build the expected URL path for an artifact.
 * @param {ArtifactContract} contract - Artifact contract.
 * @param {string} artifactId - Artifact id.
 * @returns {string} The expected artifact URL path.
 */
function buildArtifactUrl(contract, artifactId) {
  return `${contract.artifactBasePath}/${artifactId}/`;
}

/**
 * Build the expected thumbnail path for an artifact.
 * @param {ArtifactContract} contract - Artifact contract.
 * @param {string} artifactId - Artifact id.
 * @returns {string} The expected thumbnail path.
 */
function buildThumbnailPath(contract, artifactId) {
  return `${contract.artifactBasePath}/${artifactId}/${contract.thumbnailFile}`;
}

/**
 * Return whether a URL matches the expected artifact URL structure.
 * @param {string} value - Candidate URL.
 * @param {ArtifactContract} contract - Artifact contract.
 * @param {RegExp | null | undefined} compiledRegex - Optional precompiled pattern.
 * @returns {boolean} Whether the URL matches.
 */
function matchesArtifactUrlShape(value, contract, compiledRegex) {
  const parts = value.split('/');
  return parts.length === 3
    && parts[0] === contract.artifactBasePath
    && parts[2] === ''
    && matchesArtifactId(parts[1], contract, compiledRegex);
}

/**
 * Return whether a path matches the expected thumbnail path structure.
 * @param {string} value - Candidate thumbnail path.
 * @param {ArtifactContract} contract - Artifact contract.
 * @param {RegExp | null | undefined} compiledRegex - Optional precompiled pattern.
 * @returns {boolean} Whether the path matches.
 */
function matchesThumbnailShape(value, contract, compiledRegex) {
  const parts = value.split('/');
  return parts.length === 3
    && parts[0] === contract.artifactBasePath
    && parts[2] === contract.thumbnailFile
    && matchesArtifactId(parts[1], contract, compiledRegex);
}

/**
 * Validate the runtime artifact contract object.
 * @param {*} value - Runtime contract value to validate.
 * @param {string} path - Dotted path for error messages.
 * @returns {void}
 */
function validateArtifactContract(value, path) {
  assertShape(isPlainObject(value), `${path} must be an object`);
  assertShape(
    typeof value.artifactIdPattern === 'string',
    `${path}.artifactIdPattern must be a string`
  );
  assertShape(
    typeof value.artifactBasePath === 'string',
    `${path}.artifactBasePath must be a string`
  );
  assertShape(typeof value.thumbnailFile === 'string', `${path}.thumbnailFile must be a string`);
  assertShape(
    value.artifactBasePath.length > 0 && !value.artifactBasePath.includes('/') && !value.artifactBasePath.startsWith('.'),
    `${path}.artifactBasePath must be a non-empty safe path segment`
  );
  assertShape(
    value.thumbnailFile.length > 0 && !value.thumbnailFile.includes('/') && !value.thumbnailFile.startsWith('.'),
    `${path}.thumbnailFile must be a non-empty safe file name`
  );

  try {
    new RegExp(value.artifactIdPattern);
  } catch {
    assertShape(false, `${path}.artifactIdPattern must be a valid regular expression`);
  }
}

/**
 * Assert that a value is a safe repo-relative path without protocol or traversal.
 * @param {string} value - Candidate path.
 * @param {string} path - Dotted path for error messages.
 * @returns {void}
 */
function assertSafeRelativePath(value, path) {
  const decodedValue = decodeUriComponentSafely(value);
  assertShape(!value.includes('://'), `${path} must be a repo-relative path`);
  assertShape(!decodedValue.includes('://'), `${path} must be a repo-relative path`);
  assertShape(!value.startsWith('/'), `${path} must not start with '/'`);
  assertShape(!decodedValue.startsWith('/'), `${path} must not start with '/'`);
  assertShape(!/^data:/i.test(value), `${path} must not use a data URL`);
  assertShape(!/^data:/i.test(decodedValue), `${path} must not use a data URL`);
  assertShape(!/^javascript:/i.test(value), `${path} must not use a javascript URL`);
  assertShape(!/^javascript:/i.test(decodedValue), `${path} must not use a javascript URL`);
  assertShape(!decodedValue.includes('..'), `${path} must not contain path traversal segments`);
}

/**
 * Validate an artifact URL field against the contract.
 * @param {*} value - Runtime URL value to validate.
 * @param {string} path - Dotted path for error messages.
 * @param {string} expectedId - Expected artifact id.
 * @param {ArtifactContract} contract - Artifact contract.
 * @param {RegExp} compiledRegex - Precompiled artifact id pattern.
 * @returns {void}
 */
function validateArtifactUrl(value, path, expectedId, contract, compiledRegex) {
  assertShape(typeof value === 'string', `${path} must be a string`);
  assertSafeRelativePath(value, path);
  const expectedUrl = buildArtifactUrl(contract, expectedId);
  if (value === expectedUrl) {
    return;
  }

  if (matchesArtifactUrlShape(value, contract, compiledRegex)) {
    assertShape(false, `${path} must use the same artifact id as ${path.replace(/\.url$/, '.id')}`);
  }

  assertShape(false, `${path} must match ${buildArtifactUrl(contract, '<artifact-id>')}`);
}

/**
 * Validate an artifact thumbnail path field against the contract.
 * @param {*} value - Runtime thumbnail value to validate.
 * @param {string} path - Dotted path for error messages.
 * @param {string} expectedId - Expected artifact id.
 * @param {ArtifactContract} contract - Artifact contract.
 * @param {RegExp} compiledRegex - Precompiled artifact id pattern.
 * @returns {void}
 */
function validateThumbnailPath(value, path, expectedId, contract, compiledRegex) {
  assertShape(typeof value === 'string', `${path} must be a string`);
  assertSafeRelativePath(value, path);
  const expectedThumbnail = buildThumbnailPath(contract, expectedId);
  if (value === expectedThumbnail) {
    return;
  }

  if (matchesThumbnailShape(value, contract, compiledRegex)) {
    assertShape(false, `${path} must use the same artifact id as ${path.replace(/\.thumbnail$/, '.id')}`);
  }

  assertShape(false, `${path} must match ${buildThumbnailPath(contract, '<artifact-id>')}`);
}

/**
 * Validate the shape of `window.ARTIFACTS_DATA` at boot time.
 * @param {*} value - Runtime bootstrap data to validate.
 * @returns {ArtifactRecord[]} Validated artifact data.
 */
export function validateArtifactsData(value, artifactContract = DEFAULT_CONFIG.artifactContract) {
  const contract = getArtifactContract(artifactContract);
  validateArtifactContract(contract, 'artifactContract');
  assertShape(Array.isArray(value), 'window.ARTIFACTS_DATA must be an array');

  const idRegex = compileArtifactIdRegex(contract);

  value.forEach(/** @param {*} item @param {number} index */ (item, index) => {
    const path = `window.ARTIFACTS_DATA[${index}]`;
    assertShape(isPlainObject(item), `${path} must be an object`);
    assertShape(typeof item.id === 'string', `${path}.id must be a string`);
    assertShape(matchesArtifactId(item.id, contract, idRegex), `${path}.id must match the artifact id pattern`);
    assertShape(typeof item.name === 'string', `${path}.name must be a string`);
    validateArtifactUrl(item.url, `${path}.url`, item.id, contract, idRegex);

    validateNullableStringField(item, 'description', path);
    validateNullableStringField(item, 'thumbnail', path);
    if (item.thumbnail !== undefined && item.thumbnail !== null) {
      validateThumbnailPath(item.thumbnail, `${path}.thumbnail`, item.id, contract, idRegex);
    }

    assertShape(Array.isArray(item.tags), `${path}.tags must be an array`);
    item.tags.forEach(/** @param {string} tag @param {number} tagIndex */ (tag, tagIndex) => {
      assertShape(typeof tag === 'string', `${path}.tags[${tagIndex}] must be a string`);
    });

    assertShape(Array.isArray(item.tools), `${path}.tools must be an array`);
    item.tools.forEach(/** @param {string} tool @param {number} toolIndex */ (tool, toolIndex) => {
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

  /** @type {Array<[string, (value: *, path: string) => void]>} */
  const validators = [
    ['toolDisplayOrder', validateStringArray],
    ['tagDisplayOrder', validateStringArray],
    ['tools', validateLabelMap],
    ['tags', validateLabelMap]
  ];

  validators.forEach(([key, validator]) => {
    if (!(key in value)) {
      return;
    }

    validator(value[key], `window.ARTIFACTS_CONFIG.${key}`);
  });

  if ('artifactContract' in value) {
    validateArtifactContract(value.artifactContract, 'window.ARTIFACTS_CONFIG.artifactContract');
  }

  return value;
}

/**
 * Validate both generated globals before gallery initialization.
 * @param {Window} [windowObj=window] - Runtime window object containing bootstrap globals.
 * @returns {void}
 */
export function validateGalleryBootstrapData(windowObj = window) {
  const galleryWindow = /** @type {GalleryWindow} */ (windowObj);
  const config = validateArtifactsConfig(galleryWindow.ARTIFACTS_CONFIG);
  validateArtifactsData(galleryWindow.ARTIFACTS_DATA, getArtifactContract(config.artifactContract));
}

/**
 * Merge runtime config from `window.ARTIFACTS_CONFIG` with built-in defaults.
 * @param {Window} [windowObj=window] - Runtime window object containing bootstrap globals.
 * @returns {Required<GalleryConfig>} Merged gallery config.
 */
export function getGalleryConfig(windowObj = window) {
  const galleryWindow = /** @type {GalleryWindow} */ (windowObj);
  const runtimeConfig = galleryWindow.ARTIFACTS_CONFIG || {};
  return {
    artifactContract: getArtifactContract(runtimeConfig.artifactContract),
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
