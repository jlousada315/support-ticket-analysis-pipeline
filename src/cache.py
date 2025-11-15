"""Caching abstraction for pipeline outputs."""
from datetime import date
from pathlib import Path
from typing import Generic, TypeVar

T = TypeVar('T')


class FileCache(Generic[T]):
    """Simple file-based cache for serializable objects."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get(self, key: str, loader) -> T | None:
        """Get cached item, returning None if not found."""
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            return loader(cache_file.read_text())
        return None

    def save(self, key: str, value: T, serializer) -> None:
        """Save item to cache."""
        cache_file = self.cache_dir / f"{key}.json"
        cache_file.write_text(serializer(value))

    def exists(self, key: str) -> bool:
        """Check if item exists in cache."""
        return (self.cache_dir / f"{key}.json").exists()


class DateOrganizedCache(FileCache):
    """Cache organized by date: YYYY-MM/DD/key.json"""

    def get_dated(self, key: str, target_date: date, loader) -> T | None:
        """Get cached item organized by date."""
        year_month = target_date.strftime("%Y-%m")
        day = target_date.strftime("%d")
        cache_file = self.cache_dir / year_month / day / f"{key}.json"
        if cache_file.exists():
            return loader(cache_file.read_text())
        return None

    def save_dated(self, key: str, target_date: date, value: T, serializer) -> None:
        """Save item to date-organized cache."""
        year_month = target_date.strftime("%Y-%m")
        day = target_date.strftime("%d")
        cache_dir = self.cache_dir / year_month / day
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"{key}.json"
        cache_file.write_text(serializer(value))

    def exists_dated(self, key: str, target_date: date) -> bool:
        """Check if dated item exists in cache."""
        year_month = target_date.strftime("%Y-%m")
        day = target_date.strftime("%d")
        return (self.cache_dir / year_month / day / f"{key}.json").exists()
