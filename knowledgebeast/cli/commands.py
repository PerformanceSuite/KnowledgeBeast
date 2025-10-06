"""Click CLI commands for KnowledgeBeast with Rich formatting."""

import os
import sys
import signal
import logging
import platform
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich import box
from rich.prompt import Confirm

from knowledgebeast import __version__, __description__
from knowledgebeast.core.config import KnowledgeBeastConfig
from knowledgebeast.core.engine import KnowledgeBase
from knowledgebeast.utils.logging import setup_logging

logger = logging.getLogger(__name__)

console = Console()


@click.group()
@click.version_option(version=__version__)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """KnowledgeBeast - Production-ready knowledge management system."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    
    # Setup logging
    log_level = "DEBUG" if verbose else "INFO"
    setup_logging(level=log_level)


@cli.command()
@click.argument('path', default='./knowledge-base', type=click.Path())
@click.option('--name', default=None, help='Knowledge base name')
@click.pass_context
def init(ctx: click.Context, path: str, name: Optional[str]) -> None:
    """Initialize a new KnowledgeBeast instance."""
    data_dir = Path(path)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"Initializing KnowledgeBeast in {data_dir}...", total=3)

        config = KnowledgeBeastConfig(data_dir=data_dir)
        progress.update(task, advance=1, description="Creating directories...")
        config.create_directories()

        progress.update(task, advance=1, description="Initializing knowledge base...")
        with KnowledgeBase(config) as kb:
            stats = kb.get_stats()
            progress.update(task, advance=1, description="Complete!")

    # Display success panel
    panel = Panel(
        f"""[bold green]Knowledge base initialized successfully![/bold green]

[bold]Location:[/bold] {data_dir.absolute()}
[bold]Name:[/bold] {name or 'KnowledgeBeast'}

[bold cyan]Next steps:[/bold cyan]
  1. cd {path}
  2. knowledgebeast ingest <document>
  3. knowledgebeast query "your search"

[dim]Run 'knowledgebeast --help' for more commands.[/dim]""",
        title="Success",
        border_style="green",
        box=box.ROUNDED,
    )
    console.print(panel)


@cli.command()
@click.argument("file_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--data-dir",
    type=click.Path(path_type=Path),
    default="./data",
    help="Directory for data storage"
)
@click.pass_context
def ingest(ctx: click.Context, file_path: Path, data_dir: Path) -> None:
    """Ingest a document into the knowledge base."""
    try:
        config = KnowledgeBeastConfig(data_dir=data_dir)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(f"Ingesting {file_path.name}...", total=100)

            with KnowledgeBase(config) as kb:
                chunks = kb.ingest_document(file_path)
                progress.update(task, completed=100)
                console.print(f"[green]✓[/green] Successfully ingested {chunks} chunks from {file_path.name}")

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Operation cancelled by user[/yellow]")
        logger.warning("Ingest operation cancelled by KeyboardInterrupt")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        logger.error(f"Ingest command failed: {e}", exc_info=True)
        raise click.Abort()


@cli.command()
@click.argument("file_or_dir", type=click.Path(exists=True, path_type=Path))
@click.option('--recursive', '-r', is_flag=True, help='Add directories recursively')
@click.option(
    "--data-dir",
    type=click.Path(path_type=Path),
    default="./data",
    help="Directory for data storage"
)
@click.pass_context
def add(ctx: click.Context, file_or_dir: Path, recursive: bool, data_dir: Path) -> None:
    """Add documents to the knowledge base (alias for ingest with directory support)."""
    try:
        config = KnowledgeBeastConfig(data_dir=data_dir)

        # Collect files
        files_to_add = []
        if file_or_dir.is_file():
            files_to_add.append(file_or_dir)
        elif file_or_dir.is_dir():
            pattern = '**/*.md' if recursive else '*.md'
            files_to_add.extend(file_or_dir.glob(pattern))

        if not files_to_add:
            console.print(f"[yellow]No markdown files found in {file_or_dir}[/yellow]")
            return

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Adding documents...", total=len(files_to_add))

            added_count = 0
            failed_count = 0

            with KnowledgeBase(config) as kb:
                for file_path in files_to_add:
                    try:
                        progress.update(task, description=f"Processing {file_path.name}...")
                        kb.ingest_document(file_path)
                        added_count += 1
                        progress.update(task, advance=1)
                    except Exception as e:
                        console.print(f"[red]Failed to add {file_path.name}: {e}[/red]")
                        failed_count += 1
                        progress.update(task, advance=1)

        console.print()
        if added_count > 0:
            console.print(f"[green]✓[/green] Added {added_count} document(s)")
        if failed_count > 0:
            console.print(f"[yellow]⚠[/yellow] {failed_count} document(s) failed")

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Operation cancelled by user[/yellow]")
        logger.warning("Add operation cancelled by KeyboardInterrupt")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        logger.error(f"Add command failed: {e}", exc_info=True)
        raise click.Abort()


@cli.command()
@click.argument("query_text")
@click.option(
    "--n-results",
    "-n",
    type=int,
    default=5,
    help="Number of results to return"
)
@click.option(
    "--data-dir",
    type=click.Path(path_type=Path),
    default="./data",
    help="Directory for data storage"
)
@click.option(
    "--no-cache",
    is_flag=True,
    help="Disable cache for this query"
)
@click.pass_context
def query(
    ctx: click.Context,
    query_text: str,
    n_results: int,
    data_dir: Path,
    no_cache: bool
) -> None:
    """Query the knowledge base with Rich formatting."""
    config = KnowledgeBeastConfig(data_dir=data_dir)

    with console.status("[bold cyan]Searching...", spinner="dots"):
        with KnowledgeBase(config) as kb:
            try:
                results = kb.query(query_text, n_results=n_results, use_cache=not no_cache)
            except Exception as e:
                console.print(f"[bold red]Error:[/bold red] {e}")
                raise click.Abort()

    if not results:
        console.print(f"[yellow]No results found for:[/yellow] [bold]{query_text}[/bold]")
        return

    console.print(f"\n[bold]Found {len(results)} result(s)[/bold]\n")

    for i, result in enumerate(results, 1):
        distance = result['distance']
        score_color = "green" if distance < 0.3 else "yellow" if distance < 0.6 else "red"

        content = f"""[bold]Source:[/bold] {result['metadata'].get('source', 'unknown')}
