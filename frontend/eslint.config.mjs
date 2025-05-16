import { dirname } from "path";
import { fileURLToPath } from "url";
import { FlatCompat } from "@eslint/eslintrc";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const compat = new FlatCompat({
  baseDirectory: __dirname,
});

const eslintConfig = [
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  {
    rules: {
      // Désactiver la règle des apostrophes non-échappées
      "react/no-unescaped-entities": "off",

      // Désactiver l'erreur des variables non utilisées
      "@typescript-eslint/no-unused-vars": "off",

      // Ou alternativement, la transformer en avertissement et ignorer certains modèles
      // "@typescript-eslint/no-unused-vars": ["warn", {
      //   "argsIgnorePattern": "^_",
      //   "varsIgnorePattern": "^_",
      //   "caughtErrorsIgnorePattern": "^_"
      // }],
    },
  },
];

export default eslintConfig;
