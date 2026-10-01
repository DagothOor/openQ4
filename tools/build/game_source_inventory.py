#!/usr/bin/env python3
"""Track in-tree game source membership so new/removed files reconfigure Meson."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import subprocess
from pathlib import Path

SOURCE_SUFFIXES = {".cpp", ".c", ".cc", ".cxx", ".h", ".hpp", ".inl"}


def inventory(root: Path) -> dict:
    root = root.resolve(strict=True)
    paths = []
    digest = hashlib.sha256()
    for tree in ("src/game", "src/mpgame"):
        directory = root / tree
        if directory.is_symlink() or (directory.exists() and getattr(directory.stat(follow_symlinks=False), "st_file_attributes", 0) & 0x400):
            raise ValueError(f"game source directory is a link: {directory}")
        if not directory.is_dir():
            raise ValueError(f"missing canonical game source directory: {directory}")
        for path in sorted(directory.rglob("*")):
            if path.is_symlink() or getattr(path.stat(follow_symlinks=False), "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                raise ValueError(f"game source contains a link: {path}")
            if path.is_file() and path.suffix in SOURCE_SUFFIXES:
                relative = path.relative_to(root).as_posix()
                file_digest = hashlib.sha256(path.read_bytes()).hexdigest()
                paths.append({"path": relative, "sha256": file_digest})
                digest.update(relative.encode("utf-8") + b"\0")
                digest.update(bytes.fromhex(file_digest))
    def git(*args):
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else None
    commit = git("rev-parse", "HEAD")
    status = git("status", "--porcelain", "--untracked-files=all")
    return {"format": 1, "sourceRoot": root.as_posix(), "files": sorted(paths, key=lambda value: value['path']), "fileCount": len(paths),
            "sourceDigest": digest.hexdigest(), "projectGitCommit": commit,
            "gameLibsGitCommit": commit, "projectGitDirty": status != "",
            "gameLibsGitDirty": status != ""}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--check", type=Path)
    args = parser.parse_args()
    value = inventory(args.project)
    if args.check:
        try:
            previous = json.loads(args.check.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return 3
        return 0 if value == previous else 3
    print(json.dumps(value, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