[bold]Distance:[/bold] [{score_color}]{distance:.4f}[/{score_color}]

{result['text'][:300]}..."""

        panel = Panel(
            content,
            title=f"[bold cyan]Result {i}[/bold cyan]",
            border_style="blue",
            box=box.ROUNDED,
        )
        console.print(panel)
        console.print()


@cli.command()
@click.option(
    "--data-dir",
    type=click.Path(path_type=Path),
    default="./data",
    help="Directory for data storage"
)
@click.option('--detailed', '-d', is_flag=True, help='Show detailed statistics')
@click.pass_context
def stats(ctx: click.Context, data_dir: Path, detailed: bool) -> None:
    """Show knowledge base statistics with Rich tables."""
    config = KnowledgeBeastConfig(data_dir=data_dir)

    with KnowledgeBase(config) as kb:
        stats = kb.get_stats()

        # Main statistics table
        table = Table(title="Knowledge Base Statistics", box=box.ROUNDED, show_header=False)
        table.add_column("Metric", style="cyan", width=30)
        table.add_column("Value", style="green")

        table.add_row("Total documents", str(stats['total_documents']))
        table.add_row("Collection", stats['collection_name'])
        table.add_row("Embedding model", stats['embedding_model'])
        table.add_row("Heartbeat running", "Yes" if stats['heartbeat_running'] else "No")

        console.print(table)
        console.print()

        # Cache statistics table
        cache_table = Table(title="Cache Statistics", box=box.ROUNDED)
        cache_table.add_column("Metric", style="cyan")
        cache_table.add_column("Value", style="yellow")

        for key, value in stats['cache_stats'].items():
            cache_table.add_row(key.replace('_', ' ').title(), str(value))

        console.print(cache_table)


@cli.command()
@click.option(
    "--data-dir",
    type=click.Path(path_type=Path),
    default="./data",
    help="Directory for data storage"
)
@click.confirmation_option(prompt="Are you sure you want to clear all documents?")
@click.pass_context
def clear(ctx: click.Context, data_dir: Path) -> None:
    """Clear all documents from the knowledge base."""
    config = KnowledgeBeastConfig(data_dir=data_dir)

    with console.status("[bold yellow]Clearing knowledge base...", spinner="dots"):
        with KnowledgeBase(config) as kb:
            kb.clear()

    console.print("[green]✓[/green] Knowledge base cleared successfully")


@cli.command(name='clear-cache')
@click.option(
    "--data-dir",
    type=click.Path(path_type=Path),
    default="./data",
    help="Directory for data storage"
)
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation prompt')
@click.pass_context
def clear_cache(ctx: click.Context, data_dir: Path, yes: bool) -> None:
    """Clear the query cache."""
    if not yes and not Confirm.ask("[yellow]Clear all cached queries?[/yellow]"):
        console.print("[dim]Cache clearing cancelled.[/dim]")
        return

    config = KnowledgeBeastConfig(data_dir=data_dir)

    with console.status("[bold cyan]Clearing cache...", spinner="dots"):
        with KnowledgeBase(config) as kb:
            cleared = kb.clear_cache()

    console.print(f"[green]✓[/green] Cleared {cleared} cached entries")


@cli.command()
@click.option(
    "--data-dir",
    type=click.Path(path_type=Path),
    default="./data",
    help="Directory for data storage"
)
@click.pass_context
def warm(ctx: click.Context, data_dir: Path) -> None:
    """Manually trigger cache warming."""
    try:
        config = KnowledgeBeastConfig(data_dir=data_dir)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Warming cache...", total=100)

            with KnowledgeBase(config) as kb:
                # Trigger warming
                kb.warm_cache()
                progress.update(task, completed=100)

        console.print("[green]✓[/green] Cache warming completed")

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Operation cancelled by user[/yellow]")
        logger.warning("Warm operation cancelled by KeyboardInterrupt")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        logger.error(f"Warm command failed: {e}", exc_info=True)
        raise click.Abort()


@cli.command()
@click.option(
    "--data-dir",
    type=click.Path(path_type=Path),
    default="./data",
    help="Directory for data storage"
)
@click.pass_context
def health(ctx: click.Context, data_dir: Path) -> None:
    """Run health check on the knowledge base."""
    checks = []

    with console.status("[bold cyan]Running health checks..."):
        # Check configuration
        try:
            config = KnowledgeBeastConfig(data_dir=data_dir)
            checks.append(("Configuration", True, "Config loaded"))
        except Exception as e:
            checks.append(("Configuration", False, str(e)))

        # Check knowledge base
        try:
            with KnowledgeBase(config) as kb:
                stats = kb.get_stats()
                checks.append(("Knowledge Base", True, f"{stats['total_documents']} documents"))
        except Exception as e:
            checks.append(("Knowledge Base", False, str(e)))

        # Check data directory
        if data_dir.exists():
            checks.append(("Data Directory", True, str(data_dir)))
        else:
            checks.append(("Data Directory", False, "Directory not found"))

    # Display results
    console.print()
    table = Table(title="Health Check Results", box=box.ROUNDED)
    table.add_column("Check", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Details", style="dim")

    all_passed = True
    for check_name, passed, details in checks:
        status = "[green]✓ PASS[/green]" if passed else "[red]✗ FAIL[/red]"
        table.add_row(check_name, status, details)
        if not passed:
            all_passed = False

    console.print(table)
    console.print()

    if all_passed:
        console.print("[green]✓[/green] All health checks passed")
        sys.exit(0)
    else:
        console.print("[red]✗[/red] Some health checks failed")
        sys.exit(1)


@cli.command()
@click.argument('action', type=click.Choice(['start', 'stop', 'status']))
@click.option(
    "--data-dir",
    type=click.Path(path_type=Path),
    default="./data",
    help="Directory for data storage"
)
@click.option('--interval', '-i', default=300, help='Heartbeat interval in seconds')
@click.pass_context
def heartbeat(ctx: click.Context, action: str, data_dir: Path, interval: int) -> None:
    """Manage background heartbeat process."""
    config = KnowledgeBeastConfig(data_dir=data_dir)

    with KnowledgeBase(config) as kb:
        if action == 'start':
            kb.start_heartbeat(interval)
            console.print(f"[green]✓[/green] Heartbeat started with {interval}s interval")
            console.print("[dim]Heartbeat running in background...[/dim]")

        elif action == 'stop':
            kb.stop_heartbeat()
            console.print("[green]✓[/green] Heartbeat stopped")

        elif action == 'status':
            status = kb.get_heartbeat_status()

            if status.get('running', False):
                console.print(f"[green]●[/green] Heartbeat is [bold]running[/bold]")
                console.print(f"   Interval: {status.get('interval', 0)}s")
                console.print(f"   Count: {status.get('count', 0)}")
            else:
                console.print(f"[red]●[/red] Heartbeat is [bold]stopped[/bold]")


@cli.command()
@click.pass_context
def version(ctx: click.Context) -> None:
    """Display version and system information."""
    info = f"""[bold cyan]KnowledgeBeast[/bold cyan] [green]v{__version__}[/green]

