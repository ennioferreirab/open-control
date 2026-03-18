# Story 28.8: Compose Provider CLI Runtime In Gateway

Status: ready-for-dev

## Story

As a Mission Control maintainer,
I want the gateway to compose the provider-cli runtime as a first-class backend dependency,
so that interactive step execution no longer relies on the legacy interactive TUI runtime.

## Acceptance Criteria

1. The gateway composes provider-cli runtime services explicitly.
2. The provider-cli strategy no longer depends on the legacy interactive session coordinator.
3. Focused backend tests prove runtime wiring is complete.
4. No dashboard/frontend work is required in this story.

## Tasks / Subtasks

- [ ] Wire provider-cli runtime dependencies in gateway
- [ ] Remove hidden coordinator dependency from the supported step path
- [ ] Add focused backend tests for runtime wiring and strategy construction

## Dev Notes

- Keep legacy runtime available only as temporary fallback until cutover is proven.
- Validation for this story is backend-only.

## References

- [Source: docs/plans/2026-03-15-provider-cli-backend-cutover-recovery-plan.md]
- [Source: docs/plans/2026-03-15-provider-cli-backend-cutover-recovery-wave-plan.md]
