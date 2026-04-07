"""Output formatters for the transcription."""

import json
import logging
from datetime import datetime
from pathlib import Path

from .transcribe import Segment

logger = logging.getLogger(__name__)


def format_txt(segments: list[Segment]) -> str:
    """Plain text format."""
    lines: list[str] = []
    for seg in segments:
        lines.append(f"[{seg.start_formatted}] {seg.speaker}: {seg.text}")
    return "\n\n".join(lines)


def format_markdown(segments: list[Segment]) -> str:
    """Markdown format with headers."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines: list[str] = [
        f"# Session Transcription",
        f"",
        f"**Transcription date:** {now}  ",
        f"**Participants:** {', '.join(sorted({s.speaker for s in segments}))}  ",
        f"**Total interventions:** {len(segments)}",
        f"",
        f"---",
        f"",
    ]

    for seg in segments:
        lines.append(f"**[{seg.start_formatted}] {seg.speaker}**  ")
        lines.append(f"{seg.text}")
        lines.append("")

    return "\n".join(lines)


def format_json(segments: list[Segment]) -> str:
    """Structured JSON format."""
    data = {
        "metadata": {
            "transcription_date": datetime.now().isoformat(),
            "total_segments": len(segments),
            "speakers": sorted({s.speaker for s in segments}),
        },
        "segments": [
            {
                "speaker": seg.speaker,
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "timestamp": seg.start_formatted,
                "text": seg.text,
            }
            for seg in segments
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


FORMATTERS = {
    "txt": format_txt,
    "markdown": format_markdown,
    "json": format_json,
}

EXTENSIONS = {
    "txt": ".txt",
    "markdown": ".md",
    "json": ".json",
}


def export_transcript(
    segments: list[Segment],
    output_dir: Path,
    fmt: str = "txt",
    filename: str = "transcript",
) -> Path:
    """Export the transcription in the specified format.

    Args:
        segments: List of sorted segments.
        output_dir: Output directory.
        fmt: Output format (txt, markdown, json).
        filename: Base filename.

    Returns:
        Path to the generated file.
    """
    if fmt not in FORMATTERS:
        raise ValueError(f"Format '{fmt}' not supported. Options: {', '.join(FORMATTERS)}")

    output_dir.mkdir(parents=True, exist_ok=True)
    ext = EXTENSIONS[fmt]
    output_path = output_dir / f"{filename}{ext}"

    content = FORMATTERS[fmt](segments)
    output_path.write_text(content, encoding="utf-8")

    logger.info("Transcription exported: %s", output_path)
    return output_path
