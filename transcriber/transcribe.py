"""Transcription engine based on faster-whisper, optimized for CPU."""

import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from faster_whisper import WhisperModel

from .audio import (
    convert_to_optimized_wav,
    discover_audio_files,
    get_speaker_name,
    split_audio_chunks,
)
from .config import TranscriptionConfig

logger = logging.getLogger(__name__)


class ProgressCallback(Protocol):
    """Protocol for reporting transcription progress."""

    def on_status(self, message: str) -> None: ...
    def on_progress(self, current: int, total: int) -> None: ...
    def on_log(self, message: str) -> None: ...


class NullProgress:
    """Null callback for when progress reporting is not needed."""

    def on_status(self, message: str) -> None:
        logger.info(message)

    def on_progress(self, current: int, total: int) -> None:
        # No-op: CLI uses Rich directly
        pass

    def on_log(self, message: str) -> None:
        logger.info(message)


@dataclass
class Segment:
    """A transcription segment with timestamp and speaker."""

    speaker: str
    start: float
    end: float
    text: str

    @property
    def start_formatted(self) -> str:
        """Format [HH:MM:SS] for timestamps."""
        h, remainder = divmod(int(self.start), 3600)
        m, s = divmod(remainder, 60)
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"


def _load_model(config: TranscriptionConfig, progress: ProgressCallback | None = None) -> WhisperModel:
    """Load the faster-whisper model optimized for CPU."""
    p = progress or NullProgress()
    p.on_status(f"Loading model '{config.model_size}'...")
    p.on_log(
        f"Model: {config.model_size} | compute_type={config.compute_type} | threads={config.threads}"
    )
    model = WhisperModel(
        config.model_size,
        device="cpu",
        compute_type=config.compute_type,
        cpu_threads=config.threads,
    )
    p.on_log("Model loaded successfully")
    return model


def _transcribe_file(
    model: WhisperModel,
    audio_path: Path,
    speaker: str,
    config: TranscriptionConfig,
    chunk_offset: float = 0.0,
    progress: ProgressCallback | None = None,
) -> list[Segment]:
    """Transcribe a single audio file and return segments."""
    p = progress or NullProgress()
    segments_out: list[Segment] = []

    transcribe_kwargs: dict = {
        "beam_size": config.beam_size,
        "vad_filter": config.vad_filter,
        "vad_parameters": {"min_silence_duration_ms": 500},
    }

    if config.language:
        transcribe_kwargs["language"] = config.language

    segments, info = model.transcribe(str(audio_path), **transcribe_kwargs)

    detected_lang = info.language
    lang_prob = info.language_probability
    p.on_log(f"[{speaker}] Detected language: {detected_lang} (probability: {lang_prob:.2f})")

    for seg in segments:
        text = seg.text.strip()
        if text:
            segments_out.append(Segment(
                speaker=speaker,
                start=seg.start + chunk_offset,
                end=seg.end + chunk_offset,
                text=text,
            ))

    return segments_out


def transcribe_session(
    config: TranscriptionConfig,
    progress: ProgressCallback | None = None,
    cancel_event: threading.Event | None = None,
) -> list[Segment]:
    """Transcribe all audio files from a session.

    Args:
        config: Transcription configuration.
        progress: Optional callback for reporting progress.
        cancel_event: Optional event to cancel the transcription.

    Returns:
        List of transcribed segments (unsorted).
    """
    p = progress or NullProgress()
    config.validate()
    temp_dir = config.output_dir / "_temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    audio_files = discover_audio_files(config.input_dir)
    p.on_log(f"Found {len(audio_files)} audio files")

    model = _load_model(config, progress)

    all_segments: list[Segment] = []
    total = len(audio_files)

    for idx, audio_file in enumerate(audio_files):
        if cancel_event and cancel_event.is_set():
            p.on_log("Transcription cancelled by user")
            break

        speaker = get_speaker_name(audio_file)
        p.on_status(f"Processing: {speaker} ({idx + 1}/{total})")
        p.on_progress(idx, total)

        optimized = convert_to_optimized_wav(audio_file, temp_dir)
        chunks = split_audio_chunks(optimized, config.chunk_duration, temp_dir)

        file_segments: list[Segment] = []

        for i, chunk in enumerate(chunks):
            if cancel_event and cancel_event.is_set():
                break

            chunk_offset = i * config.chunk_duration
            p.on_log(f"Transcribing {speaker} chunk {i + 1}/{len(chunks)} (offset: {chunk_offset:.0f}s)")
            segs = _transcribe_file(model, chunk, speaker, config, chunk_offset, progress)
            file_segments.extend(segs)

        p.on_log(f"[{speaker}] {len(file_segments)} segments transcribed")
        all_segments.extend(file_segments)

    p.on_progress(total, total)
    p.on_log(f"Total segments transcribed: {len(all_segments)}")

    _cleanup_temp(temp_dir)

    return all_segments


def _cleanup_temp(temp_dir: Path) -> None:
    """Remove temporary conversion files."""
    import shutil

    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.debug("Temporary directory removed: %s", temp_dir)
