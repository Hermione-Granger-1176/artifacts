import test from 'node:test';
import assert from 'node:assert/strict';

import {
  getGalleryConfig,
  getTagLabel,
  getToolLabel,
  validateArtifactsConfig,
  validateArtifactsData,
  validateGalleryBootstrapData
} from '../../../js/modules/gallery/config.js';

const CONTRACT = {
  artifactIdPattern: '^[a-z0-9]+(?:-[a-z0-9]+)*$',
  artifactBasePath: 'apps',
  thumbnailFile: 'thumbnail.webp'
};

/** A config with every key scripts/build/index_outputs.py emits. */
function createConfig(overrides = {}) {
  return {
    artifactContract: { ...CONTRACT },
    toolDisplayOrder: ['claude', 'chatgpt'],
    tagDisplayOrder: ['finance'],
    tools: { claude: { label: 'Claude' } },
    tags: { finance: { label: 'Finance' } },
    ...overrides
  };
}

/** A generated record for `id`, with its canonical url and thumbnail. */
function createRecord(id, overrides = {}) {
  return {
    id,
    name: 'Artifact',
    tags: [],
    tools: [],
    url: `apps/${id}/`,
    thumbnail: `apps/${id}/thumbnail.webp`,
    ...overrides
  };
}

test('getGalleryConfig returns the validated runtime config', () => {
  const config = createConfig();
  assert.equal(getGalleryConfig({ ARTIFACTS_CONFIG: config }), config);
});

test('tool and tag labels fall back to the capitalized identifier', () => {
  const config = createConfig();
  assert.equal(getToolLabel(config, 'claude'), 'Claude');
  assert.equal(getToolLabel(config, 'custom-tool'), 'Custom-tool');
  assert.equal(getToolLabel(config, ''), '');
  assert.equal(getTagLabel(config, 'finance'), 'Finance');
  assert.equal(getTagLabel(config, 'data-viz'), 'Data viz');
});

test('validateArtifactsData accepts generated gallery records', () => {
  const data = [
    createRecord('loan-amortization', {
      name: 'Loan Amortization Schedule',
      description: 'Interactive loan amortization calculator.',
      tags: ['finance', 'calculator'],
      tools: ['claude']
    }),
    createRecord('no-description', { description: null })
  ];

  assert.equal(validateArtifactsData(data, CONTRACT), data);
});

test('validateArtifactsData follows the contract it is given', () => {
  const data = [
    createRecord('loan-amortization', {
      url: 'demos/loan-amortization/',
      thumbnail: 'demos/loan-amortization/preview.webp'
    })
  ];

  const contract = {
    artifactIdPattern: '^[a-z0-9]+(?:-[a-z0-9]+)*$',
    artifactBasePath: 'demos',
    thumbnailFile: 'preview.webp'
  };

  assert.equal(validateArtifactsData(data, contract), data);
});

test('validateArtifactsData uses full-match semantics for contract id patterns', () => {
  const contract = { ...CONTRACT, artifactIdPattern: 'artifact' };

  assert.throws(
    () => validateArtifactsData([createRecord('artifact-extra')], contract),
    /window\.ARTIFACTS_DATA\[0\]\.id must match the artifact id pattern/
  );
});

test('validateArtifactsData enforces safe repo-relative paths', () => {
  const cases = [
    [{ url: 'https://example.com/loan-amortization/' }, /\.url must be a repo-relative path/],
    [{ url: 'javascript%3Aalert(1)' }, /\.url must not use a javascript URL/],
    [{ thumbnail: 'apps/other-artifact/thumbnail.webp' }, /\.thumbnail must use the same artifact id/],
    [{ thumbnail: 'data%3Aimage/png;base64,AAAA' }, /\.thumbnail must not use a data URL/],
    [
      { thumbnail: 'apps/loan-amortization/%2E%2E/thumbnail.webp' },
      /\.thumbnail must not contain path traversal segments/
    ]
  ];

  for (const [overrides, message] of cases) {
    assert.throws(
      () => validateArtifactsData([createRecord('loan-amortization', overrides)], CONTRACT),
      message
    );
  }
});

test('validateArtifactsData requires kebab-case ids and matching urls', () => {
  assert.throws(
    () => validateArtifactsData([createRecord('LoanTool')], CONTRACT),
    /window\.ARTIFACTS_DATA\[0\]\.id must match the artifact id pattern/
  );

  assert.throws(
    () => validateArtifactsData([createRecord('loan-tool', { url: 'apps/other-tool/' })], CONTRACT),
    /window\.ARTIFACTS_DATA\[0\]\.url must use the same artifact id/
  );
});

