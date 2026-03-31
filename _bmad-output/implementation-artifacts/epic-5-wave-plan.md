# Epic 5 Wave Plan: Convex Bandwidth Reduction and File-Backed Live

## Objective

Land the bandwidth reduction work in dependency-safe waves so the Live filesystem contract lands before the dashboard starts reading from it.

## Wave Breakdown

### Wave 1: Foundation

Stories:

- 5.1 Convex Bandwidth Audit and Operator Report
- 5.2 Dedicated Live Storage Root and Runtime Contract

Why first:

- The operator report gives a repeatable baseline.
- The runtime contract is the filesystem foundation for all Live file work.

### Wave 2: Persistence

Stories:

- 5.3 File-Backed Live Session Store and Dual-Write

Why second:

- The store owns the new write path and must exist before any read migration.

### Wave 3: Read-Path Savings

Stories:

- 5.4 Live File Read API and Dashboard Consumer Migration
- 5.6 Command Palette Projected Search
- 5.7 Thread Message Overflow Hardening

Why parallel:

- They touch different read surfaces and can be tested independently once the storage contract is stable.

### Wave 4: Cutover

Stories:

- 5.5 File-Only Live Cutover and SessionActivityLog Deprecation

Why last:

- The dashboard and store must already be file-backed before transcript bytes stop going to Convex.

## Verification Gates

- Wave 1: report script runs and live-home tests pass
- Wave 2: file-backed live store tests pass
- Wave 3: Live hook/API tests and command palette tests pass
- Wave 4: no new live transcript bytes are written to Convex
