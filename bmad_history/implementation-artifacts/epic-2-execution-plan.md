# Epic 2: Plano de Execução com Codex CLI

## Visão Geral

Execução das 7 stories do Epic 2 em waves paralelas usando `codex exec` com git worktrees para isolamento. Cada wave agrupa stories que podem rodar simultaneamente sem conflitos de arquivo.

## Análise de Dependências entre Stories

```
2.1 (Dispatch) ──────────┐
                          ├──→ 2.3 (Auto-Unblock)
2.2 (Subprocesses) ──────┘

2.4 (Thread Plumbing) ──→ 2.5 (Completion Msgs) ──→ 2.6 (Thread Context)
                                                 ──→ 2.7 (Thread View UI)
```

## Análise de Conflitos de Arquivo

| Arquivo | 2.1 | 2.2 | 2.3 | 2.4 | 2.5 | 2.6 | 2.7 |
|---------|-----|-----|-----|-----|-----|-----|-----|
| `nanobot/mc/bridge.py` | W | R | W | W | W | W | - |
| `nanobot/mc/executor.py` | W | W | R | - | W | W | - |
| `nanobot/mc/types.py` | W | W | W | W | W | R | - |
| `nanobot/mc/orchestrator.py` | W | R | R | - | - | - | - |
| `nanobot/mc/gateway.py` | W | R | R | - | - | - | - |
| `dashboard/convex/messages.ts` | - | - | - | W | R | - | R |
| `dashboard/convex/steps.ts` | R | R | W | - | - | - | - |
| `dashboard/convex/tasks.ts` | R | - | W | - | - | - | - |
| `dashboard/components/*` | - | - | - | - | - | - | W |

**Legenda:** W = Write, R = Read only

## Waves de Execução

### Wave 1: Backend Foundation (2 stories paralelas)
- **2.1** — Dispatch Steps in Autonomous Mode (Python: step_dispatcher.py, orchestrator, gateway)
- **2.4** — Build Unified Thread per Task (Convex: messages.ts mutations + Python: bridge methods)

**Sem conflito direto** — 2.1 foca no dispatcher Python, 2.4 foca nas mutations Convex de mensagens. Arquivo `bridge.py` é tocado por ambos mas em métodos diferentes (step dispatch vs message posting).

**Estratégia:** Worktrees separados. Merge sequencial: 2.4 primeiro (menor scope), 2.1 depois.

### Wave 2: Execution Engine (2 stories paralelas)
- **2.2** — Execute Steps as Agent Subprocesses (Python: executor, subprocess isolation)
- **2.5** — Post Structured Completion Messages (Python: executor completion + Convex artifacts)

**Conflito em `executor.py`** — 2.2 modifica a execução de steps, 2.5 modifica o que acontece após execução. Mas são seções diferentes do arquivo.

**Estratégia:** Worktrees separados. Merge sequencial com resolução manual se necessário.

### Wave 3: Intelligence + UI (3 stories, 2 paralelas + 1 sequencial)
- **2.3** — Auto-Unblock Dependent Steps (Python: bridge + Convex: steps.ts, tasks.ts)
- **2.6** — Build Thread Context for Agents (Python: thread_context.py — novo arquivo)
- **2.7** — Render Thread View in Real-Time (Dashboard: componentes React — isolado do Python)

**2.6 e 2.7 são independentes** (Python vs React). **2.3 toca bridge.py que 2.6 também precisa.**

**Estratégia:** 2.6 + 2.7 em paralelo. 2.3 sequencial após merge de 2.6 (ou em paralelo se isolado em worktree).

## Comandos de Execução

### Setup: Criar worktrees

```bash
# Criar diretório base para worktrees
mkdir -p .claude/worktrees

# Branch base a partir do commit atual
BASE_BRANCH=novo-plano
BASE_COMMIT=$(git rev-parse HEAD)
```

### Wave 1

```bash
# Worktree para 2.1
git worktree add .claude/worktrees/story-2-1 -b story/2-1-dispatch $BASE_COMMIT
# Worktree para 2.4
git worktree add .claude/worktrees/story-2-4 -b story/2-4-thread $BASE_COMMIT

# Executar em paralelo
codex exec \
  -C .claude/worktrees/story-2-1 \
  -m gpt-5.3-codex \
  -s workspace-write \
  "$(cat <<'PROMPT'
You are implementing Story 2.1 for the nanobot-ennio project.

READ the story file at _bmad-output/implementation-artifacts/2-1-dispatch-steps-in-autonomous-mode.md

This file contains ALL the context you need: acceptance criteria, tasks/subtasks, dev notes with exact file paths, code patterns, and testing strategy.

Execute ALL tasks and subtasks in the story file:
1. Implement each task checking off subtasks as you go
2. Write tests as specified in the testing strategy
3. Run tests with: cd dashboard && npx vitest run (for TS) and uv run pytest nanobot/mc/ (for Python)
4. Update the story file: check off completed tasks, fill Dev Agent Record section

IMPORTANT:
- Follow the dev notes EXACTLY — they specify which files to create/modify
- Use existing patterns from the codebase (check the references section)
- Run tests after each major task to catch issues early
- Do NOT modify files outside the scope of this story
PROMPT
)" &

codex exec \
  -C .claude/worktrees/story-2-4 \
  -m gpt-5.3-codex \
  -s workspace-write \
  "$(cat <<'PROMPT'
You are implementing Story 2.4 for the nanobot-ennio project.

READ the story file at _bmad-output/implementation-artifacts/2-4-build-unified-thread-per-task.md

This file contains ALL the context you need: acceptance criteria, tasks/subtasks, dev notes with exact file paths, code patterns, and testing strategy.

Execute ALL tasks and subtasks in the story file:
1. Implement each task checking off subtasks as you go
2. Write tests as specified in the testing strategy
3. Run tests with: cd dashboard && npx vitest run (for TS) and uv run pytest nanobot/mc/ (for Python)
4. Update the story file: check off completed tasks, fill Dev Agent Record section

IMPORTANT:
- Follow the dev notes EXACTLY — they specify which files to create/modify
- Use existing patterns from the codebase (check the references section)
- Run tests after each major task to catch issues early
- Do NOT modify files outside the scope of this story
PROMPT
)" &

wait
echo "Wave 1 complete"
```

