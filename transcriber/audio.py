"""Audio processing and conversion with ffmpeg."""

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .config import AUDIO_CHANNELS, AUDIO_SAMPLE_RATE, SUPPORTED_EXTENSIONS

logger = logging.getLogger(__name__)


def _app_dir() -> Path:
    """Return the application directory (handles PyInstaller bundled mode)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


# Known paths where winget/chocolatey install ffmpeg on Windows
_FFMPEG_SEARCH_PATHS = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages",
    Path(os.environ.get("ProgramFiles", "")) / "ffmpeg" / "bin",
    Path(os.environ.get("ProgramFiles(x86)", "")) / "ffmpeg" / "bin",
    Path(os.environ.get("USERPROFILE", "")) / "scoop" / "shims",
]


def _find_ffmpeg() -> str:
    """Find the ffmpeg executable, searching bundled dir, PATH, and known locations."""
    # 1. Check bundled ffmpeg next to the executable
    bundled = _app_dir() / "ffmpeg" / "ffmpeg.exe"
    if bundled.exists():
        logger.info("Using bundled ffmpeg: %s", bundled)
        return str(bundled)

    # 2. Try normal PATH
    found = shutil.which("ffmpeg")
    if found:
        return found

    # 3. Search known installation paths (winget, etc.)
    for base in _FFMPEG_SEARCH_PATHS:
        if not base.exists():
            continue
        for match in base.rglob("ffmpeg.exe"):
            logger.info("ffmpeg found at: %s", match)
            return str(match)

    raise FileNotFoundError(
        "ffmpeg not found. Place the ffmpeg folder next to the executable,\n"
        "or install it with: winget install FFmpeg"
    )


def _find_ffprobe() -> str:
    """Find the ffprobe executable alongside ffmpeg."""
    found = shutil.which("ffprobe")
    if found:
        return found

    # ffprobe is alongside ffmpeg
    ffmpeg_path = Path(_find_ffmpeg())
    ffprobe = ffmpeg_path.parent / "ffprobe.exe"
    if ffprobe.exists():
        return str(ffprobe)

    # Fallback: search like ffmpeg
    for base in _FFMPEG_SEARCH_PATHS:
        if not base.exists():
            continue
        for match in base.rglob("ffprobe.exe"):
            return str(match)

    raise FileNotFoundError("ffprobe not found alongside ffmpeg.")


# Cache for found paths
_ffmpeg_bin: str | None = None
_ffprobe_bin: str | None = None


def _get_ffmpeg() -> str:
    global _ffmpeg_bin
    if _ffmpeg_bin is None:
        _ffmpeg_bin = _find_ffmpeg()
        logger.info("Using ffmpeg: %s", _ffmpeg_bin)
    return _ffmpeg_bin


def _get_ffprobe() -> str:
    global _ffprobe_bin
    if _ffprobe_bin is None:
        _ffprobe_bin = _find_ffprobe()
    return _ffprobe_bin


def is_supported(filepath: Path) -> bool:
    """Check if the file has a supported audio extension."""
    return filepath.suffix.lower() in SUPPORTED_EXTENSIONS


def discover_audio_files(directory: Path) -> list[Path]:
    """Discover all supported audio files in a directory."""
    files = sorted(
        f for f in directory.iterdir()
        if f.is_file() and is_supported(f)
    )
    if not files:
        raise FileNotFoundError(
            f"No audio files found in: {directory}"
        )
    logger.info("Found %d audio files", len(files))
    return files


def get_speaker_name(filepath: Path) -> str:
    """Extract the speaker name from the filename."""
    return filepath.stem


def get_audio_duration(filepath: Path) -> float:
    """Get the audio duration in seconds using ffprobe."""
    cmd = [
        _get_ffprobe(),
        "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(filepath),
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True
        )
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError) as e:
        logger.error("Error getting duration of %s: %s", filepath.name, e)
        raise RuntimeError(f"Could not get duration of {filepath.name}") from e


def convert_to_optimized_wav(input_path: Path, output_dir: Path) -> Path:
    """Convert an audio file to 16kHz mono WAV optimized for Whisper.

    If the file already meets requirements, copies it directly.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{input_path.stem}_optimized.wav"

    if output_path.exists():
        logger.debug("Optimized file already exists: %s", output_path.name)
        return output_path

    logger.info("Converting %s -> WAV mono 16kHz", input_path.name)

    cmd = [
        _get_ffmpeg(),
        "-i", str(input_path),
        "-ac", str(AUDIO_CHANNELS),
        "-ar", str(AUDIO_SAMPLE_RATE),
        "-sample_fmt", "s16",
        "-y",
        str(output_path),
    ]

    try:
        subprocess.run(
            cmd, capture_output=True, text=True, check=True
        )
    except subprocess.CalledProcessError as e:
        logger.error("Error converting %s: %s", input_path.name, e.stderr)
        raise RuntimeError(f"Failed to convert {input_path.name}") from e

    logger.info("Converted: %s (%.1f MB)", output_path.name, output_path.stat().st_size / 1e6)
    return output_path


def split_audio_chunks(filepath: Path, chunk_duration: int, output_dir: Path) -> list[Path]:
    """Split a long audio file into chunks for memory-efficient processing.

    Args:
        filepath: Path to the audio file.
        chunk_duration: Maximum duration of each chunk in seconds.
        output_dir: Directory to save the chunks.

    Returns:
        List of paths to the generated chunks.
    """
    duration = get_audio_duration(filepath)

    if duration <= chunk_duration:
        return [filepath]

    chunks_dir = output_dir / "chunks" / filepath.stem
    chunks_dir.mkdir(parents=True, exist_ok=True)

    chunks: list[Path] = []
    start = 0.0
    idx = 0

    while start < duration:
        chunk_path = chunks_dir / f"{filepath.stem}_chunk{idx:03d}.wav"
        cmd = [
            _get_ffmpeg(),
            "-i", str(filepath),
            "-ss", str(start),
            "-t", str(chunk_duration),
            "-ac", str(AUDIO_CHANNELS),
            "-ar", str(AUDIO_SAMPLE_RATE),
            "-sample_fmt", "s16",
            "-y",
            str(chunk_path),
        ]

        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            chunks.append(chunk_path)
        except subprocess.CalledProcessError as e:
            logger.error("Error creating chunk %d of %s: %s", idx, filepath.name, e.stderr)
            raise RuntimeError(f"Failed to create chunk {idx} of {filepath.name}") from e

        start += chunk_duration
        idx += 1

    logger.info("Audio %s split into %d chunks", filepath.name, len(chunks))
    return chunks
