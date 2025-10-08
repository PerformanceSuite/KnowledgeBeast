"""Background heartbeat manager for KnowledgeBase health and warming."""

import random
import threading
import time
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from knowledgebeast.core.engine import KnowledgeBase

# Configure logging
logger = logging.getLogger(__name__)


class KnowledgeBaseHeartbeat:
    """
    Background heartbeat thread for continuous knowledge base interaction.
    Keeps the KB "warm" and responsive by executing periodic queries and checks.

    Features:
    - Automatic stale cache detection and rebuilding
    - Periodic warming queries to keep index hot
    - Health metrics logging
    - Thread-safe operation

    Usage:
        kb = KnowledgeBase(config)
        heartbeat = KnowledgeBaseHeartbeat(kb, interval=300)
        heartbeat.start()
        # ... do work ...
        heartbeat.stop()

        # Or use context manager:
        with KnowledgeBaseHeartbeat(kb, interval=300) as heartbeat:
            # ... do work ...
            pass
    """

    def __init__(self, kb: "KnowledgeBase", interval: int = 300):
        """
        Initialize heartbeat with knowledge base and interval.

        Args:
            kb: KnowledgeBase instance to monitor
            interval: Heartbeat interval in seconds (default: 300 = 5 minutes)

        Raises:
            ValueError: If interval is less than 10 seconds
        """
        if interval < 10:
            raise ValueError("Heartbeat interval must be at least 10 seconds")

        self.kb = kb
        self.interval = interval
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.heartbeat_count = 0

    def start(self) -> None:
        """Start background heartbeat thread."""
        if self.running:
            logger.warning("Heartbeat already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self._heartbeat_loop, daemon=True, name="KB-Heartbeat")
        self.thread.start()
        logger.info(f"Knowledge base heartbeat started (interval={self.interval}s)")

    def stop(self, timeout: float = 5.0) -> None:
        """
        Stop heartbeat thread gracefully.

        Args:
            timeout: Maximum time to wait for thread to stop (seconds)
        """
        if not self.running:
            return

        self.running = False
        if self.thread:
            self.thread.join(timeout=timeout)
        logger.info(f"Heartbeat stopped (executed {self.heartbeat_count} times)")

    def _heartbeat_loop(self) -> None:
        """Background heartbeat loop with error handling."""
        while self.running:
            try:
                # Sleep in small increments to allow quick shutdown
                # This avoids long wait times when stopping the heartbeat
                elapsed = 0
                sleep_increment = 0.1  # 100ms increments
                while elapsed < self.interval and self.running:
                    time.sleep(sleep_increment)
                    elapsed += sleep_increment

                if not self.running:  # Check again after sleep
                    break

                self.heartbeat_count += 1

                # 1. Check for stale cache
                if self._is_cache_stale():
                    logger.info("Heartbeat: Rebuilding stale cache...")
                    self.kb.ingest_all()

                # 2. Execute warming query to keep index hot
                self._warm_query()

                # 3. Log health metrics
                self._log_health()

            except Exception as e:
                logger.error(f"Heartbeat error: {e}", exc_info=True)
                # Continue running despite errors

    def _is_cache_stale(self) -> bool:
        """
        Check if any knowledge base files have changed since last load.

        Returns:
            True if cache is stale and needs rebuild, False otherwise
        """
        try:
            cache_path = Path(self.kb.config.cache_file)

            if not cache_path.exists():
                return True

            cache_mtime = cache_path.stat().st_mtime

            # Check all knowledge directories
            for kb_dir in self.kb.config.knowledge_dirs:
                if not kb_dir.exists():
                    continue

                md_files = list(kb_dir.rglob("*.md"))
                md_files = [f for f in md_files if not f.is_symlink()]

                for md_file in md_files:
                    if md_file.stat().st_mtime > cache_mtime:
                        return True

            return False

        except Exception as e:
            logger.warning(f"Error checking cache staleness: {e}")
            return False

    def _warm_query(self) -> None:
        """Execute a warming query to keep system responsive."""
        try:
            queries = [
                "audio processing",
                "juce framework",
                "librosa analysis",
                "supercollider patterns",
                "music theory",
                "real-time dsp",
                "knowledge base",
                "configuration settings"
            ]
            query = random.choice(queries)
            self.kb.query(query, use_cache=True)
        except Exception as e:
            logger.warning(f"Warming query error: {e}")

    def _log_health(self) -> None:
        """Log KB health metrics."""
        try:
            stats = self.kb.get_stats()
            logger.info(f"KB Health #{self.heartbeat_count}: "
                       f"{stats['documents']} docs, "
                       f"{stats['total_queries']} queries, "
                       f"{stats['cache_hit_rate']} hit rate, "
                       f"last access {stats['last_access_age']}")
        except Exception as e:
            logger.warning(f"Health logging error: {e}")

    def is_running(self) -> bool:
        """
        Check if heartbeat is currently running.

        Returns:
            True if running, False otherwise
        """
        return self.running

    def __enter__(self) -> "KnowledgeBaseHeartbeat":
        """Context manager entry - starts heartbeat."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - stops heartbeat."""
        self.stop()
