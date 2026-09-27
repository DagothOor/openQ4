#!/usr/bin/env python3
"""CI builds the Awakening (q4xbase) game-library layer from one pinned commit.

Every workflow that fetches openQ4-game-awakening pins the same OPENQ4_AWAKENING_SHA and
fetches it in a step right after the openQ4-game one, into the sibling directory that
OPENQ4_AWAKENING_REPO names. Because CI names the layer, Meson must refuse a named layer
that is missing instead of silently building without it. Packaging workflows stay out
until shipping q4xbase modules is decided, and so do the macOS thin builds that feed the
universal2 assembly, which only lipos baseoq4's modules.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
LAYER_URL = "https://github.com/themuffinator/openQ4-game-awakening.git"
REPO_ENV = "${{ github.workspace }}/../openQ4-game-awakening"
FETCH_STEP = "Fetch openQ4-game-awakening"

# workflow -> jobs that must build the layer
COVERED = {
    "commit-validation.yml": {"windows-x64", "linux-arm64", "windows-arm64", "linux-sanitizer", "linux-wayland"},
    "push-verification.yml": {"posix-builds", "windows-build", "windows-arm64-build"},
    "linux-arm64-cross.yml": {"cross-build"},
    "macos-debug.yml": {"macos-debug", "macos-openal-migration"},
    "macos-sanitizer.yml": {"macos-sanitizer"},
}
# workflow -> jobs that must not (None: the whole workflow)
EXCLUDED = {
    "manual-release.yml": None,
    "macos-universal2-candidate.yml": None,
    "commit-validation.yml": {"macos-arm64", "macos-x64", "script-smoke"},
    "push-verification.yml": {"script-smoke"},
}


def fail(message: str) -> None:
    raise AssertionError(message)


def read(name: str) -> list[str]:
    return (WORKFLOWS / name).read_text(encoding="utf-8").splitlines()


def top_level_env(lines: list[str]) -> dict[str, str]:
    env: dict[str, str] = {}
    inside = False
    for line in lines:
        if line == "env:":
            inside = True
            continue
        if inside:
            if line and not line.startswith(" "):
                break
            match = re.match(r"^  ([A-Z0-9_]+): (\S+)\s*$", line)
            if match:
                env[match.group(1)] = match.group(2)
    return env


def jobs(lines: list[str]) -> dict[str, list[str]]:
    start = lines.index("jobs:")
    heads = [i for i in range(start + 1, len(lines)) if re.match(r"^  [A-Za-z0-9_-]+:\s*$", lines[i])]
    blocks = {}
    for k, head in enumerate(heads):
        end = heads[k + 1] if k + 1 < len(heads) else len(lines)
        blocks[lines[head].strip()[:-1]] = lines[head:end]
    return blocks


def steps(block: list[str]) -> list[tuple[str, list[str]]]:
    starts = [i for i, line in enumerate(block) if line.startswith("      - ")]
    result = []
    for k, start in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else len(block)
        match = re.match(r"^      - name: (.+?)\s*$", block[start])
        result.append((match.group(1) if match else "", block[start:end]))
    return result


def fetching_jobs(name: str) -> set[str]:
    return {job for job, block in jobs(read(name)).items() if any(step == FETCH_STEP for step, _ in steps(block))}


def check_job(name: str, job: str, block: list[str]) -> None:
    job_steps = steps(block)
    names = [step for step, _ in job_steps]
    index = names.index(FETCH_STEP)
    if index == 0 or names[index - 1] != "Fetch openQ4-game":
        fail(f"{name} {job}: {FETCH_STEP!r} must directly follow 'Fetch openQ4-game'")
    if not any(line.strip() == f"OPENQ4_AWAKENING_REPO: {REPO_ENV}" for line in block):
        fail(f"{name} {job}: OPENQ4_AWAKENING_REPO must be {REPO_ENV!r}")
    body = "\n".join(job_steps[index][1])
    shell = re.search(r"^        shell: (\S+)", body, re.M)
    if not shell or shell.group(1) not in ("bash", "pwsh"):
        fail(f"{name} {job}: {FETCH_STEP!r} must set shell bash or pwsh")
    ref = '"${OPENQ4_AWAKENING_' if shell.group(1) == "bash" else '"$env:OPENQ4_AWAKENING_'
    for token in (LAYER_URL, f"fetch --depth 1 origin {ref}SHA", f"checkout --detach {ref}SHA", "rev-parse HEAD"):
        if token not in body:
            fail(f"{name} {job}: {FETCH_STEP!r} is missing {token!r}")


def main() -> int:
    shas: dict[str, str] = {}
    for name, expected in COVERED.items():
        lines = read(name)
        sha = top_level_env(lines).get("OPENQ4_AWAKENING_SHA", "")
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            fail(f"{name}: OPENQ4_AWAKENING_SHA must be a full commit id in the workflow env")
        shas[name] = sha
        found = fetching_jobs(name)
        if found != expected:
            fail(f"{name}: layer fetched by {sorted(found)}, expected {sorted(expected)}")
        blocks = jobs(lines)
        for job in expected:
            check_job(name, job, blocks[job])

    if len(set(shas.values())) != 1:
        fail("workflows pin different openQ4-game-awakening commits: " + ", ".join(f"{k}={v[:10]}" for k, v in shas.items()))

    for name, excluded in EXCLUDED.items():
        found = fetching_jobs(name)
        if excluded is None:
            if found or "OPENQ4_AWAKENING" in (WORKFLOWS / name).read_text(encoding="utf-8"):
                fail(f"{name}: packaging workflows must not fetch the layer until shipping q4xbase is decided")
        elif found & excluded:
            fail(f"{name}: {sorted(found & excluded)} must not fetch the layer")

    cross = (WORKFLOWS / "linux-arm64-cross.yml").read_text(encoding="utf-8")
    for module in ("builddir-arm64-cross/q4xbase/game-sp_arm64.so", "builddir-arm64-cross/q4xbase/game-mp_arm64.so"):
        if module not in cross:
            fail(f"linux-arm64-cross.yml must verify {module}")

    meson = (ROOT / "meson.build").read_text(encoding="utf-8")
    for token in ("OPENQ4_AWAKENING_REPO names ", "elif awakening_named", 'print("named" if raw else "sibling")'):
        if token not in meson:
            fail(f"meson.build must refuse a missing layer that OPENQ4_AWAKENING_REPO names ({token!r})")

    print(f"awakening_ci_contract: ok ({sum(len(j) for j in COVERED.values())} jobs pin {next(iter(shas.values()))[:10]})")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as error:
        print(f"awakening_ci_contract: FAIL: {error}", file=sys.stderr)
        sys.exit(1)
