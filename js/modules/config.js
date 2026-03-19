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

export function getToolLabel(config, tool) {
  return config.tools[tool]?.label || capitalize(tool);
}

export function getTagLabel(config, tag) {
  return config.tags[tag]?.label || capitalize(tag).replace(/-/g, ' ');
}

function capitalize(value) {
  if (!value) {
    return '';
  }

  return value.charAt(0).toUpperCase() + value.slice(1);
}
