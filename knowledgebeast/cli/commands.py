"""Click CLI commands for KnowledgeBeast with Rich formatting."""

import os
import sys
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
from knowledgebeast.core.engine import KnowledgeBeast
from knowledgebeast.utils.logging import setup_logging

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
@click.option(
    "--data-dir",
    type=click.Path(path_type=Path),
    default="./data",
    help="Directory for data storage"
)
@click.pass_context
def init(ctx: click.Context, data_dir: Path) -> None:
    """Initialize a new KnowledgeBeast instance."""
    click.echo(f"Initializing KnowledgeBeast in {data_dir}")
    
    config = KnowledgeBeastConfig(data_dir=data_dir)
    config.create_directories()
    
    # Create a basic instance to verify setup
    with KnowledgeBeast(config) as kb:
        stats = kb.get_stats()
        click.echo(f"Initialized successfully!")
        click.echo(f"Collection: {stats['collection_name']}")
        click.echo(f"Embedding model: {stats['embedding_model']}")


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
    click.echo(f"Ingesting document: {file_path}")
    
    config = KnowledgeBeastConfig(data_dir=data_dir)
    
    with KnowledgeBeast(config) as kb:
        try:
            chunks = kb.ingest_document(file_path)
            click.echo(f"Successfully ingested {chunks} chunks")
        except Exception as e:
            click.echo(f"Error: {e}", err=True)
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
    """Query the knowledge base."""
    config = KnowledgeBeastConfig(data_dir=data_dir)
    
    with KnowledgeBeast(config) as kb:
        try:
            results = kb.query(query_text, n_results=n_results, use_cache=not no_cache)
            
            click.echo(f"\nQuery: {query_text}")
            click.echo(f"Found {len(results)} results:\n")
            
            for i, result in enumerate(results, 1):
                click.echo(f"Result {i} (distance: {result['distance']:.4f}):")
                click.echo(f"Source: {result['metadata'].get('source', 'unknown')}")
                click.echo(f"Text: {result['text'][:200]}...")
                click.echo()
        except Exception as e:
            click.echo(f"Error: {e}", err=True)
            raise click.Abort()


@cli.command()
@click.option(
    "--data-dir",
    type=click.Path(path_type=Path),
    default="./data",
    help="Directory for data storage"
)
@click.pass_context
def stats(ctx: click.Context, data_dir: Path) -> None:
    """Show knowledge base statistics."""
    config = KnowledgeBeastConfig(data_dir=data_dir)
    
    with KnowledgeBeast(config) as kb:
        stats = kb.get_stats()
        
        click.echo("Knowledge Base Statistics:")
        click.echo(f"  Total documents: {stats['total_documents']}")
        click.echo(f"  Collection: {stats['collection_name']}")
        click.echo(f"  Embedding model: {stats['embedding_model']}")
        click.echo(f"  Heartbeat running: {stats['heartbeat_running']}")
        click.echo(f"\nCache Statistics:")
        for key, value in stats['cache_stats'].items():
            click.echo(f"  {key}: {value}")


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
    
    with KnowledgeBeast(config) as kb:
        kb.clear()
        click.echo("Knowledge base cleared successfully")


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
    try:
        import uvicorn
    except ImportError:
        click.echo("Error: uvicorn is required to run the server", err=True)
        click.echo("Install it with: pip install uvicorn", err=True)
        raise click.Abort()
    
    click.echo(f"Starting KnowledgeBeast API server on {host}:{port}")
    
    uvicorn.run(
        "knowledgebeast.api.app:app",
        host=host,
        port=port,
        reload=reload
    )


if __name__ == "__main__":
    cli()