### Merge Wave 1

```bash
# Merge 2.4 primeiro (menor scope)
git checkout $BASE_BRANCH
git merge story/2-4-thread --no-edit
# Merge 2.1
git merge story/2-1-dispatch --no-edit
# Se houver conflitos: resolver manualmente, depois git merge --continue

# Rodar testes integrados
cd dashboard && npx vitest run && cd ..
uv run pytest nanobot/mc/

# Limpar worktrees
git worktree remove .claude/worktrees/story-2-1
git worktree remove .claude/worktrees/story-2-4

# Novo base commit para wave 2
BASE_COMMIT=$(git rev-parse HEAD)
```

### Wave 2

```bash
git worktree add .claude/worktrees/story-2-2 -b story/2-2-subprocesses $BASE_COMMIT
git worktree add .claude/worktrees/story-2-5 -b story/2-5-completion $BASE_COMMIT

# Mesma estrutura de codex exec com prompts apontando para:
# _bmad-output/implementation-artifacts/2-2-execute-steps-as-agent-subprocesses.md
# _bmad-output/implementation-artifacts/2-5-post-structured-completion-messages.md

# (mesmos comandos codex exec com -C apontando para o worktree correto)
# ... (ver padrão da Wave 1)

wait
echo "Wave 2 complete"

# Merge Wave 2 (mesmo padrão)
git checkout $BASE_BRANCH
git merge story/2-5-completion --no-edit
git merge story/2-2-subprocesses --no-edit

# Testes integrados
cd dashboard && npx vitest run && cd ..
uv run pytest nanobot/mc/

git worktree remove .claude/worktrees/story-2-2
git worktree remove .claude/worktrees/story-2-5
BASE_COMMIT=$(git rev-parse HEAD)
```

### Wave 3

```bash
# 2.6 e 2.7 em paralelo (Python vs React, zero conflito)
git worktree add .claude/worktrees/story-2-6 -b story/2-6-context $BASE_COMMIT
git worktree add .claude/worktrees/story-2-7 -b story/2-7-thread-ui $BASE_COMMIT

# codex exec para 2.6 e 2.7 em paralelo (mesmo padrão)
# ...

wait

# Merge 2.6 e 2.7
git checkout $BASE_BRANCH
git merge story/2-6-context --no-edit
git merge story/2-7-thread-ui --no-edit

# Testes integrados
cd dashboard && npx vitest run && cd ..
uv run pytest nanobot/mc/

git worktree remove .claude/worktrees/story-2-6
git worktree remove .claude/worktrees/story-2-7
BASE_COMMIT=$(git rev-parse HEAD)

# Agora 2.3 (depende de 2.1, 2.2, 2.6 — todas já mergeadas)
git worktree add .claude/worktrees/story-2-3 -b story/2-3-unblock $BASE_COMMIT

# codex exec para 2.3 (mesmo padrão)
# ...

wait

git checkout $BASE_BRANCH
git merge story/2-3-unblock --no-edit

# Testes finais integrados
cd dashboard && npx vitest run && cd ..
uv run pytest nanobot/mc/

git worktree remove .claude/worktrees/story-2-3
echo "Epic 2 complete!"
```

## Script Automatizado

Para facilitar, usar o script `run-epic2.sh` abaixo que automatiza todo o fluxo:

