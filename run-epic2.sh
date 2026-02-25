#!/bin/bash
set -e

PROJECT_DIR="/Users/ennio/Documents/nanobot-ennio"
WORKTREE_DIR="$PROJECT_DIR/.claude/worktrees"
BASE_BRANCH="novo-plano"
MODEL="gpt-5.3-codex"
REVIEW_MODEL="gpt-5.3-codex"

cd "$PROJECT_DIR"
mkdir -p "$WORKTREE_DIR"

# Helper: build codex dev prompt from story file
make_dev_prompt() {
  local story_file="$1"
  cat <<PROMPT
You are implementing a story for the nanobot-ennio project.

READ the story file at $story_file — it contains ALL context you need.

Execute ALL tasks and subtasks:
1. Implement each task, checking off subtasks as you go
2. Write tests as specified in the testing strategy
3. Run tests: cd dashboard && npx vitest run (TS) / uv run pytest nanobot/mc/ (Python)
4. Update the story file: check off tasks, fill Dev Agent Record

CRITICAL RULES:
- Follow dev notes EXACTLY — they specify files to create/modify
- Use existing codebase patterns (see references section)
- Run tests after each major task
- Do NOT modify files outside this story's scope
PROMPT
}

# Helper: build codex code-review prompt
make_review_prompt() {
  local story_file="$1"
  cat <<'REVIEWPROMPT'
You are performing an ADVERSARIAL Senior Developer code review for the nanobot-ennio project.

## WORKFLOW
You MUST follow the BMAD code-review workflow. Load these files IN ORDER:
1. READ _bmad/core/tasks/workflow.xml (the workflow execution engine)
2. READ _bmad/bmm/workflows/4-implementation/code-review/workflow.yaml (the workflow config)
3. READ _bmad/bmm/workflows/4-implementation/code-review/instructions.xml (the review instructions)

## TARGET STORY
REVIEWPROMPT
  echo "Review the story file at: $story_file"
  cat <<'REVIEWPROMPT2'

## EXECUTION MODE
Run in YOLO mode — skip all user confirmations. When the workflow asks what to do with findings:
- Choose option 1: FIX THEM AUTOMATICALLY
- Fix ALL HIGH and MEDIUM severity issues in the code
- Add/update tests as needed
- Update the story file with fixes applied and completion status
- Update sprint-status.yaml if the story reaches "done" status

## REVIEW REQUIREMENTS
- Find 3-10 specific issues minimum — NO lazy "looks good" reviews
- Validate EVERY acceptance criterion against actual implementation
- Verify EVERY task marked [x] is actually implemented
- Check code quality, test quality, architecture compliance
- After fixing, run tests: cd dashboard && npx vitest run (TS) / uv run pytest nanobot/mc/ (Python)
- Commit fixes with message: "review: fix findings for story X.Y"
REVIEWPROMPT2
}

# Helper: run codex dev on a worktree
run_story() {
  local worktree="$1"
  local story_file="$2"
  local prompt
  prompt=$(make_dev_prompt "$story_file")
  echo "[$(date +%H:%M:%S)] DEV Starting: $story_file"
  codex exec -C "$worktree" -m "$MODEL" -s workspace-write "$prompt"
  echo "[$(date +%H:%M:%S)] DEV Finished: $story_file"
}

# Helper: run codex code-review on a worktree
run_review() {
  local worktree="$1"
  local story_file="$2"
  local prompt
  prompt=$(make_review_prompt "$story_file")
  echo "[$(date +%H:%M:%S)] REVIEW Starting: $story_file"
  codex exec -C "$worktree" -m "$REVIEW_MODEL" -s workspace-write "$prompt"
  echo "[$(date +%H:%M:%S)] REVIEW Finished: $story_file"
}

# Helper: run dev + review sequentially on same worktree
run_story_with_review() {
  local worktree="$1"
  local story_file="$2"
  run_story "$worktree" "$story_file"
  run_review "$worktree" "$story_file"
}

# Helper: merge a branch into base
merge_branch() {
  local branch="$1"
  echo "Merging $branch..."
  git checkout "$BASE_BRANCH"
  git merge "$branch" --no-edit || {
    echo "CONFLICT merging $branch — resolve manually then run: git merge --continue"
    echo "After resolving, re-run this script from the current wave."
    exit 1
  }
}

# Helper: run all tests
run_tests() {
  echo "Running integrated tests..."
  (cd "$PROJECT_DIR/dashboard" && npx vitest run) || { echo "TS tests failed!"; exit 1; }
  (cd "$PROJECT_DIR" && uv run pytest nanobot/mc/) || { echo "Python tests failed!"; exit 1; }
  echo "All tests passed."
}

# Helper: cleanup worktree and branch
cleanup_worktree() {
  local name="$1"
  git worktree remove "$WORKTREE_DIR/$name" --force 2>/dev/null || true
  git branch -D "story/$name" 2>/dev/null || true
}

# ============================================
# WAVE 1: 2.1 (dispatch) + 2.4 (thread)
# ============================================
echo ""
echo "========================================="
echo "  WAVE 1: Stories 2.1 + 2.4 (dev + review)"
echo "========================================="
BASE_COMMIT=$(git rev-parse HEAD)

