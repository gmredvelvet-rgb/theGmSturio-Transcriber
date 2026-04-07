"""Automatic transcription summarization using Ollama (local AI).

Uses models like mistral or llama3.2 that run well on CPU with 24GB RAM.
Ollama must be installed and running: https://ollama.com
"""

import json
import logging
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_URL = "http://localhost:11434"


def _api_url(base_url: str, endpoint: str) -> str:
    """Build the full Ollama API URL."""
    return f"{base_url.rstrip('/')}/api/{endpoint}"

# Recommended models for CPU with 24GB RAM (from lower to higher quality)
AVAILABLE_MODELS = ("mistral", "llama3.2", "llama3.1:8b", "gemma2:9b")
DEFAULT_MODEL = "mistral"

# Optimized prompt for RPG sessions
SUMMARY_SYSTEM_PROMPT = """You are an expert chronicler of tabletop role-playing games.
Your job is to create narrative summaries of game sessions from transcriptions.

Rules:
- Write in third person and past tense, like a fantasy narrator.
- Identify player characters (PCs) and NPCs mentioned by the GM/DM.
- Organize the summary into sections: Main Events, Important Decisions, Combats, NPCs Encountered.
- Include relevant plot details and discovered clues.
- Keep an epic but concise tone.
- If you detect the campaign name or setting, include it.
- Write in the same language as the transcription."""

SUMMARY_USER_PROMPT = """Analyze the following RPG session transcription and generate:

1. **Narrative Summary** — A prose summary of what happened in the session (3-5 paragraphs).
2. **Main Events** — List of key events.
3. **Important Decisions** — Decisions made by the players.
4. **NPCs Encountered** — List of NPCs mentioned with brief description.
5. **Clues and Hooks** — Relevant information for future sessions.
6. **Highlights** — Epic, funny, or memorable moments.

---
TRANSCRIPTION:
{transcript}
---

Generate the full summary:"""


def check_ollama_running(base_url: str = DEFAULT_OLLAMA_URL) -> bool:
    """Check if Ollama is running at the given URL."""
    try:
        req = Request(_api_url(base_url, "tags"), method="GET")
        with urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except (URLError, OSError):
        return False


def list_ollama_models(base_url: str = DEFAULT_OLLAMA_URL) -> list[str]:
    """List available models in Ollama."""
    try:
        req = Request(_api_url(base_url, "tags"), method="GET")
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return [m["name"] for m in data.get("models", [])]
    except (URLError, OSError, KeyError):
        return []


def _truncate_transcript(transcript: str, max_chars: int = 12000) -> str:
    """Truncate transcript if too long for the model's context.

    Keeps beginning and end to preserve narrative context.
    """
    if len(transcript) <= max_chars:
        return transcript

    half = max_chars // 2
    return (
        transcript[:half]
        + "\n\n[... MIDDLE SECTION OMITTED DUE TO LENGTH ...]\n\n"
        + transcript[-half:]
    )


def generate_summary(
    transcript: str,
    model: str = DEFAULT_MODEL,
    callback: callable = None,
    base_url: str = DEFAULT_OLLAMA_URL,
) -> str:
    """Generate a summary of the transcription using Ollama.

    Args:
        transcript: Full transcription text.
        model: Ollama model name to use.
        callback: Optional function to report progress (receives partial text).

    Returns:
        AI-generated summary.
    """
    if not check_ollama_running(base_url):
        raise ConnectionError(
            f"Ollama not detected at {base_url}\n"
            "Install it from https://ollama.com and run: ollama serve\n"
            "If you use a different port or host, change the URL in the settings."
        )

    truncated = _truncate_transcript(transcript)
    prompt = SUMMARY_USER_PROMPT.format(transcript=truncated)

    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "system": SUMMARY_SYSTEM_PROMPT,
        "stream": True,
        "options": {
            "temperature": 0.7,
            "top_p": 0.9,
            "num_predict": 2048,
        },
    }).encode("utf-8")

    req = Request(
        _api_url(base_url, "generate"),
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    full_response = []

    try:
        with urlopen(req, timeout=300) as resp:
            for line in resp:
                if not line.strip():
                    continue
                try:
                    chunk = json.loads(line.decode())
                    token = chunk.get("response", "")
                    if token:
                        full_response.append(token)
                        if callback:
                            callback(token)
                    if chunk.get("done", False):
                        break
                except json.JSONDecodeError:
                    continue

    except URLError as e:
        raise ConnectionError(f"Error connecting to Ollama: {e}") from e

    result = "".join(full_response)
    logger.info("Summary generated: %d characters", len(result))
    return result


def save_summary(summary: str, output_path: Path) -> Path:
    """Save the summary to a text file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(summary, encoding="utf-8")
    logger.info("Summary saved to: %s", output_path)
    return output_path
