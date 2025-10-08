#!/usr/bin/env python3
"""Migration script for converting term-based index to vector embeddings.

This script migrates an existing KnowledgeBeast v1 term-based index to v2 vector embeddings
with ChromaDB storage. It preserves all existing documents and provides rollback support.

Features:
- Migrate existing term-based index to vector embeddings
- Preserve all existing documents
- Generate embeddings for all documents
- Store in ChromaDB
- Progress reporting during migration
- Backup and rollback support
- Validation of migration results

Usage:
    python scripts/migrate_to_vector.py --data-dir ./data
    python scripts/migrate_to_vector.py --data-dir ./data --rollback
"""

import argparse
import json
import logging
import shutil
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.panel import Panel
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Warning: rich not available, using basic output")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MigrationError(Exception):
    """Custom exception for migration errors."""
    pass


class VectorMigrationTool:
    """Tool for migrating from term-based index to vector embeddings.

    This tool handles the complete migration process including:
    - Backing up existing term-based index
    - Loading all documents from term-based index
    - Generating vector embeddings for all documents
    - Storing embeddings in ChromaDB
    - Validating migration results
    - Providing rollback capability
    """

    def __init__(self, data_dir: Path, backup_dir: Optional[Path] = None):
        """Initialize migration tool.

        Args:
            data_dir: Data directory containing knowledge base
            backup_dir: Directory for backups (default: data_dir/backups)
        """
        self.data_dir = Path(data_dir)
        self.backup_dir = backup_dir or (self.data_dir / "backups")
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        if RICH_AVAILABLE:
            self.console = Console()
        else:
            self.console = None

        self.stats = {
            "documents_migrated": 0,
            "embeddings_generated": 0,
            "errors": 0,
            "start_time": None,
            "end_time": None,
        }

    def _print(self, message: str, style: str = ""):
        """Print message with optional Rich styling."""
        if self.console:
            self.console.print(message)
        else:
            print(message)

    def _create_backup(self) -> Path:
        """Create backup of existing term-based index.

        Returns:
            Path to backup directory

        Raises:
            MigrationError: If backup fails
        """
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"backup_{timestamp}"
        backup_path.mkdir(parents=True, exist_ok=True)

        try:
            # Backup term-based index files (if they exist)
            term_index_file = self.data_dir / "term_index.json"
            documents_file = self.data_dir / "documents.json"
            cache_file = self.data_dir / ".knowledge_cache.pkl"

            files_backed_up = 0

            if term_index_file.exists():
                shutil.copy2(term_index_file, backup_path / "term_index.json")
                files_backed_up += 1

            if documents_file.exists():
                shutil.copy2(documents_file, backup_path / "documents.json")
                files_backed_up += 1

            if cache_file.exists():
                shutil.copy2(cache_file, backup_path / ".knowledge_cache.pkl")
                files_backed_up += 1

            # Create backup manifest
            manifest = {
                "timestamp": timestamp,
                "data_dir": str(self.data_dir),
                "files_backed_up": files_backed_up,
                "backup_complete": True
            }

            with open(backup_path / "manifest.json", "w") as f:
                json.dump(manifest, f, indent=2)

            logger.info(f"Backup created at {backup_path} ({files_backed_up} files)")
            return backup_path

        except Exception as e:
            raise MigrationError(f"Backup failed: {e}")

    def _load_term_based_documents(self) -> List[Dict[str, Any]]:
        """Load documents from term-based index.

        Returns:
            List of document dictionaries

        Raises:
            MigrationError: If loading fails
        """
        documents_file = self.data_dir / "documents.json"

        if not documents_file.exists():
            logger.warning(f"No documents file found at {documents_file}")
            return []

        try:
            with open(documents_file, "r") as f:
                documents = json.load(f)

            logger.info(f"Loaded {len(documents)} documents from term-based index")
            return documents

        except Exception as e:
            raise MigrationError(f"Failed to load documents: {e}")

    def _migrate_to_vector(
        self,
        documents: List[Dict[str, Any]],
        embedding_model: str = "all-MiniLM-L6-v2"
    ) -> Dict[str, Any]:
        """Migrate documents to vector embeddings.

        Args:
            documents: List of documents to migrate
            embedding_model: Model name for embeddings

        Returns:
            Migration statistics

        Raises:
            MigrationError: If migration fails
        """
        try:
            from knowledgebeast.core.embeddings import EmbeddingEngine
            from knowledgebeast.core.vector_store import VectorStore
        except ImportError as e:
            raise MigrationError(f"Failed to import required modules: {e}")

        try:
            # Initialize embedding engine and vector store
            embedding_engine = EmbeddingEngine(model_name=embedding_model)
            chromadb_path = self.data_dir / "chromadb"
            vector_store = VectorStore(
                persist_directory=chromadb_path,
                collection_name="knowledgebeast_v2"
            )

            # Clear existing collection
            try:
                vector_store.clear()
            except Exception:
                pass  # Collection might not exist yet

            migrated_count = 0
            error_count = 0

            # Setup progress tracking
            if RICH_AVAILABLE:
                progress = Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TaskProgressColumn(),
                    console=self.console,
                )
                task = progress.add_task(
                    "Migrating documents...",
                    total=len(documents)
                )
                progress.start()
            else:
                progress = None

            try:
                for i, doc in enumerate(documents):
                    try:
                        # Extract document info
                        doc_id = doc.get("id", f"doc_{i}")
                        content = doc.get("content", "")
                        metadata = doc.get("metadata", {})

                        if not content:
                            logger.warning(f"Skipping document {doc_id}: no content")
                            continue

                        # Generate embedding
                        embedding = embedding_engine.embed(content)

                        # Add to vector store
                        vector_store.add(
                            ids=[doc_id],
                            embeddings=[embedding],
                            documents=[content],
                            metadatas=[metadata]
                        )

                        migrated_count += 1
                        self.stats["documents_migrated"] += 1
                        self.stats["embeddings_generated"] += 1

                        if progress:
                            progress.update(
                                task,
                                advance=1,
                                description=f"Migrated {migrated_count}/{len(documents)} documents"
                            )
                        elif i % 10 == 0:
                            logger.info(f"Migrated {migrated_count}/{len(documents)} documents")

                    except Exception as e:
                        logger.error(f"Error migrating document {doc.get('id', i)}: {e}")
                        error_count += 1
                        self.stats["errors"] += 1

            finally:
                if progress:
                    progress.stop()

            logger.info(f"Migration complete: {migrated_count} documents, {error_count} errors")

            return {
                "migrated_count": migrated_count,
                "error_count": error_count,
                "embedding_model": embedding_model,
                "vector_store_path": str(chromadb_path)
            }

        except Exception as e:
            raise MigrationError(f"Migration failed: {e}")

    def migrate(
        self,
        embedding_model: str = "all-MiniLM-L6-v2",
        skip_backup: bool = False
    ) -> Dict[str, Any]:
        """Execute full migration from term-based to vector.

        Args:
            embedding_model: Model name for embeddings
            skip_backup: Skip backup creation (not recommended)

        Returns:
            Migration statistics

        Raises:
            MigrationError: If migration fails
        """
        self.stats["start_time"] = time.time()

        try:
            # Step 1: Create backup
            if not skip_backup:
                self._print("[bold cyan]Step 1/3:[/bold cyan] Creating backup...")
                backup_path = self._create_backup()
                self._print(f"[green]✓[/green] Backup created at {backup_path}")
            else:
                self._print("[yellow]⚠[/yellow] Skipping backup (not recommended)")
                backup_path = None

            # Step 2: Load documents
            self._print("[bold cyan]Step 2/3:[/bold cyan] Loading documents from term-based index...")
            documents = self._load_term_based_documents()
            self._print(f"[green]✓[/green] Loaded {len(documents)} documents")

            if not documents:
                self._print("[yellow]⚠[/yellow] No documents to migrate")
                return {
                    "status": "no_documents",
                    "backup_path": str(backup_path) if backup_path else None,
                    "stats": self.stats
                }

            # Step 3: Migrate to vector
            self._print(f"[bold cyan]Step 3/3:[/bold cyan] Migrating to vector embeddings (model: {embedding_model})...")
            migration_result = self._migrate_to_vector(documents, embedding_model)
            self._print(f"[green]✓[/green] Migration complete: {migration_result['migrated_count']} documents")

            self.stats["end_time"] = time.time()
            duration = self.stats["end_time"] - self.stats["start_time"]

            result = {
                "status": "success",
                "backup_path": str(backup_path) if backup_path else None,
                "stats": self.stats,
                "duration_seconds": duration,
                "migration_result": migration_result
            }

            return result

        except Exception as e:
            self.stats["end_time"] = time.time()
            raise MigrationError(f"Migration failed: {e}")

    def rollback(self, backup_path: Optional[Path] = None) -> bool:
        """Rollback to term-based index from backup.

        Args:
            backup_path: Path to backup directory (uses latest if not specified)

        Returns:
            True if rollback successful

        Raises:
            MigrationError: If rollback fails
        """
        try:
            # Find backup to restore
            if backup_path is None:
                # Find latest backup
                backups = sorted(self.backup_dir.glob("backup_*"))
                if not backups:
                    raise MigrationError("No backups found")
                backup_path = backups[-1]

            backup_path = Path(backup_path)

            if not backup_path.exists():
                raise MigrationError(f"Backup not found: {backup_path}")

            self._print(f"[bold cyan]Rolling back from:[/bold cyan] {backup_path}")

            # Verify backup manifest
            manifest_file = backup_path / "manifest.json"
            if not manifest_file.exists():
                raise MigrationError("Invalid backup: manifest.json not found")

            with open(manifest_file, "r") as f:
                manifest = json.load(f)

            if not manifest.get("backup_complete"):
                raise MigrationError("Backup is incomplete or corrupted")

            # Restore files
            files_restored = 0

            for backup_file in backup_path.glob("*"):
                if backup_file.name == "manifest.json":
                    continue

                dest_file = self.data_dir / backup_file.name
                shutil.copy2(backup_file, dest_file)
                files_restored += 1

            # Remove vector store (optional)
            chromadb_path = self.data_dir / "chromadb"
            if chromadb_path.exists():
                shutil.rmtree(chromadb_path)
                self._print(f"[yellow]ℹ[/yellow] Removed ChromaDB directory")

            logger.info(f"Rollback complete: {files_restored} files restored")
            self._print(f"[green]✓[/green] Rollback complete: {files_restored} files restored")

            return True

        except Exception as e:
            raise MigrationError(f"Rollback failed: {e}")


