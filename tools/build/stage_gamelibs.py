#!/usr/bin/env python3
"""Stage openQ4-game game sources into a temporary local tree.

usage: stage_gamelibs.py <project-root> <gamelibs-root> <stage-root> [--layer <layer-root>]
       stage_gamelibs.py --check-fresh <stage-root>

With --layer, a game-library layer (see game_layer.py) is staged on top: its
sources are copied into src/game/<id>/ and src/mpgame/<id>/ beside the
unchanged openQ4-game trees, so they include base headers exactly as base
sources do. A layer never replaces an openQ4-game file. --check-fresh exits
0 when a stage still matches its recorded sources and 3 when it is stale.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import game_layer


OPENQ4_SUPPORT_DIRS = (
    "idlib",
    "renderer",
    "ui",
    "sys",
    "bse",
    "MayaImport",
)

MANIFEST_NAME = "openq4_gamelibs_stage_manifest.json"
PYTHON_BYTECODE_SUFFIXES = (".pyc", ".pyo")


def repo_git_value(root: Path, *args: str) -> str:
    if not (root / ".git").exists():
        return ""

    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def repo_git_dirty(root: Path) -> bool:
    return bool(repo_git_value(root, "status", "--porcelain"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_regular_source_files(source_dir: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(source_dir.rglob("*")):
        if path.is_symlink():
            raise RuntimeError(f"refusing to stage symlink: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise RuntimeError(f"refusing to stage non-regular file: {path}")
        relative = path.relative_to(source_dir)
        if "__pycache__" in relative.parts or path.suffix.lower() in PYTHON_BYTECODE_SUFFIXES:
            continue
        files.append(path)
    return files


def copy_regular_tree(source_dir: Path, dest_dir: Path) -> list[Path]:
    if dest_dir.exists():
        shutil.rmtree(dest_dir)

    copied: list[Path] = []
    for source_path in iter_regular_source_files(source_dir):
        rel = source_path.relative_to(source_dir)
        if any(part in ("", ".", "..") for part in rel.parts):
            raise RuntimeError(f"refusing to stage unsafe path: {source_path}")

        dest_path = dest_dir / rel
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        # This is a generated compiler-input tree. A changed source may carry
        # a timestamp older than an existing PCH (checkout or a concurrent
        # companion edit), so the newly staged copy must get a fresh mtime.
        # Preserve permissions, but never backdate a replacement build input.
        shutil.copy(source_path, dest_path)
        copied.append(dest_path)
    return copied


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def validate_stage_root(project_root: Path, gamelibs_root: Path, stage_root: Path) -> None:
    if stage_root.is_symlink():
        raise RuntimeError(f"refusing to stage into symlink: {stage_root}")

    project_tmp = project_root / ".tmp"
    if not is_relative_to(stage_root, project_tmp) or stage_root == project_tmp:
        raise RuntimeError(f"stage root must be under openQ4 .tmp: {stage_root}")

    if is_relative_to(project_root, stage_root) or is_relative_to(gamelibs_root, stage_root):
        raise RuntimeError(f"refusing to stage over source repository: {stage_root}")


def copy_game_sources(source_game_dir: Path, dest_game_dir: Path) -> list[Path]:
    return copy_regular_tree(source_game_dir, dest_game_dir)


def mirror_support_dir(source_dir: Path, dest_dir: Path) -> list[Path]:
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    if not source_dir.is_dir():
        return []
    return copy_regular_tree(source_dir, dest_dir)


def mirror_project_support_dirs(project_root: Path, stage_root: Path) -> list[Path]:
    source_root = project_root / "src"
    stage_src_root = stage_root / "src"
    copied: list[Path] = []

    for dir_name in OPENQ4_SUPPORT_DIRS:
        copied += mirror_support_dir(source_root / dir_name, stage_src_root / dir_name)
    return copied


def staged_file_manifest(stage_root: Path, staged_files: list[Path]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for path in sorted(staged_files):
        entries.append(
            {
                "path": path.relative_to(stage_root).as_posix(),
                "sha256": file_sha256(path),
            }
        )
    return entries


def write_stage_manifest(
    project_root: Path,
    gamelibs_root: Path,
    stage_root: Path,
    staged_files: list[Path],
    source_roots: list[tuple[Path, Path]] | None = None,
    layer: dict | None = None,
) -> None:
    manifest = {
        "format": 1,
        "projectRoot": project_root.as_posix(),
        "projectGitCommit": repo_git_value(project_root, "rev-parse", "--verify", "HEAD"),
        "projectGitDirty": repo_git_dirty(project_root),
        "gameLibsRoot": gamelibs_root.as_posix(),
        "gameLibsGitCommit": repo_git_value(gamelibs_root, "rev-parse", "--verify", "HEAD"),
        "gameLibsGitDirty": repo_git_dirty(gamelibs_root),
        "fileCount": len(staged_files),
        "files": staged_file_manifest(stage_root, staged_files),
    }
    if source_roots is not None:
        # every staged directory and the source it mirrors, for --check-fresh
        manifest["sourceRoots"] = [
            {"source": source.as_posix(), "staged": staged.relative_to(stage_root).as_posix()}
            for source, staged in source_roots
        ]
    if layer is not None:
        manifest["layer"] = {
            "id": layer["id"],
            "gameDir": layer["gameDir"],
            "root": layer["root"].as_posix(),
            "gitCommit": repo_git_value(layer["root"], "rev-parse", "--verify", "HEAD"),
            "gitDirty": repo_git_dirty(layer["root"]),
        }

    manifest_path = stage_root / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def stage_layer_sources(layer: dict, stage_root: Path) -> tuple[list[Path], list[tuple[Path, Path]]]:
    """Copy a layer's source trees into src/<module>/<id>/ of the stage.

    The destination directories must not exist in the staged openQ4-game trees:
    a layer only ever adds files.
    """
    layer_id = layer["id"]
    staged: list[Path] = []
    roots: list[tuple[Path, Path]] = []
    claimed: dict[Path, str] = {}
    for module in ("game", "mpgame"):
        dest_root = stage_root / "src" / module / layer_id
        if dest_root.exists():
            raise RuntimeError(f"openQ4-game already has src/{module}/{layer_id}; layer '{layer_id}' would replace it")
        # both module trees exist even when a layer only feeds one of them
        dest_root.mkdir(parents=True)

    for tree, source_dir in layer["sources"].items():
        for module in game_layer.LAYER_TREE_MODULES[tree]:
            dest_root = stage_root / "src" / module / layer_id
            for source_path in iter_regular_source_files(source_dir):
                rel = source_path.relative_to(source_dir)
                if any(part in ("", ".", "..") for part in rel.parts):
                    raise RuntimeError(f"refusing to stage unsafe path: {source_path}")
                dest_path = dest_root / rel
                if dest_path in claimed:
                    raise RuntimeError(
                        f"layer '{layer_id}' provides src/{module}/{layer_id}/{rel.as_posix()} "
                        f"from both '{claimed[dest_path]}' and '{tree}'"
                    )
                claimed[dest_path] = tree
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(source_path, dest_path)
                staged.append(dest_path)
            roots.append((source_dir, dest_root))
    return staged, roots


def check_stage_fresh(stage_root: Path) -> bool:
    """True while every recorded source root still matches its staged copy.

    Needs a manifest written with source roots; any stage without them, or any
    difference in the set of files or their contents, reads as stale.
    """
    manifest_path = stage_root / MANIFEST_NAME
    if manifest_path.is_symlink() or not manifest_path.is_file():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    roots = manifest.get("sourceRoots")
    files = manifest.get("files")
    if manifest.get("format") != 1 or not isinstance(roots, list) or not isinstance(files, list):
        return False
    recorded = {entry.get("path"): entry.get("sha256") for entry in files if isinstance(entry, dict)}

    expected: dict[str, Path] = {}
    for root in roots:
        if not isinstance(root, dict) or not isinstance(root.get("source"), str) or not isinstance(root.get("staged"), str):
            return False
        source_dir = Path(root["source"])
        if not source_dir.is_dir():
            return False
        try:
            source_files = iter_regular_source_files(source_dir)
        except RuntimeError:
            return False
        for source_path in source_files:
            rel = (Path(root["staged"]) / source_path.relative_to(source_dir)).as_posix()
            if rel in expected:
                # two sources for one staged file (say a layer's shared and game
                # trees): restaging reports the conflict
                return False
            expected[rel] = source_path

    staged_under_roots = {
        rel for rel in recorded
        if any(rel.startswith(root["staged"] + "/") for root in roots)
    }
    if set(expected) != staged_under_roots:
        return False
    for rel, source_path in expected.items():
        staged_path = stage_root / rel
        if not staged_path.is_file() or file_sha256(source_path) != recorded[rel] or file_sha256(staged_path) != recorded[rel]:
            return False
    return True


def validate_stage_manifest(stage_root: Path) -> None:
    stage_root = stage_root.resolve()
    manifest_path = stage_root / MANIFEST_NAME
    if manifest_path.is_symlink():
        raise RuntimeError(f"stage manifest must not be a symlink: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != 1:
        raise RuntimeError("stage manifest has unsupported format")
    files = manifest.get("files")
    file_count = manifest.get("fileCount")
    if not isinstance(files, list) or not isinstance(file_count, int) or isinstance(file_count, bool) or file_count != len(files):
        raise RuntimeError("stage manifest file count is inconsistent")

    for entry in files:
        rel = entry.get("path")
        expected_hash = entry.get("sha256")
        if not isinstance(rel, str) or not isinstance(expected_hash, str):
            raise RuntimeError("stage manifest contains malformed file entry")
        if re.fullmatch(r"[0-9a-f]{64}", expected_hash) is None:
            raise RuntimeError(f"stage manifest contains malformed sha256 for {rel}")

        rel_path = Path(rel)
        if not rel_path.parts or rel_path.is_absolute() or any(part in ("", ".", "..") for part in rel_path.parts):
            raise RuntimeError(f"stage manifest contains unsafe path: {rel}")

        path = (stage_root / rel_path).resolve()
        if not is_relative_to(path, stage_root):
            raise RuntimeError(f"stage manifest path escapes stage root: {rel}")
        if path.is_symlink() or not path.is_file():
            raise RuntimeError(f"stage manifest references missing file: {rel}")
        actual_hash = file_sha256(path)
        if actual_hash != expected_hash:
            raise RuntimeError(f"stage manifest hash mismatch for {rel}")


def prepare_stage_root(stage_root: Path) -> None:
    if stage_root.exists():
        shutil.rmtree(stage_root)
    stage_root.mkdir(parents=True, exist_ok=True)


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[1] == "--check-fresh":
        return 0 if check_stage_fresh(Path(argv[2]).resolve()) else 3

    layer_arg = None
    if len(argv) == 6 and argv[4] == "--layer":
        layer_arg = argv[5]
        argv = argv[:4]
    if len(argv) != 4:
        print(
            "usage: stage_gamelibs.py <project-root> <gamelibs-root> <stage-root> [--layer <layer-root>]\n"
            "       stage_gamelibs.py --check-fresh <stage-root>",
            file=sys.stderr,
        )
        return 2

    raw_project_root = Path(argv[1])
    raw_gamelibs_root = Path(argv[2])
    if raw_project_root.is_symlink():
        print(f"error: openQ4 root must not be a symlink: {raw_project_root}", file=sys.stderr)
        return 1
    if raw_gamelibs_root.is_symlink():
        print(f"error: GameLibs root must not be a symlink: {raw_gamelibs_root}", file=sys.stderr)
        return 1

    project_root = raw_project_root.resolve()
    gamelibs_root = raw_gamelibs_root.resolve()
    raw_stage_root = Path(argv[3])
    if raw_stage_root.is_symlink():
        print(f"error: refusing to stage into symlink: {raw_stage_root}", file=sys.stderr)
        return 1
    stage_root = raw_stage_root.resolve()

    source_game_dirs = {
        "game": gamelibs_root / "src" / "game",
        "mpgame": gamelibs_root / "src" / "mpgame",
    }
    for module_name, source_game_dir in source_game_dirs.items():
        if not source_game_dir.is_dir():
            print(f"error: {module_name} source directory not found: {source_game_dir}", file=sys.stderr)
            return 1

    if not project_root.is_dir():
        print(f"error: openQ4 root not found: {project_root}", file=sys.stderr)
        return 1

    try:
        layer = game_layer.load_layer(Path(layer_arg)) if layer_arg is not None else None
        validate_stage_root(project_root, gamelibs_root, stage_root)
        if layer is not None and is_relative_to(layer["root"], stage_root):
            raise RuntimeError(f"refusing to stage over source repository: {stage_root}")
        prepare_stage_root(stage_root)
        staged_files = []
        source_roots: list[tuple[Path, Path]] = []
        for module_name, source_game_dir in source_game_dirs.items():
            staged_files += copy_game_sources(source_game_dir, stage_root / "src" / module_name)
            source_roots.append((source_game_dir, stage_root / "src" / module_name))
        staged_files += mirror_project_support_dirs(project_root, stage_root)
        for dir_name in OPENQ4_SUPPORT_DIRS:
            if (project_root / "src" / dir_name).is_dir():
                source_roots.append((project_root / "src" / dir_name, stage_root / "src" / dir_name))
        if layer is not None:
            layer_files, layer_roots = stage_layer_sources(layer, stage_root)
            staged_files += layer_files
            source_roots += layer_roots
        write_stage_manifest(project_root, gamelibs_root, stage_root, staged_files, source_roots, layer)
        validate_stage_manifest(stage_root)
    except (RuntimeError, game_layer.LayerError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(stage_root.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
