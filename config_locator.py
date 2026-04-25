from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Optional


def resolve_config_path(preferred_path: Optional[str] = None) -> Path:
    """
    Resolve config.yaml in local-dev and installed package contexts.
    """
    candidates = []

    if preferred_path:
        candidates.append(Path(preferred_path).expanduser().resolve())

    script_dir = Path(__file__).parent.resolve()
    candidates.append(Path.cwd() / "config.yaml")
    candidates.append(script_dir / "config.yaml")
    candidates.append(script_dir.parent / "config.yaml")

    for candidate in candidates:
        if candidate.exists():
            return candidate

    # Fallback for wheels that install config as distribution data.
    try:
        dist = importlib_metadata.distribution("rays-core")
        for entry in dist.files or []:
            if entry.name == "config.yaml":
                located = Path(dist.locate_file(entry))
                if located.exists():
                    return located
    except importlib_metadata.PackageNotFoundError:
        pass

    raise FileNotFoundError(
        "config.yaml not found. Pass --config /path/to/config.yaml."
    )
