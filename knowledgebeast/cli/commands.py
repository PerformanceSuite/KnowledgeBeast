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


@cli.command(name='mcp-server')
@click.option(
    "--projects-db",
    type=click.Path(),
    default="./kb_projects.db",
    help="Path to projects database"
)
@click.option(
    "--chroma-path",
    type=click.Path(),
    default="./chroma_db",
    help="Path to ChromaDB storage"
)
@click.option(
    "--log-level",
    type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
    default='INFO',
    help="Logging level"
)
@click.pass_context
def mcp_server(
    ctx: click.Context,
    projects_db: str,
    chroma_path: str,
    log_level: str
) -> None:
    """Start the MCP server with stdio transport.

    The MCP server provides a Model Context Protocol interface for
    KnowledgeBeast, allowing MCP clients like Claude Code to interact
    with knowledge base projects through standardized tools.

    The server runs on stdio transport and communicates via JSON-RPC.
    """
    try:
        import asyncio
        from knowledgebeast.mcp.config import MCPConfig
        from knowledgebeast.mcp.server import serve

        # Create configuration
        config = MCPConfig(
            projects_db_path=projects_db,
            chroma_path=chroma_path,
            log_level=log_level,
        )

        # Run MCP server
        console.print(f"[cyan]Starting KnowledgeBeast MCP server...[/cyan]", file=sys.stderr)
        console.print(f"[dim]Projects DB: {projects_db}[/dim]", file=sys.stderr)
        console.print(f"[dim]Chroma Path: {chroma_path}[/dim]", file=sys.stderr)
        console.print(f"[dim]Log Level: {log_level}[/dim]", file=sys.stderr)
        console.print(f"[dim]Communicating via stdio...[/dim]", file=sys.stderr)

        # Run async server
        asyncio.run(serve(config))

    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped by user[/yellow]", file=sys.stderr)
        logger.warning("MCP server stopped by KeyboardInterrupt")
        sys.exit(0)
    except Exception as e:
        console.print(f"[red]MCP server error: {e}[/red]", file=sys.stderr)
        logger.error(f"MCP server command failed: {e}", exc_info=True)
        raise click.Abort()


@cli.command()
@click.option(
    "--from",
    "from_mode",
    type=click.Choice(['term', 'vector']),
    default='term',
    help="Migration source mode (default: term)"
)
@click.option(
    "--to",
    "to_mode",
    type=click.Choice(['term', 'vector']),
    default='vector',
    help="Migration target mode (default: vector)"
)
@click.option(
    "--data-dir",
    type=click.Path(path_type=Path),
    default="./data",
    help="Directory for data storage"
)
@click.option(
    "--embedding-model",
    type=str,
    default="all-MiniLM-L6-v2",
    help="Embedding model for vector mode (default: all-MiniLM-L6-v2)"
)
@click.option(
    "--rollback",
    is_flag=True,
    help="Rollback to previous version from backup"
)
@click.option(
    "--backup-path",
    type=click.Path(path_type=Path),
    help="Specific backup path for rollback"
)
@click.option(
    "--skip-backup",
    is_flag=True,
    help="Skip backup creation (not recommended)"
)
@click.pass_context
def migrate(
    ctx: click.Context,
    from_mode: str,
    to_mode: str,
    data_dir: Path,
    embedding_model: str,
    rollback: bool,
    backup_path: Optional[Path],
    skip_backup: bool
) -> None:
    """Migrate knowledge base between term-based and vector modes."""
    try:
        # Import migration tool
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from scripts.migrate_to_vector import VectorMigrationTool, MigrationError
        except ImportError as e:
            console.print(f"[red]❌ Error: Failed to import migration tool: {e}[/red]")
            raise click.Abort()

        # Validate migration path
        if from_mode == to_mode:
            console.print(f"[yellow]⚠ Warning: Source and target modes are the same ({from_mode})[/yellow]")
            return

        if from_mode != 'term' or to_mode != 'vector':
            console.print(f"[yellow]⚠ Only term → vector migration is currently supported[/yellow]")
            return

        # Initialize migration tool
        migration_tool = VectorMigrationTool(data_dir=data_dir)

        if rollback:
            # Execute rollback
            console.print("[bold yellow]⚠ ROLLBACK MODE[/bold yellow]")
            console.print()

            if not Confirm.ask("[yellow]Are you sure you want to rollback to term-based index?[/yellow]"):
                console.print("[dim]Rollback cancelled.[/dim]")
                return

            with console.status("[bold cyan]Rolling back...", spinner="dots"):
                success = migration_tool.rollback(backup_path=backup_path)

            if success:
                panel = Panel(
                    "[bold green]Rollback successful![/bold green]\n\n"
                    "Term-based index has been restored from backup.",
                    title="Rollback Complete",
                    border_style="green",
                    box=box.ROUNDED,
                )
                console.print(panel)
        else:
            # Execute migration
            console.print("[bold cyan]🚀 KnowledgeBeast Migration Tool[/bold cyan]")
            console.print(f"Migrating from [yellow]{from_mode}[/yellow] to [green]{to_mode}[/green]")
            console.print(f"Data directory: {data_dir}")
            console.print(f"Embedding model: {embedding_model}")
            console.print()

            if not skip_backup:
                console.print("[dim]A backup will be created before migration.[/dim]")

            if not Confirm.ask("[yellow]Proceed with migration?[/yellow]"):
                console.print("[dim]Migration cancelled.[/dim]")
                return

            console.print()

            result = migration_tool.migrate(
                embedding_model=embedding_model,
                skip_backup=skip_backup
            )

            if result["status"] == "success":
                duration = result["duration_seconds"]
                migrated = result["migration_result"]["migrated_count"]
                errors = result["migration_result"]["error_count"]

                panel = Panel(
                    f"[bold green]Migration successful![/bold green]\n\n"
                    f"[cyan]Documents migrated:[/cyan] {migrated}\n"
                    f"[cyan]Errors:[/cyan] {errors}\n"
                    f"[cyan]Duration:[/cyan] {duration:.2f}s\n"
                    f"[cyan]Backup:[/cyan] {result['backup_path']}\n\n"
                    f"[dim]Your knowledge base is now using vector embeddings!\n"
                    f"Run 'knowledgebeast migrate --rollback' to restore term-based index.[/dim]",
                    title="Migration Complete",
                    border_style="green",
                    box=box.ROUNDED,
                )
                console.print(panel)
            elif result["status"] == "no_documents":
                console.print("[yellow]⚠ No documents to migrate[/yellow]")

    except MigrationError as e:
        console.print(f"[bold red]❌ Migration error:[/bold red] {e}")
        logger.error(f"Migration error: {e}", exc_info=True)
        raise click.Abort()
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Migration cancelled by user[/yellow]")
        logger.warning("Migration cancelled by KeyboardInterrupt")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        logger.error(f"Migrate command failed: {e}", exc_info=True)
        raise click.Abort()


