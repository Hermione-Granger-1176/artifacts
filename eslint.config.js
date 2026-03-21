import globals from 'globals';

const commonRules = {
  'no-console': 'off',
  'no-undef': 'error'
};

export default [
  {
    files: ['js/**/*.js'],
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
    files: ['tests/js/**/*.js', '.github/actions/verified-commit/**/*.mjs', 'scripts/**/*.mjs', 'eslint.config.js'],
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
