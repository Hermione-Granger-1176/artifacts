import test from 'node:test';
import assert from 'node:assert/strict';

import {
  getGalleryConfig,
  getTagLabel,
  getToolLabel,
  validateArtifactsConfig,
  validateArtifactsData,
  validateGalleryBootstrapData
} from '../../js/modules/config.js';

test('getGalleryConfig merges runtime config with defaults', () => {
  const config = getGalleryConfig({
    ARTIFACTS_CONFIG: {
      toolDisplayOrder: ['claude'],
      tools: {
        claude: { label: 'Claude AI' }
      }
    }
  });

  assert.equal(config.tools.claude.label, 'Claude AI');
  assert.equal(config.tools.chatgpt.label, 'ChatGPT');
});

test('tool and tag labels fall back sensibly', () => {
  const config = getGalleryConfig({ ARTIFACTS_CONFIG: {} });
  assert.equal(getToolLabel(config, 'claude'), 'Claude');
  assert.equal(getToolLabel(config, 'custom-tool'), 'Custom-tool');
  assert.equal(getTagLabel(config, 'finance'), 'Finance');
  assert.equal(getTagLabel(config, 'data-viz'), 'Data viz');
});

test('validateArtifactsData accepts generated gallery records', () => {
  const data = [
    {
      id: 'loan-amortization',
      name: 'Loan Amortization Schedule',
      description: 'Interactive loan amortization calculator.',
      tags: ['finance', 'calculator'],
      tools: ['claude'],
      url: 'apps/loan-amortization/',
      thumbnail: null
    }
  ];

  assert.equal(validateArtifactsData(data), data);
});

test('validateArtifactsData rejects invalid artifact shapes', () => {
  assert.throws(
    () => validateArtifactsData({}),
    /window\.ARTIFACTS_DATA must be an array/
  );

  assert.throws(
    () => validateArtifactsData([
      { id: 'artifact-1', name: 'Artifact 1', tags: [], tools: [], url: 42 }
    ]),
    /window\.ARTIFACTS_DATA\[0\]\.url must be a string/
  );

  assert.throws(
    () => validateArtifactsData([
      {
        id: 'artifact-1',
        name: 'Artifact 1',
        tags: ['ok', 42],
        tools: [],
        url: 'apps/artifact-1/'
      }
    ]),
    /window\.ARTIFACTS_DATA\[0\]\.tags\[1\] must be a string/
  );
});

test('validateArtifactsConfig accepts expected runtime config shape', () => {
  const config = {
    toolDisplayOrder: ['claude', 'chatgpt'],
    tagDisplayOrder: ['finance'],
    tools: {
      claude: { label: 'Claude' }
    },
    tags: {
      finance: { label: 'Finance' }
    }
  };

  assert.equal(validateArtifactsConfig(config), config);
});

test('validateArtifactsConfig rejects invalid config shapes', () => {
  assert.throws(
    () => validateArtifactsConfig(null),
    /window\.ARTIFACTS_CONFIG must be an object/
  );

  assert.throws(
    () => validateArtifactsConfig({ toolDisplayOrder: ['claude', 3] }),
    /window\.ARTIFACTS_CONFIG\.toolDisplayOrder\[1\] must be a string/
  );

  assert.throws(
    () => validateArtifactsConfig({ tools: { claude: { label: 5 } } }),
    /window\.ARTIFACTS_CONFIG\.tools\.claude\.label must be a string/
  );

  assert.throws(
    () => validateArtifactsConfig({ tags: { finance: {} } }),
    /window\.ARTIFACTS_CONFIG\.tags\.finance\.label must be a string/
  );
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
