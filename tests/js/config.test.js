import test from 'node:test';
import assert from 'node:assert/strict';

import { getGalleryConfig, getTagLabel, getToolLabel } from '../../js/modules/config.js';

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
