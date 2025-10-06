"""Custom configuration example.

This example demonstrates:
- Creating custom configurations
- Environment-based config
- Advanced settings
"""

import os
from pathlib import Path
from knowledgebeast import KnowledgeBeast, KnowledgeBeastConfig


def basic_config_example():
    """Basic custom configuration."""
    print("Basic Configuration Example")
    print("=" * 50)

    config = KnowledgeBeastConfig(
        data_dir=Path("./my-data"),
        collection_name="my_collection",
        cache_size=200,
        heartbeat_interval=120.0,
        log_level="DEBUG"
    )

    config.print_config()

    with KnowledgeBeast(config) as kb:
        stats = kb.get_stats()
        print(f"Collection: {stats['collection_name']}")
        print(f"Cache size: {stats['cache_stats']['max_size']}")


def advanced_config_example():
    """Advanced configuration with custom model."""
    print("\nAdvanced Configuration Example")
    print("=" * 50)

    config = KnowledgeBeastConfig(
        data_dir=Path("./advanced-data"),
        collection_name="advanced_kb",
        embedding_model="all-mpnet-base-v2",  # Better quality
        chunk_size=1500,  # Larger chunks
        chunk_overlap=300,  # More overlap
        cache_size=500,  # Larger cache
        heartbeat_interval=300.0,  # 5 minutes
        log_level="INFO"
    )

    print(f"Using model: {config.embedding_model}")
    print(f"Chunk size: {config.chunk_size}")
    print(f"Cache size: {config.cache_size}")


def environment_based_config():
    """Configuration based on environment."""
    print("\nEnvironment-Based Configuration")
    print("=" * 50)

    env = os.getenv("ENV", "development")
    print(f"Environment: {env}")

    if env == "production":
        config = KnowledgeBeastConfig(
            data_dir=Path("/var/lib/knowledgebeast"),
            cache_size=1000,
            heartbeat_interval=300.0,
            log_level="WARNING"
        )
        print("Using production configuration")
    elif env == "staging":
        config = KnowledgeBeastConfig(
            data_dir=Path("./staging-data"),
            cache_size=500,
            heartbeat_interval=180.0,
            log_level="INFO"
        )
        print("Using staging configuration")
    else:
        config = KnowledgeBeastConfig(
            data_dir=Path("./dev-data"),
            cache_size=50,
            heartbeat_interval=60.0,
            log_level="DEBUG"
        )
        print("Using development configuration")

    config.print_config()


def performance_optimized_config():
    """Performance-optimized configuration."""
    print("\nPerformance-Optimized Configuration")
    print("=" * 50)

    config = KnowledgeBeastConfig(
        # Fast, small model
        embedding_model="all-MiniLM-L6-v2",

        # Smaller chunks for precision
        chunk_size=800,
        chunk_overlap=150,

        # Large cache for frequent queries
        cache_size=1000,

        # Aggressive heartbeat
        heartbeat_interval=60.0,

        # Minimal logging
        log_level="WARNING"
    )

    print("Configuration optimized for:")
    print("  - Fast queries (small model)")
    print("  - Precise results (small chunks)")
    print("  - High cache hit rate (large cache)")


def main():
    """Run all configuration examples."""
    print("KnowledgeBeast - Configuration Examples\n")

    basic_config_example()
    advanced_config_example()
    environment_based_config()
    performance_optimized_config()

    print("\n✓ All examples complete!")


if __name__ == "__main__":
    main()