git worktree add "$WORKTREE_DIR/2-1" -b story/2-1 "$BASE_COMMIT"
git worktree add "$WORKTREE_DIR/2-4" -b story/2-4 "$BASE_COMMIT"

# Dev + Review run sequentially per story, but stories run in parallel
run_story_with_review "$WORKTREE_DIR/2-1" "_bmad-output/implementation-artifacts/2-1-dispatch-steps-in-autonomous-mode.md" &
PID_21=$!
run_story_with_review "$WORKTREE_DIR/2-4" "_bmad-output/implementation-artifacts/2-4-build-unified-thread-per-task.md" &
PID_24=$!

wait $PID_21 || { echo "Story 2.1 FAILED"; exit 1; }
wait $PID_24 || { echo "Story 2.4 FAILED"; exit 1; }

merge_branch "story/2-4"
merge_branch "story/2-1"
run_tests
cleanup_worktree "2-1"
cleanup_worktree "2-4"
git commit --allow-empty -m "wave-1: Stories 2.1 + 2.4 implemented, reviewed, merged" 2>/dev/null || true

# ============================================
# WAVE 2: 2.2 (subprocesses) + 2.5 (completion)
# ============================================
echo ""
echo "========================================="
echo "  WAVE 2: Stories 2.2 + 2.5 (dev + review)"
echo "========================================="
BASE_COMMIT=$(git rev-parse HEAD)

git worktree add "$WORKTREE_DIR/2-2" -b story/2-2 "$BASE_COMMIT"
git worktree add "$WORKTREE_DIR/2-5" -b story/2-5 "$BASE_COMMIT"

run_story_with_review "$WORKTREE_DIR/2-2" "_bmad-output/implementation-artifacts/2-2-execute-steps-as-agent-subprocesses.md" &
PID_22=$!
run_story_with_review "$WORKTREE_DIR/2-5" "_bmad-output/implementation-artifacts/2-5-post-structured-completion-messages.md" &
PID_25=$!

wait $PID_22 || { echo "Story 2.2 FAILED"; exit 1; }
wait $PID_25 || { echo "Story 2.5 FAILED"; exit 1; }

merge_branch "story/2-5"
merge_branch "story/2-2"
run_tests
cleanup_worktree "2-2"
cleanup_worktree "2-5"
git commit --allow-empty -m "wave-2: Stories 2.2 + 2.5 implemented, reviewed, merged" 2>/dev/null || true

# ============================================
# WAVE 3a: 2.6 (context) + 2.7 (UI)
# ============================================
echo ""
echo "========================================="
echo "  WAVE 3a: Stories 2.6 + 2.7 (dev + review)"
echo "========================================="
BASE_COMMIT=$(git rev-parse HEAD)

git worktree add "$WORKTREE_DIR/2-6" -b story/2-6 "$BASE_COMMIT"
git worktree add "$WORKTREE_DIR/2-7" -b story/2-7 "$BASE_COMMIT"

run_story_with_review "$WORKTREE_DIR/2-6" "_bmad-output/implementation-artifacts/2-6-build-thread-context-for-agents.md" &
PID_26=$!
run_story_with_review "$WORKTREE_DIR/2-7" "_bmad-output/implementation-artifacts/2-7-render-thread-view-in-real-time.md" &
PID_27=$!

wait $PID_26 || { echo "Story 2.6 FAILED"; exit 1; }
wait $PID_27 || { echo "Story 2.7 FAILED"; exit 1; }

merge_branch "story/2-6"
merge_branch "story/2-7"
run_tests
cleanup_worktree "2-6"
cleanup_worktree "2-7"
git commit --allow-empty -m "wave-3a: Stories 2.6 + 2.7 implemented, reviewed, merged" 2>/dev/null || true

# ============================================
# WAVE 3b: 2.3 (auto-unblock) — depends on all prior
# ============================================
echo ""
echo "========================================="
echo "  WAVE 3b: Story 2.3 (dev + review)"
echo "========================================="
BASE_COMMIT=$(git rev-parse HEAD)

git worktree add "$WORKTREE_DIR/2-3" -b story/2-3 "$BASE_COMMIT"

run_story_with_review "$WORKTREE_DIR/2-3" "_bmad-output/implementation-artifacts/2-3-auto-unblock-dependent-steps.md"

merge_branch "story/2-3"
run_tests
cleanup_worktree "2-3"

# ============================================
# FINAL
# ============================================
echo ""
echo "========================================="
echo "  EPIC 2 COMPLETE"
echo "========================================="
echo ""
echo "All 7 stories implemented, reviewed, and merged into $BASE_BRANCH."
echo ""
echo "Pipeline per story: codex dev -> codex review (auto-fix) -> merge -> tests"
echo ""
echo "Next steps:"
echo "  1. git log --oneline -20"
echo "  2. Verify sprint-status.yaml (reviews should have marked stories done)"
echo "  3. Consider /bmad-bmm-retrospective for Epic 2"
