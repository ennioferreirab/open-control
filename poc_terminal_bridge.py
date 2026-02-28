#!/usr/bin/env python3
"""
PoC — Terminal Bridge com Subscription Real via Convex SDK

Arquitetura:
  [Convex DB] --subscribe--> [Bridge] --send-keys--> [tmux/Claude]
  [tmux/Claude] --capture-pane--> [Bridge] --mutation--> [Convex DB]

O bridge usa `ConvexBridge.subscribe()` (blocking iterator via Convex SDK WebSocket)
em uma thread separada. Quando o Convex notifica um novo `pendingInput`, o bridge
injeta no tmux. Quando o Claude responde, o bridge escreve o output de volta no Convex.

Sem polling — event-driven puro no lado do input.
"""

from __future__ import annotations

import subprocess
import sys
import time
import threading
from pathlib import Path

# ── Resolve project root ───────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from nanobot.mc.bridge import ConvexBridge

# ── Config ─────────────────────────────────────────────────────────────────────
CONVEX_URL = "https://affable-clownfish-908.convex.cloud"
SESSION_ID = "poc-bridge-001"
TMUX_SESSION = "claude-poc"
TMUX_PANE = f"{TMUX_SESSION}:0"
STABLE_SECONDS = 2.5   # segundos sem mudança no output = Claude terminou
POLL_INTERVAL = 0.4    # intervalo de leitura do pane (local, não chama LLM)

bridge = ConvexBridge(CONVEX_URL)

# ── tmux helpers ───────────────────────────────────────────────────────────────

def tmux_send(text: str):
    """Envia texto para o pane tmux."""
    subprocess.run(["tmux", "send-keys", "-t", TMUX_PANE, text, ""], check=True)

def tmux_enter():
    """Envia Enter para o pane tmux."""
    subprocess.run(["tmux", "send-keys", "-t", TMUX_PANE, "", "Enter"], check=True)

def tmux_capture() -> str:
    """Captura o conteúdo atual do pane tmux."""
    result = subprocess.run(
        ["tmux", "capture-pane", "-t", TMUX_PANE, "-p", "-S", "-50"],
        capture_output=True, text=True
    )
    return result.stdout.strip()

def wait_for_claude_response() -> str:
    """
    Aguarda Claude terminar de responder.
    Detecta estabilidade: output não muda por STABLE_SECONDS.
    100% local — zero chamadas LLM.
    """
    print("[bridge] Aguardando resposta do Claude...", flush=True)
    last_output = ""
    stable_since = None

    while True:
        current = tmux_capture()
        if current != last_output:
            last_output = current
            stable_since = time.time()
        else:
            if stable_since and (time.time() - stable_since) >= STABLE_SECONDS:
                print("[bridge] Claude terminou de responder.", flush=True)
                return current
        time.sleep(POLL_INTERVAL)

def inject_input(text: str):
    """Injeta input no Claude via tmux. Suporta !!keys: protocol para teclas TUI."""
    print(f"[bridge] Injetando input: {repr(text)}", flush=True)

    if text.startswith("!!keys:"):
        # Parse key sequence: "!!keys:Up,Down,Enter" → individual keystrokes
        keys = text[7:].split(",")
        for key in keys:
            key = key.strip()
            if not key:
                continue
            subprocess.run(
                ["tmux", "send-keys", "-t", TMUX_PANE, key],
                check=True
            )
            print(f"[bridge] Key enviada: {key}", flush=True)
            time.sleep(0.3)
    else:
        # Regular text input
        tmux_send(text)
        time.sleep(0.2)
        tmux_enter()

_last_good_output: str = ""

def write_output_to_convex(output: str, status: str = "idle"):
    """Escreve o output do Claude no Convex."""
    global _last_good_output
    if output:
        _last_good_output = output
    bridge.mutation("terminalSessions:upsert", {
        "session_id": SESSION_ID,
        "output": output,
        "pending_input": "",
        "status": status
    })
    print(f"[bridge] Output escrito no Convex ({len(output)} chars, status={status}).", flush=True)

