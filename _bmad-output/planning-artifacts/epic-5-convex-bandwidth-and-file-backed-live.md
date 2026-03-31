# Epic 5: Convex Bandwidth Reduction and File-Backed Live

## Epic Goal

Reduce Convex read bandwidth at the dashboard and move live transcript storage to a dedicated filesystem root so Live can survive independently from the main workspace.

## Business Value

- Cuts the largest re-evaluation hotspots in the dashboard.
- Makes Live transcripts durable outside Convex payload limits.
- Lets operators inspect, delete, and migrate Live data without touching task/workspace state.

## Scope

- Convex bandwidth operator report
- Dedicated live filesystem root
- File-backed live transcript persistence
- File-backed live read APIs and dashboard consumer migration
- Live cutover away from `sessionActivityLog`
- Command palette query reduction
- Thread message overflow hardening

## Out of Scope

- Replacing the dashboard thread tab
- Shared cloud object storage
- Non-local live transcript replication

## Story Set

1. 5.1 Convex Bandwidth Audit and Operator Report
2. 5.2 Dedicated Live Storage Root and Runtime Contract
3. 5.3 File-Backed Live Session Store and Dual-Write
4. 5.4 Live File Read API and Dashboard Consumer Migration
5. 5.5 File-Only Live Cutover and SessionActivityLog Deprecation
6. 5.6 Command Palette Projected Search
7. 5.7 Thread Message Overflow Hardening

## Recommended Execution Order

1. 5.1 and 5.2 in parallel
2. 5.3 after 5.2
3. 5.4, 5.6, and 5.7 in parallel after 5.3
4. 5.5 after the Live read path is stable

## Dependencies

- Story 5.2 is the filesystem contract foundation.
- Story 5.3 depends on 5.2.
- Story 5.4 depends on 5.3.
- Story 5.5 depends on 5.4.
- Story 5.6 depends on the existing `AppDataProvider` pattern from PERF-1.
- Story 5.7 depends on the existing overflow helper in `mc/bridge/overflow.py`.