@cli.command()
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output file path (.json, .html, or .txt)"
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(['json', 'html', 'text']),
    default='text',
    help="Output format (default: text)"
)
@click.option(
    "--data-dir",
    type=click.Path(path_type=Path),
    default="./data",
    help="Directory for data storage"
)
@click.pass_context
def benchmark(ctx: click.Context, output: Optional[Path], format: str, data_dir: Path) -> None:
    """Run comprehensive performance benchmarks."""
    try:
        from tests.performance.dashboard import PerformanceDashboard
    except ImportError:
        console.print("[red]❌ Error: Performance dashboard module not found[/red]")
        console.print("[dim]Make sure you're running from the project root directory[/dim]")
        raise click.Abort()

    try:
        config = KnowledgeBeastConfig(data_dir=data_dir)

        with console.status("[bold cyan]Running performance benchmarks...", spinner="dots"):
            with KnowledgeBase(config) as kb:
                # Check if KB has data
                stats = kb.get_stats()
                if stats['total_documents'] == 0:
                    console.print("[yellow]⚠ Warning: Knowledge base is empty. Benchmarks may not be representative.[/yellow]")

                dashboard = PerformanceDashboard(kb)
                report = dashboard.run_full_benchmark()

        console.print()
        console.print("[green]✓[/green] Benchmark complete!")
        console.print()

        # Generate output
        if format == 'json' or (output and str(output).endswith('.json')):
            output_text = report.to_json()
        elif format == 'html' or (output and str(output).endswith('.html')):
            output_text = dashboard.generate_html_report(report)
        else:
            output_text = dashboard.generate_ascii_report(report)

        # Save or display
        if output:
            output.write_text(output_text)
            console.print(f"[green]✓[/green] Report saved to: {output}")

            # Open HTML in browser if requested
            if str(output).endswith('.html'):
                console.print("[dim]You can open the HTML report in your browser[/dim]")
        else:
            console.print(output_text)

        # Display summary panel
        panel = Panel(
            f"""[bold]Benchmark Summary[/bold]

[cyan]Query Latency (P99):[/cyan]
  Uncached: {report.query_latency['p99_ms']:.2f}ms
  Cached: {report.cached_query_latency['p99_ms']:.2f}ms

[cyan]Throughput:[/cyan]
  Sequential: {report.throughput_sequential['queries_per_second']:.2f} queries/sec
  Concurrent (10 workers): {report.throughput_concurrent[0]['queries_per_second']:.2f} queries/sec

[cyan]Cache Performance:[/cyan]
  Hit Ratio: {report.cache_performance['hit_ratio']*100:.1f}%
  Hit Latency: {report.cache_performance['avg_hit_latency_us']:.2f}μs

[cyan]Memory:[/cyan]
  RSS: {report.memory_usage['rss_mb']:.2f}MB
""",
            title="Performance Metrics",
            border_style="cyan",
            box=box.ROUNDED,
        )
        console.print(panel)

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Benchmark cancelled by user[/yellow]")
        logger.warning("Benchmark operation cancelled by KeyboardInterrupt")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        logger.error(f"Benchmark command failed: {e}", exc_info=True)
        raise click.Abort()


if __name__ == "__main__":
    cli()