def set_status(status: str):
    """Atualiza apenas o status no Convex, preserving last known good output."""
    global _last_good_output
    try:
        captured = tmux_capture()
        if captured:
            _last_good_output = captured
    except Exception:
        captured = ""
    bridge.mutation("terminalSessions:upsert", {
        "session_id": SESSION_ID,
        "output": captured or _last_good_output,
        "status": status
    })
    print(f"[bridge] Status atualizado: {status}", flush=True)

# ── Subscription thread ────────────────────────────────────────────────────────

def subscription_loop():
    """
    Roda em thread separada.
    Usa ConvexBridge.subscribe() — blocking iterator via Convex SDK WebSocket.
    Recebe notificação INSTANTÂNEA quando pendingInput muda no Convex.
    Sem polling — puro event-driven.
    """
    print("[subscription] Iniciando subscription em terminalSessions:get...", flush=True)
    last_input = ""

    for snapshot in bridge.subscribe("terminalSessions:get", {"session_id": SESSION_ID}):
        if snapshot is None:
            continue

        pending = snapshot.get("pending_input", "") or ""

        # Ignora se vazio ou igual ao último processado
        if not pending or pending == last_input:
            continue

        print(f"[subscription] 🔔 Novo input detectado via Convex: {repr(pending)}", flush=True)
        last_input = pending

        try:
            # Set processing status
            set_status("processing")

            # Injeta no Claude
            inject_input(pending)

            # Aguarda resposta (local, sem LLM)
            output = wait_for_claude_response()

            # Escreve output no Convex com status idle
            write_output_to_convex(output, status="idle")

            print("[subscription] ✅ Ciclo completo. Aguardando próximo input...\n", flush=True)
        except Exception as e:
            print(f"[subscription] ❌ Erro no ciclo: {e}", flush=True)
            try:
                set_status("error")
            except Exception:
                print("[subscription] ❌ Falha ao setar status de erro no Convex", flush=True)

# ── Setup inicial ──────────────────────────────────────────────────────────────

def setup_tmux_and_claude():
    """Cria sessão tmux, abre Claude e passa pela tela de boas-vindas."""
    print("[setup] Criando sessão tmux...", flush=True)

    # Mata sessão anterior se existir
    subprocess.run(["tmux", "kill-session", "-t", TMUX_SESSION],
                   capture_output=True)
    time.sleep(0.5)

    # Cria nova sessão detached
    subprocess.run(["tmux", "new-session", "-d", "-s", TMUX_SESSION], check=True)
    time.sleep(1)

    # Abre Claude
    print("[setup] Abrindo Claude Code...", flush=True)
    tmux_send("claude")
    tmux_enter()
    time.sleep(4)

    # Bypass tela de boas-vindas (Enter confirma padrão)
    print("[setup] Bypass tela inicial...", flush=True)
    tmux_enter()
    time.sleep(2)

    # Registra estado inicial no Convex
    initial_output = tmux_capture()
    write_output_to_convex(initial_output, status="idle")
    print(f"[setup] Estado inicial registrado no Convex.", flush=True)
    print("[setup] ✅ Claude pronto. Bridge aguardando inputs via Convex.\n", flush=True)

# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    setup_tmux_and_claude()

    # Subscription roda em thread daemon
    t = threading.Thread(target=subscription_loop, daemon=True)
    t.start()

    print("=" * 60)
    print("Bridge ativa. Para enviar input, use:")
    print(f'  python -c "')
    print(f'    import sys; sys.path.insert(0, \\"{ROOT}\\")')
    print(f'    from nanobot.mc.bridge import ConvexBridge')
    print(f'    b = ConvexBridge(\\"{CONVEX_URL}\\")')
    print(f'    b.mutation(\\"terminalSessions:sendInput\\", {{\\\"session_id\\\": \\\"{SESSION_ID}\\\", \\\"input\\\": \\\"sua pergunta aqui\\\"}})')
    print(f'  "')
    print("=" * 60)
    print("Pressione Ctrl+C para encerrar.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[bridge] Encerrando...")
        subprocess.run(["tmux", "kill-session", "-t", TMUX_SESSION], capture_output=True)
        print("[bridge] Sessão tmux encerrada. Bye!")
