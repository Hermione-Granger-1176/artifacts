import globals from 'globals';

const commonRules = {
  'no-console': 'off',
  'no-undef': 'error',
  'no-eval': 'error',
  'no-implied-eval': 'error',
  'no-new-func': 'error',
  'no-script-url': 'error',
  'no-restricted-syntax': [
    'error',
    {
      selector:
        "AssignmentExpression[left.property.name=/^(inner|outer)HTML$/][right.type='TemplateLiteral']",
      message:
        'Do not assign a template literal directly to innerHTML/outerHTML. Build markup in a helper that escapes interpolated values with js/modules/html-escape.js, or use textContent/createElement.'
    }
  ]
};

export default [
  {
    ignores: ['node_modules/**', '.venv/**', '_site/**', 'locks/**', 'assets/**', 'config/**', '**/vendor/**']
  },
  {
    files: ['js/**/*.js', 'apps/**/*.js'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        ...globals.browser
      }
    },
    rules: commonRules
  },
  {
    files: ['tests/js/**/*.js', '.github/actions/verified-commit/**/*.mjs', '.github/actions/deploy-site/**/*.mjs', 'scripts/**/*.mjs', 'eslint.config.js'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        ...globals.node
      }
    },
    rules: commonRules
  }
];