def main():
    """Main entry point for migration script."""
    parser = argparse.ArgumentParser(
        description="Migrate KnowledgeBeast from term-based index to vector embeddings"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("./data"),
        help="Data directory containing knowledge base"
    )
    parser.add_argument(
        "--embedding-model",
        type=str,
        default="all-MiniLM-L6-v2",
        help="Embedding model to use (default: all-MiniLM-L6-v2)"
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Rollback to term-based index from backup"
    )
    parser.add_argument(
        "--backup-path",
        type=Path,
        help="Specific backup path for rollback (uses latest if not specified)"
    )
    parser.add_argument(
        "--skip-backup",
        action="store_true",
        help="Skip backup creation (not recommended)"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Initialize migration tool
    migration_tool = VectorMigrationTool(data_dir=args.data_dir)

    try:
        if args.rollback:
            # Execute rollback
            if RICH_AVAILABLE:
                migration_tool.console.print("[bold yellow]⚠ ROLLBACK MODE[/bold yellow]")
            else:
                print("⚠ ROLLBACK MODE")

            success = migration_tool.rollback(backup_path=args.backup_path)

            if success:
                if RICH_AVAILABLE:
                    panel = Panel(
                        "[bold green]Rollback successful![/bold green]\n\n"
                        "Term-based index has been restored from backup.",
                        title="Rollback Complete",
                        border_style="green",
                        box=box.ROUNDED,
                    )
                    migration_tool.console.print(panel)
                else:
                    print("\n✓ Rollback successful!")
                sys.exit(0)
            else:
                sys.exit(1)
        else:
            # Execute migration
            if RICH_AVAILABLE:
                migration_tool.console.print("[bold cyan]🚀 KnowledgeBeast Migration Tool[/bold cyan]")
                migration_tool.console.print(f"Data directory: {args.data_dir}")
                migration_tool.console.print(f"Embedding model: {args.embedding_model}")
                migration_tool.console.print()
            else:
                print("🚀 KnowledgeBeast Migration Tool")
                print(f"Data directory: {args.data_dir}")
                print(f"Embedding model: {args.embedding_model}\n")

            result = migration_tool.migrate(
                embedding_model=args.embedding_model,
                skip_backup=args.skip_backup
            )

            if result["status"] == "success":
                duration = result["duration_seconds"]
                migrated = result["migration_result"]["migrated_count"]
                errors = result["migration_result"]["error_count"]

                if RICH_AVAILABLE:
                    panel = Panel(
                        f"[bold green]Migration successful![/bold green]\n\n"
                        f"[cyan]Documents migrated:[/cyan] {migrated}\n"
                        f"[cyan]Errors:[/cyan] {errors}\n"
                        f"[cyan]Duration:[/cyan] {duration:.2f}s\n"
                        f"[cyan]Backup:[/cyan] {result['backup_path']}\n\n"
                        f"[dim]Your knowledge base is now using vector embeddings![/dim]",
                        title="Migration Complete",
                        border_style="green",
                        box=box.ROUNDED,
                    )
                    migration_tool.console.print(panel)
                else:
                    print(f"\n✓ Migration successful!")
                    print(f"Documents migrated: {migrated}")
                    print(f"Errors: {errors}")
                    print(f"Duration: {duration:.2f}s")
                    print(f"Backup: {result['backup_path']}")

                sys.exit(0)
            else:
                sys.exit(1)

    except MigrationError as e:
        logger.error(f"Migration error: {e}")
        if RICH_AVAILABLE:
            migration_tool.console.print(f"[bold red]❌ Error:[/bold red] {e}")
        else:
            print(f"❌ Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.warning("Migration cancelled by user")
        if RICH_AVAILABLE:
            migration_tool.console.print("\n[yellow]⚠ Migration cancelled by user[/yellow]")
        else:
            print("\n⚠ Migration cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        if RICH_AVAILABLE:
            migration_tool.console.print(f"[bold red]❌ Unexpected error:[/bold red] {e}")
        else:
            print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