```bash
#!/bin/bash
set -e

PROJECT_DIR="/Users/ennio/Documents/nanobot-ennio"
WORKTREE_DIR="$PROJECT_DIR/.claude/worktrees"
BASE_BRANCH="novo-plano"
MODEL="gpt-5.3-codex"

cd "$PROJECT_DIR"
mkdir -p "$WORKTREE_DIR"

# Função helper para criar prompt de execução
make_prompt() {
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

run_story() {
  local worktree="$1"
  local story_file="$2"
  local prompt
  prompt=$(make_prompt "$story_file")
  codex exec -C "$worktree" -m "$MODEL" -s workspace-write "$prompt"
}

merge_branch() {
  local branch="$1"
  git checkout "$BASE_BRANCH"
  git merge "$branch" --no-edit || {
    echo "CONFLICT merging $branch — resolve manually then run: git merge --continue"
    exit 1
  }
}

run_tests() {
  echo "Running integrated tests..."
  (cd dashboard && npx vitest run) || { echo "TS tests failed!"; exit 1; }
  uv run pytest nanobot/mc/ || { echo "Python tests failed!"; exit 1; }
  echo "All tests passed."
}

cleanup_worktree() {
  local name="$1"
  git worktree remove "$WORKTREE_DIR/$name" --force 2>/dev/null || true
  git branch -D "story/$name" 2>/dev/null || true
}

# ============================================
# WAVE 1: 2.1 (dispatch) + 2.4 (thread)
# ============================================
echo "=== WAVE 1 ==="
BASE_COMMIT=$(git rev-parse HEAD)

git worktree add "$WORKTREE_DIR/2-1" -b story/2-1 "$BASE_COMMIT"
git worktree add "$WORKTREE_DIR/2-4" -b story/2-4 "$BASE_COMMIT"

run_story "$WORKTREE_DIR/2-1" "_bmad-output/implementation-artifacts/2-1-dispatch-steps-in-autonomous-mode.md" &
PID_21=$!
run_story "$WORKTREE_DIR/2-4" "_bmad-output/implementation-artifacts/2-4-build-unified-thread-per-task.md" &
PID_24=$!

wait $PID_21 || { echo "Story 2.1 failed"; exit 1; }
wait $PID_24 || { echo "Story 2.4 failed"; exit 1; }

merge_branch "story/2-4"
merge_branch "story/2-1"
run_tests
cleanup_worktree "2-1"
cleanup_worktree "2-4"

# ============================================
# WAVE 2: 2.2 (subprocesses) + 2.5 (completion)
# ============================================
echo "=== WAVE 2 ==="
BASE_COMMIT=$(git rev-parse HEAD)

git worktree add "$WORKTREE_DIR/2-2" -b story/2-2 "$BASE_COMMIT"
git worktree add "$WORKTREE_DIR/2-5" -b story/2-5 "$BASE_COMMIT"

run_story "$WORKTREE_DIR/2-2" "_bmad-output/implementation-artifacts/2-2-execute-steps-as-agent-subprocesses.md" &
PID_22=$!
run_story "$WORKTREE_DIR/2-5" "_bmad-output/implementation-artifacts/2-5-post-structured-completion-messages.md" &
PID_25=$!

wait $PID_22 || { echo "Story 2.2 failed"; exit 1; }
wait $PID_25 || { echo "Story 2.5 failed"; exit 1; }

merge_branch "story/2-5"
merge_branch "story/2-2"
run_tests
cleanup_worktree "2-2"
cleanup_worktree "2-5"

# ============================================
# WAVE 3: 2.6 (context) + 2.7 (UI) paralelas, depois 2.3 (unblock)
# ============================================
echo "=== WAVE 3a ==="
BASE_COMMIT=$(git rev-parse HEAD)

git worktree add "$WORKTREE_DIR/2-6" -b story/2-6 "$BASE_COMMIT"
git worktree add "$WORKTREE_DIR/2-7" -b story/2-7 "$BASE_COMMIT"

run_story "$WORKTREE_DIR/2-6" "_bmad-output/implementation-artifacts/2-6-build-thread-context-for-agents.md" &
PID_26=$!
run_story "$WORKTREE_DIR/2-7" "_bmad-output/implementation-artifacts/2-7-render-thread-view-in-real-time.md" &
PID_27=$!

wait $PID_26 || { echo "Story 2.6 failed"; exit 1; }
wait $PID_27 || { echo "Story 2.7 failed"; exit 1; }

merge_branch "story/2-6"
merge_branch "story/2-7"
run_tests
cleanup_worktree "2-6"
cleanup_worktree "2-7"

echo "=== WAVE 3b ==="
BASE_COMMIT=$(git rev-parse HEAD)

git worktree add "$WORKTREE_DIR/2-3" -b story/2-3 "$BASE_COMMIT"

run_story "$WORKTREE_DIR/2-3" "_bmad-output/implementation-artifacts/2-3-auto-unblock-dependent-steps.md"

merge_branch "story/2-3"
run_tests
cleanup_worktree "2-3"

echo "=== EPIC 2 COMPLETE ==="
echo "All 7 stories implemented and merged."
echo "Run final validation: git log --oneline -10"
```

## Notas Importantes

1. **Se um merge falhar com conflitos:** O script para. Resolve manualmente, roda `git merge --continue`, depois continua a partir da próxima wave.

2. **Se o codex_exec falhar em uma story:** Pode re-executar apenas aquela story no mesmo worktree com `codex exec resume`.

3. **Testes entre waves são críticos:** Não avance para a próxima wave se os testes falharem.

4. **Sprint status:** Após cada story completar, atualizar manualmente (ou via script) o `sprint-status.yaml` de `ready-for-dev` para `done`.
