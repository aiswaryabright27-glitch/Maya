import globals from 'globals';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  { ignores: ['node_modules/**', 'dist/**', 'release/**', 'backend/.venv/**', '.pytest_cache/**', '**/__pycache__/**', '**/*.tsbuildinfo'] },
  {
    files: ['*.js', 'electron/**/*.cjs', 'tests-js/**/*.cjs', 'scripts/**/*.cjs'],
    languageOptions: { globals: globals.node },
    rules: { 'no-undef': 'error', 'no-unused-vars': 'error' },
  },
  {
    files: ['frontend/src/**/*.{ts,tsx}', 'vite.config.ts'],
    extends: [...tseslint.configs.recommended],
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
  },
);
