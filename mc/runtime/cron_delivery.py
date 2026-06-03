"""Cron delivery helpers extracted from the runtime gateway."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)

PendingDeliveries = dict[str, tuple[str, str]]


def _markdown_to_telegram_html(text: str) -> str:
    """Convert markdown to Telegram-safe HTML."""
    import re

    if not text:
        return ""

    code_blocks: list[str] = []

    def save_code_block(m: re.Match) -> str:
        code_blocks.append(m.group(1))
        return f"\x00CB{len(code_blocks) - 1}\x00"

    text = re.sub(r"```[\w]*\n?([\s\S]*?)```", save_code_block, text)

    inline_codes: list[str] = []

    def save_inline_code(m: re.Match) -> str:
        inline_codes.append(m.group(1))
        return f"\x00IC{len(inline_codes) - 1}\x00"

    text = re.sub(r"`([^`]+)`", save_inline_code, text)

    text = re.sub(r"^#{1,6}\s+(.+)$", r"\1", text, flags=re.MULTILINE)
    text = re.sub(r"^>\s*(.*)$", r"\1", text, flags=re.MULTILINE)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)
    text = re.sub(r"(?<![a-zA-Z0-9])_([^_]+)_(?![a-zA-Z0-9])", r"<i>\1</i>", text)
    text = re.sub(r"~~(.+?)~~", r"<s>\1</s>", text)
    text = re.sub(r"^[-*]\s+", "• ", text, flags=re.MULTILINE)

    for i, code in enumerate(inline_codes):
        escaped = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = text.replace(f"\x00IC{i}\x00", f"<code>{escaped}</code>")

    for i, code in enumerate(code_blocks):
        escaped = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = text.replace(f"\x00CB{i}\x00", f"<pre><code>{escaped}</code></pre>")

    return text


def _split_message(content: str, max_len: int = 4000) -> list[str]:
    """Split content into chunks within max_len, preferring line breaks."""
    if len(content) <= max_len:
        return [content]
    chunks: list[str] = []
    while content:
        if len(content) <= max_len:
            chunks.append(content)
            break
        cut = content[:max_len]
        pos = cut.rfind("\n")
        if pos == -1:
            pos = cut.rfind(" ")
        if pos == -1:
            pos = max_len
        chunks.append(content[:pos])
        content = content[pos:].lstrip()
    return chunks


async def _send_telegram_direct(config: Any, chat_id: str, content: str) -> None:
    """Send a Telegram message directly without going through polling."""
    from telegram import Bot

    if not chat_id.lstrip("-").isdigit():
        logger.error(
            "[gateway] Telegram delivery aborted — chat_id %r is not a numeric ID. "
            "The cron job was likely created with deliver_to set to an MC agent name "
            "instead of a Telegram chat ID. Update or recreate the cron job with the "
            "correct numeric chat_id (e.g. '986097959').",
            chat_id,
        )
        return

    token = config.channels.telegram.token
    if not token:
        logger.warning("[gateway] No Telegram token — skipping delivery")
        return

    bot = Bot(token=token)
    html = _markdown_to_telegram_html(content)
    for chunk in _split_message(html):
        await bot.send_message(chat_id=int(chat_id), text=chunk, parse_mode="HTML")


def build_on_task_completed_callback(
    config: Any,
    pending_deliveries: PendingDeliveries,
) -> Callable[[str, str], Awaitable[None]]:
    """Build the executor completion callback that performs deferred delivery."""

    async def on_task_completed(task_id: str, result: str) -> None:
        delivery = pending_deliveries.pop(task_id, None)
        if not delivery:
            return
        if not result.strip():
            logger.info(
                "[gateway] Skipping delivery for task %s — empty result (task may have failed)",
                task_id,
            )
            return

        channel, target = delivery
        try:
            if channel == "telegram":
                await _send_telegram_direct(config, target, result)
                logger.info(
                    "[gateway] Delivered cron result for task %s → telegram:%s",
                    task_id,
                    target,
                )
            else:
                logger.warning("[gateway] Delivery to '%s' not supported", channel)
        except Exception:
            logger.exception("[gateway] Failed to deliver result for task %s", task_id)

    return on_task_completed
