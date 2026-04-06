from __future__ import annotations

import argparse
import importlib.metadata as md
import os
import shutil
import sys
from pathlib import Path
from typing import Iterable

import site as _site


DEFAULT_REMOVE = [
    # Unused for this repo (no references in code) and very heavy.
    "paddleocr",
    "paddlepaddle",
    "paddlex",
    "opencv-contrib-python",
    "modelscope",
    "huggingface_hub",
    "hf-xet",
    "safetensors",
    "numpy",
    "pandas",
    # Not used by the current implementation (SQLite + no Supabase integration).
    "supabase",
    "supabase-auth",
    "supabase-functions",
    "postgrest",
    "realtime",
    "storage3",
    # Not used (no migrations / no postgres driver needed).
    "alembic",
    "psycopg2-binary",
    # Mostly transitive from the removed stacks above.
    "aistudio-sdk",
    "bce-python-sdk",
    "pyiceberg",
    "shapely",
    "fsspec",
    "networkx",
    "protobuf",
    "crc32c",
    "mmh3",
    "prettytable",
    "pyroaring",
    "ruamel.yaml",
    "strictyaml",
    "uuid_utils",
    "xxhash",
    "zstandard",
]


def _safe_within_prefix(path: Path, prefix: Path) -> bool:
    try:
        path_resolved = path.resolve()
        prefix_resolved = prefix.resolve()
        return prefix_resolved == path_resolved or prefix_resolved in path_resolved.parents
    except Exception:
        return False


def _remove_path(path: Path, *, dry_run: bool) -> None:
    if not path.exists():
        return
    if dry_run:
        print(f"DRY_RUN delete {path}")
        return
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=False)
    else:
        path.unlink(missing_ok=True)


def _read_metadata_name(dist_info_dir: Path) -> str | None:
    meta = dist_info_dir / "METADATA"
    if not meta.exists():
        return None
    try:
        for line in meta.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.lower().startswith("name:"):
                return line.split(":", 1)[1].strip()
    except Exception:
        return None
    return None


def _iter_dist_info_dirs(site_packages: Path) -> Iterable[Path]:
    for entry in site_packages.iterdir():
        if entry.is_dir() and entry.name.lower().endswith(".dist-info"):
            yield entry


def _remove_scripts_for_dist(dist_info_dir: Path, scripts_dir: Path, *, dry_run: bool) -> list[str]:
    entry_points = dist_info_dir / "entry_points.txt"
    if not entry_points.exists():
        return []
    removed: list[str] = []
    try:
        text = entry_points.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    in_console = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            in_console = line.lower() == "[console_scripts]"
            continue
        if not in_console:
            continue
        name = line.split("=", 1)[0].strip()
        if not name:
            continue
        for suffix in (".exe", "-script.py", ".py"):
            candidate = scripts_dir / f"{name}{suffix}"
            if candidate.exists():
                _remove_path(candidate, dry_run=dry_run)
                removed.append(str(candidate))
    return removed


