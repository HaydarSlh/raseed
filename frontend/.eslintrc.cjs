// ESLint config for the Raseed SPA — feeds the CI lint gate (stack-independent).
module.exports = {
  root: true,
  env: { browser: true, es2020: true },
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
  ],
  parser: '@typescript-eslint/parser',
  parserOptions: { ecmaVersion: 'latest', sourceType: 'module' },
  plugins: ['react-hooks', '@typescript-eslint'],
  ignorePatterns: ['dist', 'node_modules', '.eslintrc.cjs', 'vite.config.ts'],
  rules: {
    'react-hooks/rules-of-hooks': 'error',
    'react-hooks/exhaustive-deps': 'warn',
  },
};
