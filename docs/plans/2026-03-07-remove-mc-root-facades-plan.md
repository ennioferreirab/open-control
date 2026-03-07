# Remove MC Root Facades Plan

1. Add package-level reexports for runtime and contexts.
2. Rewrite imports and patch targets away from deleted root modules.
3. Update CLI/process entrypoints to run `mc.runtime.gateway`.
4. Tighten architecture tests for a minimal `mc/` root.
5. Delete the remaining root facade modules.
6. Run the `tests/mc` suite and merge once the branch is clean.
