"""Merge and sort segments from multiple audio tracks."""

import logging

from .transcribe import Segment

logger = logging.getLogger(__name__)


def merge_and_sort(segments: list[Segment]) -> list[Segment]:
    """Sort all segments by start timestamp.

    This reconstructs the real conversation from separate
    per-user audio tracks (Craig Bot format).
    """
    sorted_segments = sorted(segments, key=lambda s: s.start)
    logger.info("Segments sorted chronologically: %d", len(sorted_segments))
    return sorted_segments


def merge_consecutive(segments: list[Segment], gap_threshold: float = 1.5) -> list[Segment]:
    """Merge consecutive segments from the same speaker if close together.

    This reduces fragmentation in the final output.

    Args:
        segments: List of already sorted segments.
        gap_threshold: Maximum gap in seconds to merge.
    """
    if not segments:
        return []

    merged: list[Segment] = [segments[0]]

    for seg in segments[1:]:
        prev = merged[-1]
        if (
            seg.speaker == prev.speaker
            and (seg.start - prev.end) <= gap_threshold
        ):
            merged[-1] = Segment(
                speaker=prev.speaker,
                start=prev.start,
                end=seg.end,
                text=f"{prev.text} {seg.text}",
            )
        else:
            merged.append(seg)

    logger.info(
        "Segments merged: %d -> %d",
        len(segments), len(merged),
    )
    return merged
