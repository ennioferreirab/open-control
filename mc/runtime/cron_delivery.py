"""Cron delivery helpers extracted from the runtime gateway."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

PendingDeliveries = dict[str, tuple[str, str]]


async def _send_telegram_direct(config: Any, chat_id: str, content: str) -> None:
    """Send a Telegram message directly without going through polling."""
    from nanobot.channels.telegram import _markdown_to_telegram_html, _split_message
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