{__description__}

[bold]System Information:[/bold]
  Python: {sys.version.split()[0]}
  Platform: {platform.system()} {platform.release()}
  Architecture: {platform.machine()}

[dim]Built with Click and Rich[/dim]"""

    panel = Panel(
        info,
        title="Version Info",
        border_style="cyan",
        box=box.ROUNDED,
    )
    console.print(panel)


@cli.command()
@click.option(
    "--host",
    default="0.0.0.0",
    help="Host to bind to"
)
@click.option(
    "--port",
    default=8000,
    type=int,
    help="Port to bind to"
)
@click.option(
    "--reload",
    is_flag=True,
    help="Enable auto-reload"
)
@click.pass_context
def serve(ctx: click.Context, host: str, port: int, reload: bool) -> None:
    """Start the FastAPI server."""
    def signal_handler(sig, frame):
        """Handle shutdown signals gracefully."""
        console.print("\n[yellow]⚠️  Shutting down server...[/yellow]")
        logger.info("Server shutdown initiated by signal")
        sys.exit(0)

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        import uvicorn
    except ImportError:
        console.print("[red]❌ Error: uvicorn is required to run the server[/red]")
        console.print("[dim]Install it with: pip install uvicorn[/dim]")
        logger.error("uvicorn not installed")
        raise click.Abort()

    try:
        console.print(f"[cyan]Starting KnowledgeBeast API server on {host}:{port}[/cyan]")
        logger.info(f"Starting server on {host}:{port}")

        uvicorn.run(
            "knowledgebeast.api.app:app",
            host=host,
            port=port,
            reload=reload
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Server stopped by user[/yellow]")
        logger.warning("Server stopped by KeyboardInterrupt")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        logger.error(f"Serve command failed: {e}", exc_info=True)
        raise click.Abort()


if __name__ == "__main__":
    cli()
