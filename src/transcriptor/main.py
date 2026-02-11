"""CLI entry point for the transcriptor tool."""

from pathlib import Path

import click

from transcriptor.config import settings


@click.group()
def cli():
    """Transcriptor - Call center audio transcription and analysis tool."""
    pass


@cli.command()
def watch():
    """Start watching the NAGRANIA folder for new WAV files."""
    from transcriptor.watcher.folder_watcher import start_watcher

    watch_dir = Path(settings.WATCH_DIR)
    click.echo(f"Starting watcher on: {watch_dir}")
    start_watcher(watch_dir)


@cli.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
def process(file: Path):
    """Process a single WAV file."""
    if file.suffix.lower() != ".wav":
        click.echo("Error: Only .wav files are supported.", err=True)
        raise SystemExit(1)

    from transcriptor.watcher.folder_watcher import process_single_file

    click.echo(f"Processing: {file}")
    process_single_file(file)
    click.echo("Done.")


@cli.command("process-all")
def process_all():
    """Process all unprocessed WAV files in the NAGRANIA folder."""
    from transcriptor.watcher.folder_watcher import process_all_unprocessed

    watch_dir = Path(settings.WATCH_DIR)
    click.echo(f"Processing all unprocessed WAV files in: {watch_dir}")
    process_all_unprocessed(watch_dir)
    click.echo("Done.")


@cli.command()
@click.argument("recording_id", type=int)
def query(recording_id: int):
    """Show transcript for a given recording ID."""
    from transcriptor.api.query import get_transcript

    result = get_transcript(recording_id)
    if result is None:
        click.echo(f"Recording #{recording_id} not found.", err=True)
        raise SystemExit(1)

    rec = result["recording"]
    click.echo(f"Recording: {rec['filename']} (status: {rec['status']})")

    if result["transcript"] is None:
        click.echo("No transcript available yet.")
        return

    click.echo(f"Language: {result['transcript'].get('language', 'unknown')}")
    click.echo(f"\n{'='*60}")
    click.echo("FULL TRANSCRIPT:")
    click.echo(f"{'='*60}")
    click.echo(result["transcript"]["full_text"])

    if result["segments"]:
        click.echo(f"\n{'='*60}")
        click.echo("SEGMENTS:")
        click.echo(f"{'='*60}")
        for seg in result["segments"]:
            role = seg["role"] or seg["speaker"] or "?"
            start = seg["start_time"] or 0
            end = seg["end_time"] or 0
            click.echo(f"[{start:.1f}s - {end:.1f}s] {role}: {seg['text']}")


@cli.command()
@click.argument("text")
def search(text: str):
    """Search across all transcripts."""
    from transcriptor.api.query import search_transcripts

    results = search_transcripts(text)
    if not results:
        click.echo("No results found.")
        return

    click.echo(f"Found {len(results)} result(s):\n")
    for r in results:
        click.echo(f"  Recording #{r['recording_id']} ({r['filename']}) [{r['match_type']}]")
        if r["match_type"] == "segment":
            role = r.get("role", r.get("speaker", "?"))
            click.echo(f"    [{role}]: {r['text']}")
        else:
            text_preview = r["text"][:200] + "..." if len(r["text"]) > 200 else r["text"]
            click.echo(f"    {text_preview}")
        click.echo()


@cli.command()
def stats():
    """Show overall transcription statistics."""
    from transcriptor.api.query import get_stats

    s = get_stats()
    click.echo("Transcriptor Statistics")
    click.echo(f"{'='*30}")
    click.echo(f"Total recordings:  {s['total_recordings']}")
    click.echo(f"  Completed:       {s['done']}")
    click.echo(f"  Pending:         {s['pending']}")
    click.echo(f"  Errors:          {s['errors']}")
    avg = s["avg_duration_seconds"]
    click.echo(f"Avg duration:      {avg:.1f}s" if avg else "Avg duration:      N/A")


@cli.command("swap-speakers")
@click.argument("recording_id", type=int)
def swap_speakers(recording_id: int):
    """Swap agent/customer labels for a recording (manual override)."""
    from transcriptor.api.query import swap_speakers as do_swap

    if do_swap(recording_id):
        click.echo(f"Swapped agent/customer labels for recording #{recording_id}.")
    else:
        click.echo(f"Recording #{recording_id} not found or has no transcript.", err=True)
        raise SystemExit(1)


@cli.command("list")
def list_recordings():
    """List all recordings."""
    from transcriptor.api.query import get_all_recordings

    recordings = get_all_recordings()
    if not recordings:
        click.echo("No recordings found.")
        return

    click.echo(f"{'ID':<6} {'Status':<10} {'Filename':<40} {'Duration':<10}")
    click.echo("-" * 66)
    for r in recordings:
        dur = f"{r['duration']:.1f}s" if r["duration"] else "-"
        click.echo(f"{r['id']:<6} {r['status']:<10} {r['filename']:<40} {dur:<10}")


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=8000, type=int, help="Port to listen on")
@click.option("--reload", "do_reload", is_flag=True, help="Enable auto-reload for development")
def serve(host: str, port: int, do_reload: bool):
    """Start the dashboard web server (FastAPI + frontend)."""
    import uvicorn

    click.echo(f"Starting Transcriptor dashboard on http://{host}:{port}")
    uvicorn.run(
        "transcriptor.api.server:app",
        host=host,
        port=port,
        reload=do_reload,
    )


if __name__ == "__main__":
    cli()
