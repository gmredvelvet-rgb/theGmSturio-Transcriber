"""Central project configuration."""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Literal

# Supported audio extensions
SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".aac"}

# Audio conversion parameters
AUDIO_SAMPLE_RATE = 16000
AUDIO_CHANNELS = 1

# Available models for faster-whisper
AVAILABLE_MODELS = ("small", "medium", "large-v3")
DEFAULT_MODEL = "medium"

# Compute type optimized for CPU (no CUDA)
COMPUTE_TYPE = "int8"

# Maximum chunk duration in seconds (30 min)
CHUNK_DURATION_SECONDS = 1800

# Supported output formats
OUTPUT_FORMATS = ("txt", "markdown", "json")


@dataclass
class TranscriptionConfig:
    """Configuration for a transcription session."""

    input_dir: Path = field(default_factory=lambda: Path("."))
    output_dir: Path = field(default_factory=lambda: Path("output"))
    model_size: str = DEFAULT_MODEL
    compute_type: str = COMPUTE_TYPE
    language: str | None = None  # None = auto-detect
    output_format: Literal["txt", "markdown", "json"] = "txt"
    chunk_duration: int = CHUNK_DURATION_SECONDS
    beam_size: int = 5
    vad_filter: bool = True
    threads: int = 6  # Optimized for Ryzen 5 5500 (6 cores)

    def validate(self) -> None:
        """Validate the current configuration."""
        if self.model_size not in AVAILABLE_MODELS:
            raise ValueError(
                f"Model '{self.model_size}' not supported. "
                f"Options: {', '.join(AVAILABLE_MODELS)}"
            )
        if not self.input_dir.is_dir():
            raise FileNotFoundError(
                f"Input directory not found: {self.input_dir}"
            )
