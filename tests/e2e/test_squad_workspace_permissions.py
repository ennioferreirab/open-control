"""E2E: instagram-post-squad-v3 two-step workflow — workspace permission failure.

Runs REAL Claude Code CLI inside the Docker container to demonstrate that
the Image Generator agent cannot access task workspace files due to workspace
preparation gaps and sandbox restrictions.

Workflow simulated:
  Step 9: Post Designer ("Cria a direção visual") — simulated, writes output files
  Step 10: Image Generator ("Gera imagens e slides") — REAL CC CLI, 6 tool iterations

After 6 tool iterations the CC process is killed. The captured tool I/O is
analyzed to show the agent is lost: it cannot find the visual direction from
step 9, cannot locate the generate-image skill, and wastes iterations exploring.

Run with::

    docker compose exec mc uv run pytest tests/e2e/test_squad_workspace_permissions.py -m e2e -v -s

Requires: the mc container running (``make up``).
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import threading
import time
from pathlib import Path

import pytest

from claude_code.workspace import CCWorkspaceManager, sync_workspace_back
from mc.types import AgentData, task_safe_id

pytestmark = [pytest.mark.e2e, pytest.mark.timeout(180)]

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MAX_TOOL_ITERATIONS = 6
CC_TIMEOUT_SECONDS = 120

# Use the real runtime home when inside Docker, else fall back to tmp
WORKSPACE_ROOT = Path(os.environ.get("OPEN_CONTROL_HOME", ""))


def _get_workspace_root(tmp_path: Path) -> Path:
    """Return the workspace root: real /workspace inside Docker, tmp_path outside."""
    if WORKSPACE_ROOT.is_dir():
        return WORKSPACE_ROOT
    return tmp_path


# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------


def _skip_unless_cc_available():
    if shutil.which("claude") is None:
        pytest.skip("claude CLI not on PATH — run inside Docker container")


# ---------------------------------------------------------------------------
# Agent configs matching the real squad
# ---------------------------------------------------------------------------


def _image_generator_agent() -> AgentData:
    return AgentData(
        name="image-generator",
        display_name="Image Generator",
        role=(
            "Generates still images, carousel slides, and design assets from "
            "approved visual directions while ignoring reel/video tasks."
        ),
        prompt=(
            "You are the Image Generator. Read the visual direction from your "
            "task workspace and generate all required images. Use the generate-image "
            "skill to create each slide image. Save all outputs to task/output/\n\n"
            "IMPORTANT: You must find and read the visual direction document before "
            "generating any images. It contains the exact prompts for each slide."
        ),
        skills=["generate-image"],
        backend="claude-code",
    )


# ---------------------------------------------------------------------------
# Step simulation
# ---------------------------------------------------------------------------


def _simulate_step9_completion(workspace_root: Path, task_id: str) -> Path:
    """Simulate Post Designer completing step 9.

    Creates task attachments and step 9 output on the persistent volume,
    exactly as sync_workspace_back() would after a real step 9 execution.

    Returns the persistent task directory.
    """
    safe_id = task_safe_id(task_id)
    task_dir = workspace_root / "tasks" / safe_id

    # Original task attachments (uploaded by user before the workflow started)
    attachments = task_dir / "attachments"
    attachments.mkdir(parents=True, exist_ok=True)
    (attachments / "logo_adrena-removebg-preview.png").write_bytes(
        b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    )
    (attachments / "post_spec.md").write_text(
        "# Post Specification — Adrena Fitness\n\n"
        "## Post ID: POST002\n"
        "- **Type**: Post Estático\n"
        "- **Format**: Carrossel 5 slides\n"
        "- **Template**: A — Card com foto de fundo\n"
        "- **Aspect Ratio**: 1:1 (1080×1080)\n"
        "- **Brand**: Adrena\n"
        "- **Colors**: Primary #0A0A0A, Accent #00E5CC (teal)\n\n"
        "## Content per Slide\n"
        "1. Hero: Atleta em ação, fundo escuro\n"
        "2. Produto em destaque close-up\n"
        "3. Sequência de ação\n"
        "4. Card de depoimento\n"
        "5. CTA com logo Adrena\n",
        encoding="utf-8",
    )

    # Step 9 output: visual direction produced by Post Designer
    # This is what sync_workspace_back() copies from the ephemeral workspace
    # to the persistent path after step 9 completes.
    output_dir = task_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "visual_direction.md").write_text(
        "# Visual Direction — POST002 Carrossel\n\n"
        "## Photography Style\n"
        "Dark editorial extreme sports photography. Low-key dramatic lighting "
        "with teal (#00E5CC) rim light accent from the left side. Near-black "
        "background blending to dark bottom third.\n\n"
        "## Composition Rules\n"
        "- 1:1 square (1080×1080px)\n"
        "- Lower third intentionally dark and clear for text overlay\n"
        "- No embedded text, no watermarks\n"
        "- Photorealistic DSLR quality, cinematic raw energy\n\n"
        "## Slide Generation Prompts\n"
        "### Slide 1 — Hero\n"
        "Dark editorial extreme sports photography. Action athlete full-bleed "
        "shot, low-key dramatic lighting, teal rim light accent from left.\n\n"
        "### Slide 2 — Product\n"
        "Close-up fitness product on matte black surface, teal accent lighting "
        "from left, shallow depth of field, dark moody atmosphere.\n\n"
        "### Slide 3 — Action\n"
        "Dynamic motion blur athlete mid-jump, teal rim lighting, dark gym "
        "environment, high contrast editorial style.\n\n"
        "### Slide 4 — Testimonial Card\n"
        "Solid dark background with subtle teal gradient from bottom-left "
        "corner, minimal, space for text overlay.\n\n"
        "### Slide 5 — CTA\n"
        "Dark gradient background, bottom half clear for CTA text, subtle "
        "teal glow from center-bottom.\n",
        encoding="utf-8",
    )

    return task_dir


def _ensure_generate_image_skill(workspace_root: Path) -> None:
    """Ensure the generate-image skill exists in the global skills search path.

    In production, the skill lives at /app/mc/skills/generate-image/.
    The CCWorkspaceManager searches: agent-local → global workspace → vendor.
    We place it in workspace_root/workspace/skills/ (the global search path).
    """
    skill_src = Path("/app/mc/skills/generate-image")
    skill_dest = workspace_root / "workspace" / "skills" / "generate-image"

    if skill_src.is_dir() and not skill_dest.exists():
        skill_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(skill_src, skill_dest)
    elif not skill_dest.exists():
        # Fallback: create a minimal skill for testing outside Docker
        skill_dest.mkdir(parents=True, exist_ok=True)
        (skill_dest / "SKILL.md").write_text(
            "---\n"
            "name: generate-image\n"
            "description: Generate images via OpenRouter image models\n"
            "---\n\n"
            "# Generate Image\n\n"
            "Run: `uv run python .claude/skills/generate-image/scripts/generate_image.py`\n",
            encoding="utf-8",
        )
        scripts_dir = skill_dest / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "generate_image.py").write_text(
            "#!/usr/bin/env python3\nprint('placeholder')\n", encoding="utf-8"
        )


# ---------------------------------------------------------------------------
# CC CLI launcher
# ---------------------------------------------------------------------------


def _build_step10_command() -> list[str]:
    """Build the CC CLI command for the Image Generator agent (headless)."""
    return [
        "claude",
        "-p",
        (
            "Execute your task: generate the Instagram carousel images.\n\n"
            "Steps:\n"
            "1. List all files in your workspace to understand your environment\n"
            "2. Find and read the visual direction document\n"
            "3. Read the post specification from attachments\n"
            "4. Use the generate-image skill to create each slide\n"
            "5. Save all generated images to task/output/\n\n"
            "Start by listing your workspace files to see what's available."
        ),
        "--output-format",
        "stream-json",
        "--verbose",
        "--setting-sources",
        "project",
        "--permission-mode",
        "bypassPermissions",
        "--allowedTools",
        "*",
        "--max-budget-usd",
        "0.50",
        "--max-turns",
        str(MAX_TOOL_ITERATIONS + 4),
    ]


def _stream_reader(proc, event_queue: queue.Queue, stop_event: threading.Event) -> None:
    """Background thread: read NDJSON lines from CC stdout into a queue."""
    try:
        for line in proc.stdout:
            if stop_event.is_set():
                break
            text = line.decode(errors="replace").strip()
            if not text:
                continue
            try:
                event_queue.put(json.loads(text))
            except json.JSONDecodeError:
                pass
    except (OSError, ValueError):
        pass
    finally:
        event_queue.put(None)  # sentinel


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

# Keywords that indicate the agent is failing to access workspace files
ACCESS_FAILURE_KEYWORDS = [
    # CC sandbox blocks
    "was blocked",
    "only list files in the allowed",
    "only read files in the allowed",
    "only write files in the allowed",
    "only create",
    # OS-level permission errors
    "permission denied",
    "not allowed",
    # File not found (workspace preparation gap)
    "not found",
    "no such file",
    "does not exist",
    "no files found",
    # Skill/tool resolution failures
    "unknown skill",
    "tool_use_error",
]


def _extract_tool_io(events: list[dict]) -> list[dict]:
    """Parse NDJSON events into a flat list of tool call/result records."""
    tool_calls: dict[str, dict] = {}
    ordered_ids: list[str] = []

    for event in events:
        msg_type = event.get("type", "")
        content = (event.get("message") or {}).get("content", [])
        if not isinstance(content, list):
            continue

        for block in content:
            if not isinstance(block, dict):
                continue

            if msg_type == "assistant" and block.get("type") == "tool_use":
                tid = block.get("id", "")
                tool_calls[tid] = {
                    "name": block.get("name", "?"),
                    "input": block.get("input", {}),
                    "result": "",
                    "is_error": False,
                }
                ordered_ids.append(tid)

            elif msg_type == "user" and block.get("type") == "tool_result":
                tid = block.get("tool_use_id", "")
                raw = block.get("content", "")
                if isinstance(raw, list):
                    raw = "\n".join(
                        c.get("text", "") for c in raw if isinstance(c, dict)
                    )
                if tid in tool_calls:
                    tool_calls[tid]["result"] = str(raw)[:2000]
                    tool_calls[tid]["is_error"] = bool(block.get("is_error", False))

    return [tool_calls[tid] for tid in ordered_ids if tid in tool_calls]


def _classify_problems(tool_io: list[dict]) -> list[dict]:
    """Tag tool calls whose results indicate an access/permission failure."""
    problems = []
    for entry in tool_io:
        text = entry["result"].lower()
        matched = [kw for kw in ACCESS_FAILURE_KEYWORDS if kw in text]
        if matched or entry["is_error"]:
            problems.append({**entry, "matched_keywords": matched})
    return problems


def _format_tool_entry(i: int, entry: dict) -> str:
    name = entry["name"]
    inp = entry["input"]
    if name == "Bash":
        inp_str = inp.get("command", str(inp))[:150]
    elif name == "Read":
        inp_str = inp.get("file_path", str(inp))[:150]
    elif name in ("Glob", "Grep"):
        inp_str = f"pattern={inp.get('pattern', '?')} path={inp.get('path', '?')}"
    elif name == "Write":
        inp_str = inp.get("file_path", str(inp))[:150]
    else:
        inp_str = str(inp)[:150]

    error_tag = " ✗" if entry["is_error"] else " ✓"
    result_preview = entry["result"][:250].replace("\n", " ↵ ")
    return f"  [{i}] {name}{error_tag}  {inp_str}\n      → {result_preview}"


def _print_full_report(
    tool_io: list[dict],
    problems: list[dict],
    visual_direction_found: bool,
    skill_found: bool,
) -> str:
    """Print the full analysis report and return it as a string."""
    lines: list[str] = [""]
    lines.append("=" * 70)
    lines.append("E2E: Image Generator — Squad Workflow Permission Analysis")
    lines.append("=" * 70)
    lines.append(f"Tool iterations captured: {len(tool_io)}")
    lines.append(f"Access/permission failures: {len(problems)}")
    lines.append(f"Visual direction found by agent: {visual_direction_found}")
    lines.append(f"generate-image skill available: {skill_found}")
    lines.append("")

    lines.append("─── TOOL I/O LOG (chronological) ───")
    for i, entry in enumerate(tool_io, 1):
        lines.append(_format_tool_entry(i, entry))
        lines.append("")

    if problems:
        lines.append("─── FAILURES ───")
        for i, p in enumerate(problems, 1):
            kws = ", ".join(p.get("matched_keywords", [])) or "is_error=True"
            lines.append(f"  {i}. [{p['name']}] reason: {kws}")
            lines.append(f"     → {p['result'][:200]}")
            lines.append("")

    # Verdict
    lines.append("─── VERDICT ───")
    all_good = visual_direction_found and skill_found and len(problems) == 0
    if visual_direction_found:
        lines.append("  ✓ Visual direction from step 9 found and read.")
    else:
        lines.append("  ✗ Step 9 output (visual_direction.md) NOT found by agent.")
    if skill_found:
        lines.append("  ✓ generate-image skill mapped into agent workspace.")
    else:
        lines.append("  ✗ generate-image skill NOT found in workspace.")
    if problems:
        lines.append(
            f"  ✗ {len(problems)}/{len(tool_io)} tool calls hit access errors."
        )
    else:
        lines.append(f"  ✓ 0 access errors in {len(tool_io)} tool calls.")
    if all_good:
        lines.append("  → Agent is WELL-DIRECTED: has all inputs, skill works, no errors.")
    else:
        lines.append("  → Agent has ISSUES — see above.")
    lines.append("=" * 70)

    report = "\n".join(lines)
    print(report)
    return report


# ---------------------------------------------------------------------------
# E2E Test
# ---------------------------------------------------------------------------


class TestSquadWorkspacePermissionE2E:
    """Run the real CC CLI as Image Generator and observe it getting lost."""

    TASK_ID = "e2e_perm_test_002"

    def test_image_generator_lost_in_workspace_gaps(self, tmp_path: Path) -> None:
        """Step 9 completes → Step 10 starts → agent is lost.

        After 6 tool iterations we stop the CC process and analyze the output.
        The analysis shows the agent cannot find:
        - The visual direction from step 9 (not copied to ephemeral workspace)
        - The generate-image skill (not in search path)

        The agent wastes all 6 iterations exploring the filesystem instead of
        generating images.
        """
        _skip_unless_cc_available()

        ws_root = _get_workspace_root(tmp_path)

        # ── Step 9: Post Designer (simulated) ──
        task_dir = _simulate_step9_completion(ws_root, self.TASK_ID)
        assert (task_dir / "output" / "visual_direction.md").exists(), (
            "Step 9 output must exist on persistent path"
        )

        # Ensure the generate-image skill is in the search path
        _ensure_generate_image_skill(ws_root)

        # ── Step 10: Image Generator (real CC CLI) ──
        manager = CCWorkspaceManager(workspace_root=ws_root)
        agent = _image_generator_agent()
        ctx = manager.prepare("image-generator", agent, self.TASK_ID)

        # Disable MCP servers — no socket server in test
        (ctx.cwd / ".mcp.json").write_text(
            json.dumps({"mcpServers": {}}), encoding="utf-8"
        )

        # ── Pre-flight: verify the workspace gap is FIXED ──
        # With the new direct-task-dir CWD, step 9's output should already
        # be in output/ because the agent CWD IS the persistent task dir.
        task_output = ctx.cwd / "output"
        assert (task_output / "visual_direction.md").exists(), (
            "REGRESSION: visual_direction.md should now be available in output/ "
            "since the agent CWD is the persistent task directory."
        )

        # .stage directory should exist for intermediate work
        assert (ctx.cwd / "attachments" / ".stage").is_dir(), (
            "attachments/.stage/ must exist for intermediate operations"
        )

        # ── Launch CC CLI ──
        cmd = _build_step10_command()
        env = {**os.environ}
        env.setdefault("CLAUDE_CODE_BUBBLEWRAP", "1")

        proc = subprocess.Popen(
            cmd,
            cwd=str(ctx.cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        # ── Stream and capture 6 tool iterations ──
        events: list[dict] = []
        eq: queue.Queue = queue.Queue()
        stop = threading.Event()
        reader = threading.Thread(
            target=_stream_reader, args=(proc, eq, stop), daemon=True
        )
        reader.start()

        tool_turns = 0
        deadline = time.monotonic() + CC_TIMEOUT_SECONDS

        while time.monotonic() < deadline:
            try:
                msg = eq.get(timeout=2.0)
            except queue.Empty:
                if proc.poll() is not None:
                    break
                continue

            if msg is None:
                break

            events.append(msg)

            if msg.get("type") == "user":
                tool_turns += 1
                if tool_turns >= MAX_TOOL_ITERATIONS:
                    break

        # ── Stop CC process ──
        stop.set()
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)

        stderr_output = ""
        if proc.stderr:
            stderr_output = proc.stderr.read().decode(errors="replace")[:2000]

        reader.join(timeout=5)

        # ── Analysis (before cleanup so paths are still valid) ──
        tool_io = _extract_tool_io(events)
        problems = _classify_problems(tool_io)

        # Check if the agent ever found the visual direction
        all_results = " ".join(e["result"] for e in tool_io)
        visual_direction_found = "visual direction" in all_results.lower() or (
            "visual_direction.md" in all_results
        )

        # Check if the skill was available
        skill_available = (ctx.cwd / ".claude" / "skills" / "generate-image").is_dir()

        report = _print_full_report(
            tool_io, problems, visual_direction_found, skill_available
        )

        # ── Assertions ──

        assert len(events) > 0, (
            f"No events from CC CLI. stderr: {stderr_output[:500]}"
        )
        assert len(tool_io) > 0, (
            f"No tool calls captured in {len(events)} events. "
            f"CC may have failed to start. stderr: {stderr_output[:300]}"
        )

        # ── The visual direction should now be found ──
        # With direct task-dir CWD, the agent can read output/visual_direction.md
        # which was written by step 9.
        assert visual_direction_found, (
            f"The agent should have found and read the visual direction.\n"
            f"Report:\n{report}"
        )

        # ── Detect whether the agent used the actual visual direction ──
        generate_calls = [
            e for e in tool_io
            if "generate_image" in str(e.get("input", ""))
        ]

        print(f"\n{'─'*50}")
        print(
            f"RESULT: {len(tool_io)} tool calls, "
            f"{len(problems)} failures, "
            f"visual_direction found: {visual_direction_found}"
        )
        print(f"  generate-image skill available: {skill_available}")
        print(f"  generate_image.py calls: {len(generate_calls)}")
        if visual_direction_found:
            print("  ✓ Agent found the visual direction from step 9")
            print("    The cross-step output sharing now works.")
        else:
            print("  ✗ Agent did NOT find visual direction — still broken")
        if skill_available:
            print("  ✓ generate-image skill correctly mapped")
        else:
            print("  ✗ generate-image skill NOT in workspace")
        print(f"{'─'*50}\n")

        # ── Cleanup test task dir ──
        safe_id = task_safe_id(self.TASK_ID)
        test_task_dir = ws_root / "tasks" / safe_id
        if test_task_dir.exists() and "e2e_perm_test" in safe_id:
            shutil.rmtree(test_task_dir, ignore_errors=True)
