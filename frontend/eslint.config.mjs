// ESLint 9 flat config (eslint-config-next 16 requires it). Mirrors the rule set the
// former `next lint` default used (core-web-vitals); the stricter TypeScript preset can
// be added later once existing `any` usages are cleaned up.
import nextVitals from "eslint-config-next/core-web-vitals";

export default [
  ...nextVitals,
  {
    ignores: [".next/**", "node_modules/**", "out/**", "content/**", "next-env.d.ts"],
  },
  {
    rules: {
      // Fires on `useEffect(() => { void fetchThenSetState() })`, where setState runs after
      // an await (not synchronously). Keep visible as a warning, not a build blocker.
      "react-hooks/set-state-in-effect": "warn",
    },
  },
];
