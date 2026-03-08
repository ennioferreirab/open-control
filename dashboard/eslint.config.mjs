import { defineConfig, globalIgnores } from "eslint/config";
import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

export default defineConfig([
  ...nextCoreWebVitals,
  ...nextTypescript,
  globalIgnores(["convex/_generated"]),
  {
    files: ["components/**/*.{ts,tsx}", "tests/components/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          paths: [
            {
              name: "convex/react",
              message:
                "Use feature hooks or view-model hooks instead of importing convex/react in UI-facing modules.",
            },
          ],
        },
      ],
    },
  },
]);
