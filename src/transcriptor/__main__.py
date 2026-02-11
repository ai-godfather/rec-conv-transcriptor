"""Allow running as ``python -m transcriptor``."""

from transcriptor.main import cli as main  # noqa: F401 – re-exported for pyproject.toml entry point

if __name__ == "__main__":
    main()