test('validateArtifactsData rejects invalid artifact shapes', () => {
  assert.throws(
    () => validateArtifactsData({}, CONTRACT),
    /window\.ARTIFACTS_DATA must be an array/
  );

  const cases = [
    [{ url: 42 }, /\[0\]\.url must be a string/],
    [{ thumbnail: 42 }, /\[0\]\.thumbnail must be a string/],
    [{ thumbnail: null }, /\[0\]\.thumbnail must be a string/],
    [{ description: 42 }, /\[0\]\.description must be a string or null/],
    [{ tags: ['ok', 42] }, /\[0\]\.tags\[1\] must be a string/]
  ];

  for (const [overrides, message] of cases) {
    assert.throws(() => validateArtifactsData([createRecord('artifact-1', overrides)], CONTRACT), message);
  }
});

test('validateArtifactsConfig accepts the generated config shape', () => {
  const config = createConfig();
  assert.equal(validateArtifactsConfig(config), config);
});

test('validateArtifactsConfig rejects invalid config shapes', () => {
  assert.throws(
    () => validateArtifactsConfig(null),
    /window\.ARTIFACTS_CONFIG must be an object/
  );

  const cases = [
    [{ toolDisplayOrder: undefined }, /window\.ARTIFACTS_CONFIG\.toolDisplayOrder must be an array/],
    [{ toolDisplayOrder: ['claude', 3] }, /window\.ARTIFACTS_CONFIG\.toolDisplayOrder\[1\] must be a string/],
    [{ tags: undefined }, /window\.ARTIFACTS_CONFIG\.tags must be an object/],
    [{ tools: { claude: 'Claude' } }, /window\.ARTIFACTS_CONFIG\.tools\.claude must be an object/],
    [{ tools: { claude: { label: 5 } } }, /window\.ARTIFACTS_CONFIG\.tools\.claude\.label must be a string/],
    [{ tags: { finance: {} } }, /window\.ARTIFACTS_CONFIG\.tags\.finance\.label must be a string/],
    [{ artifactContract: undefined }, /window\.ARTIFACTS_CONFIG\.artifactContract must be an object/],
    [
      { artifactContract: { artifactBasePath: 'apps/nested' } },
      /window\.ARTIFACTS_CONFIG\.artifactContract\.artifactIdPattern must be a string/
    ],
    [
      { artifactContract: { ...CONTRACT, artifactBasePath: 42 } },
      /artifactContract\.artifactBasePath must be a string/
    ],
    [
      { artifactContract: { ...CONTRACT, thumbnailFile: 42 } },
      /artifactContract\.thumbnailFile must be a string/
    ],
    [
      { artifactContract: { ...CONTRACT, artifactBasePath: '' } },
      /artifactContract\.artifactBasePath must be a non-empty safe path segment/
    ],
    [
      { artifactContract: { ...CONTRACT, thumbnailFile: '' } },
      /artifactContract\.thumbnailFile must be a non-empty safe file name/
    ],
    [
      { artifactContract: { ...CONTRACT, artifactIdPattern: '(' } },
      /artifactContract\.artifactIdPattern must be a valid regular expression/
    ]
  ];

  for (const [overrides, message] of cases) {
    assert.throws(() => validateArtifactsConfig(createConfig(overrides)), message);
  }
});

test('validateGalleryBootstrapData validates config before data', () => {
  assert.throws(
    () => validateGalleryBootstrapData({
      ARTIFACTS_CONFIG: null,
      ARTIFACTS_DATA: 'not-an-array'
    }),
    /window\.ARTIFACTS_CONFIG must be an object/
  );
});

test('validateGalleryBootstrapData checks the data against the configured contract', () => {
  const config = createConfig({ artifactContract: { ...CONTRACT, artifactBasePath: 'demos' } });

  assert.throws(
    () => validateGalleryBootstrapData({ ARTIFACTS_CONFIG: config, ARTIFACTS_DATA: [createRecord('demo')] }),
    /window\.ARTIFACTS_DATA\[0\]\.url must match demos\/<artifact-id>\//
  );

  const data = [createRecord('demo', { url: 'demos/demo/', thumbnail: 'demos/demo/thumbnail.webp' })];
  assert.doesNotThrow(() => validateGalleryBootstrapData({ ARTIFACTS_CONFIG: config, ARTIFACTS_DATA: data }));
});
