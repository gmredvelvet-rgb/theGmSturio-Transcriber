"""Send summaries to Discord via Webhook."""

import json
import logging
from urllib.error import URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

# Discord character limit per message
DISCORD_MAX_LENGTH = 1900


def validate_webhook_url(url: str) -> bool:
    """Validate that the URL is a legitimate Discord webhook."""
    return (
        url.startswith("https://discord.com/api/webhooks/")
        or url.startswith("https://discordapp.com/api/webhooks/")
    ) and len(url) > 60


def _split_message(text: str, max_len: int = DISCORD_MAX_LENGTH) -> list[str]:
    """Split a long message into parts respecting Discord's limit."""
    if len(text) <= max_len:
        return [text]

    parts: list[str] = []
    lines = text.split("\n")
    current = ""

    for line in lines:
        if len(current) + len(line) + 1 > max_len:
            if current:
                parts.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line

    if current:
        parts.append(current)

    return parts


def send_to_discord(
    webhook_url: str,
    content: str,
    title: str = "Resumen de Sesión",
    campaign_name: str = "",
) -> bool:
    """Envía un resumen a un canal de Discord vía webhook.

    Args:
        webhook_url: URL del webhook de Discord.
        content: Texto del resumen a enviar.
        title: Título del embed.
        campaign_name: Nombre de la campaña (opcional).

    Returns:
        True si se envió correctamente.
    """
    if not validate_webhook_url(webhook_url):
        raise ValueError("URL de webhook de Discord no válida.")

    # Header embed con info de la campaña
    header = f"🎲 **{title}**"
    if campaign_name:
        header += f"\n📋 Campaña: **{campaign_name}**"
    header += "\n─────────────────────────────"

    full_text = f"{header}\n\n{content}"
    parts = _split_message(full_text)

    for i, part in enumerate(parts):
        payload = json.dumps({
            "content": part,
            "username": "TheGmStudio Transcriber",
        }).encode("utf-8")

        req = Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(req, timeout=30) as resp:
                if resp.status not in (200, 204):
                    logger.error("Discord responded with status %d", resp.status)
                    return False
        except URLError as e:
            logger.error("Error sending to Discord (part %d): %s", i + 1, e)
            raise ConnectionError(f"Error sending to Discord: {e}") from e

    logger.info("Summary sent to Discord in %d part(s)", len(parts))
    return True
