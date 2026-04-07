"""Professional CLI interface with Typer and Rich."""

import logging
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

from . import __version__
from .config import AVAILABLE_MODELS, DEFAULT_MODEL, OUTPUT_FORMATS, TranscriptionConfig
from .formatter import export_transcript
from .merger import merge_and_sort, merge_consecutive
from .transcribe import transcribe_session

console = Console()
app = typer.Typer(
    name="whisperer",
    help="RPG session transcriber for Craig Bot recordings.",
    add_completion=False,
    rich_markup_mode="rich",
)


def _setup_logging(verbose: bool) -> None:
    """Configure logging with Rich."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


def _show_banner() -> None:
    """Show the application banner."""
    console.print(Panel.fit(
        "[bold magenta]\U0001f399\ufe0f Whisperer[/bold magenta]\n"
        f"[dim]v{__version__} \u2014 RPG session transcriber[/dim]",
        border_style="magenta",
    ))


def _show_config_table(config: TranscriptionConfig) -> None:
    """Show the current configuration in a table."""
    table = Table(title="Configuration", show_header=False, border_style="blue")
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Input directory", str(config.input_dir))
    table.add_row("Output directory", str(config.output_dir))
    table.add_row("Model", config.model_size)
    table.add_row("Compute type", config.compute_type)
    table.add_row("Language", config.language or "auto-detect")
    table.add_row("Output format", config.output_format)
    table.add_row("CPU Threads", str(config.threads))
    table.add_row("VAD Filter", "Yes" if config.vad_filter else "No")
    console.print(table)


@app.command()
def transcribe(
    input_dir: Path = typer.Argument(
        ...,
        help="Directory with Craig Bot audio files.",
        exists=True,
        file_okay=False,
        resolve_path=True,
    ),
    output_dir: Path = typer.Option(
        "output",
        "--output", "-o",
        help="Output directory for the transcription.",
        resolve_path=True,
    ),
    model: str = typer.Option(
        DEFAULT_MODEL,
        "--model", "-m",
        help=f"Whisper model. Options: {', '.join(AVAILABLE_MODELS)}",
    ),
    language: str = typer.Option(
        None,
        "--language", "-l",
        help="Language code (e.g. es, en). Default: auto-detect.",
    ),
    output_format: str = typer.Option(
        "txt",
        "--format", "-f",
        help=f"Output format. Options: {', '.join(OUTPUT_FORMATS)}",
    ),
    threads: int = typer.Option(
        6,
        "--threads", "-t",
        help="Number of CPU threads.",
        min=1,
        max=32,
    ),
    filename: str = typer.Option(
        "transcript",
        "--filename",
        help="Base name for the output file.",
    ),
    no_merge: bool = typer.Option(
        False,
        "--no-merge",
        help="Do not merge consecutive segments from the same speaker.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Enable detailed logs.",
    ),
) -> None:
    """Transcribe a full RPG session from Craig Bot audio files."""
    _setup_logging(verbose)
    _show_banner()

    config = TranscriptionConfig(
        input_dir=input_dir,
        output_dir=output_dir,
        model_size=model,
        language=language,
        output_format=output_format,
        threads=threads,
    )

    try:
        config.validate()
    except (ValueError, FileNotFoundError) as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)

    _show_config_table(config)
    console.print()

    try:
        # 1. Transcribe all files
        segments = transcribe_session(config)

        if not segments:
            console.print("[yellow]No audio segments with content were found.[/yellow]")
            raise typer.Exit(code=0)

        # 2. Sort chronologically
        segments = merge_and_sort(segments)

        # 3. Merge consecutive segments from the same speaker
        if not no_merge:
            segments = merge_consecutive(segments)

        # 4. Export
        output_path = export_transcript(segments, output_dir, output_format, filename)

        console.print()
        console.print(Panel.fit(
            f"[bold green]Transcription completed[/bold green]\n\n"
            f"File: [cyan]{output_path}[/cyan]\n"
            f"Segments: [cyan]{len(segments)}[/cyan]\n"
            f"Speakers: [cyan]{', '.join(sorted({s.speaker for s in segments}))}[/cyan]",
            border_style="green",
            title="Result",
        ))

    except KeyboardInterrupt:
        console.print("\n[yellow]Transcription cancelled by user.[/yellow]")
        raise typer.Exit(code=130)
    except Exception as e:
        logging.exception("Error during transcription")
        console.print(f"\n[bold red]Fatal error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def version() -> None:
    """Show the Whisperer version."""
    console.print(f"Whisperer v{__version__}")


def main() -> None:
    """Main entry point."""
    app()