def remove_by_dist_info_name(package_name: str, *, dry_run: bool) -> dict:
    sys_prefix = Path(sys.prefix)
    site_packages = Path(_site.getsitepackages()[-1])
    scripts_dir = sys_prefix / "Scripts"

    removed: list[str] = []
    skipped: list[str] = []

    matches: list[Path] = []
    for dist_info in _iter_dist_info_dirs(site_packages):
        name = _read_metadata_name(dist_info)
        if not name:
            continue
        if name.strip().lower() == package_name.strip().lower():
            matches.append(dist_info)

    if not matches:
        return {"name": package_name, "version": None, "removed": [], "skipped": [], "file_count": 0, "missing": True}

    for dist_info in matches:
        version = dist_info.name.rsplit("-", 1)[-1].replace(".dist-info", "")

        # Remove top-level modules.
        top_level = dist_info / "top_level.txt"
        module_names: list[str] = []
        if top_level.exists():
            try:
                module_names = [
                    line.strip()
                    for line in top_level.read_text(encoding="utf-8", errors="ignore").splitlines()
                    if line.strip()
                ]
            except Exception:
                module_names = []

        for module_name in module_names:
            candidates = [
                site_packages / module_name,
                site_packages / f"{module_name}.py",
                site_packages / f"~{module_name}",
            ]
            if len(module_name) > 1:
                # pip's "stash" rename often becomes "~" + name[1:], e.g. "alembic" -> "~lembic"
                candidates.append(site_packages / f"~{module_name[1:]}")
            for candidate in candidates:
                if candidate.exists():
                    try:
                        _remove_path(candidate, dry_run=dry_run)
                        removed.append(str(candidate))
                    except Exception as e:
                        skipped.append(f"{candidate} ({type(e).__name__}: {e})")

        # Some failed uninstalls rename the package dir to ~<name> (ex: ~lembic). Remove common leftovers.
        tilde_dirs = [
            site_packages / f"~{package_name}",
            site_packages / f"~{package_name.lower()}",
            site_packages / f"~{package_name.strip().lower().lstrip('~')}",
        ]
        if len(package_name) > 1:
            tilde_dirs.append(site_packages / f"~{package_name[1:]}")
            tilde_dirs.append(site_packages / f"~{package_name.strip().lower().lstrip('~')[1:]}")
        for d in tilde_dirs:
            if d.exists():
                try:
                    _remove_path(d, dry_run=dry_run)
                    removed.append(str(d))
                except Exception as e:
                    skipped.append(f"{d} ({type(e).__name__}: {e})")

        removed.extend(_remove_scripts_for_dist(dist_info, scripts_dir, dry_run=dry_run))

        try:
            _remove_path(dist_info, dry_run=dry_run)
            removed.append(str(dist_info))
        except Exception as e:
            skipped.append(f"{dist_info} ({type(e).__name__}: {e})")

        return {
            "name": package_name,
            "version": version,
            "removed": removed,
            "skipped": skipped,
            "file_count": len(removed),
            "missing": False,
        }

    return {"name": package_name, "version": None, "removed": removed, "skipped": skipped, "file_count": len(removed), "missing": False}


def remove_distribution(dist: md.Distribution, *, dry_run: bool) -> dict:
    # Always constrain deletions to sys.prefix to avoid accidental damage.
    prefix = Path(os.fspath(Path(sys.prefix)))

    removed: list[str] = []
    skipped: list[str] = []

    files = list(dist.files or [])
    for rel in files:
        abs_path = Path(dist.locate_file(rel))
        if not _safe_within_prefix(abs_path, prefix):
            skipped.append(str(abs_path))
            continue
        try:
            if abs_path.exists():
                _remove_path(abs_path, dry_run=dry_run)
                removed.append(str(abs_path))
        except Exception as e:
            skipped.append(f"{abs_path} ({type(e).__name__}: {e})")

    return {
        "name": dist.metadata.get("Name", "unknown"),
        "version": dist.version,
        "removed": removed,
        "skipped": skipped,
        "file_count": len(files),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Prune unused packages from the plum venv without pip (Windows tempfile ACL workaround).")
    parser.add_argument("--dry-run", action="store_true", help="Print deletions without removing anything.")
    parser.add_argument(
        "--remove",
        nargs="*",
        default=DEFAULT_REMOVE,
        help="Package names to remove (default: curated list).",
    )
    args = parser.parse_args()

    targets = [name.strip() for name in (args.remove or []) if name.strip()]
    if not targets:
        print("No packages specified.")
        return 0

    total_removed_files = 0
    missing: list[str] = []
    failures: list[str] = []

    for pkg in targets:
        try:
            dist = md.distribution(pkg)
            result = remove_distribution(dist, dry_run=args.dry_run)
        except Exception:
            # Fallback for broken/partial installs (e.g. pip uninstall left ~name dirs / dist-info renamed).
            result = remove_by_dist_info_name(pkg, dry_run=args.dry_run)
            if result.get("missing"):
                missing.append(pkg)
                continue
        total_removed_files += len(result["removed"])
        print(f"Removed {result['name']}=={result['version']} files={len(result['removed'])} skipped={len(result['skipped'])}")
        if result["skipped"]:
            failures.append(f"{pkg}: {len(result['skipped'])} skipped")

    if missing:
        print("Not installed:", ", ".join(sorted(set(missing))))
    if failures:
        print("Had skips/errors:", "; ".join(failures))

    print(f"Total removed files: {total_removed_files}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
