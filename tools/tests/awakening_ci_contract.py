#!/usr/bin/env python3
"""CI builds the Awakening (q4xbase) game-library layer from one pinned commit, and releases ship it.

Every workflow that fetches openQ4-game-awakening pins the same OPENQ4_AWAKENING_SHA and
fetches it in a step right after the openQ4-game one, into the sibling directory that
OPENQ4_AWAKENING_REPO names. Because CI names the layer, Meson must refuse a named layer
that is missing instead of silently building without it. The release workflows fetch the
pin the way they fetch openQ4-game: they refuse to reuse a checkout, verify the commit and
its cleanliness, then prove the staged layer came from it. Every packaging step requires
q4xbase, so a build that lost the layer cannot publish a package without it.
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
PINNED_FETCH_STEP = "Fetch pinned openQ4-game-awakening"
REQUIRE_LAYER = "--require-game-layer q4xbase"

# workflow -> jobs that must build the layer
COVERED = {
    "commit-validation.yml": {
        "windows-x64",
        "linux-arm64",
        "windows-arm64",
        "linux-sanitizer",
        "linux-wayland",
        "macos-arm64",
        "macos-x64",
    },
    "push-verification.yml": {"posix-builds", "windows-build", "windows-arm64-build"},
    "linux-arm64-cross.yml": {"cross-build"},
    "macos-debug.yml": {"macos-debug", "macos-openal-migration"},
    "macos-sanitizer.yml": {"macos-sanitizer"},
    "manual-release.yml": {"builds"},
    "macos-universal2-candidate.yml": {"thin_build"},
}
# workflows whose fetch follows the release pattern
RELEASE_WORKFLOWS = {"manual-release.yml", "macos-universal2-candidate.yml"}
# workflow -> jobs that must not fetch it
EXCLUDED = {
    "commit-validation.yml": {"script-smoke"},
    "push-verification.yml": {"script-smoke"},
}
# workflow -> packaging steps (by name) that must refuse a package without q4xbase
PACKAGING = {
    "manual-release.yml": "Prepare package",
    "macos-universal2-candidate.yml": "Package universal2 release candidate",
    "commit-validation.yml": "Package and validate universal2 app",
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
    return {
        job
        for job, block in jobs(read(name)).items()
        if any(step in (FETCH_STEP, PINNED_FETCH_STEP) for step, _ in steps(block))
    }


def check_job(name: str, job: str, block: list[str]) -> None:
    job_steps = steps(block)
    names = [step for step, _ in job_steps]
    release = name in RELEASE_WORKFLOWS
    fetch_step = PINNED_FETCH_STEP if release else FETCH_STEP
    if fetch_step not in names:
        fail(f"{name} {job}: the layer must be fetched by a step named {fetch_step!r}")
    index = names.index(fetch_step)
    previous = names[index - 1] if index > 0 else ""
    if release:
        if not previous.startswith("Fetch pinned openQ4-game") or previous == fetch_step:
            fail(f"{name} {job}: {fetch_step!r} must directly follow the pinned openQ4-game fetch")
    elif previous != "Fetch openQ4-game":
        fail(f"{name} {job}: {fetch_step!r} must directly follow 'Fetch openQ4-game'")
    if not any(line.strip() == f"OPENQ4_AWAKENING_REPO: {REPO_ENV}" for line in block):
        fail(f"{name} {job}: OPENQ4_AWAKENING_REPO must be {REPO_ENV!r}")
    body = "\n".join(job_steps[index][1])
    shell = re.search(r"^        shell: (\S+)", body, re.M)
    if not shell or shell.group(1) not in ("bash", "pwsh") or (release and shell.group(1) != "bash"):
        fail(f"{name} {job}: {fetch_step!r} must set shell bash{'' if release else ' or pwsh'}")
    ref = '"${OPENQ4_AWAKENING_' if shell.group(1) == "bash" else '"$env:OPENQ4_AWAKENING_'
    if release:
        tokens = (
            LAYER_URL,
            "=~ ^[0-9a-f]{40}$",
            "Refusing to reuse an existing openQ4-game-awakening checkout",
            f"fetch --quiet --no-tags --depth=1 origin {ref}SHA",
            f"checkout --quiet --detach {ref}SHA",
            "rev-parse --verify 'HEAD^{commit}'",
            "status --porcelain --untracked-files=all",
        )
    else:
        tokens = (LAYER_URL, f"fetch --depth 1 origin {ref}SHA", f"checkout --detach {ref}SHA", "rev-parse HEAD")
    for token in tokens:
        if token not in body:
            fail(f"{name} {job}: {fetch_step!r} is missing {token!r}")
    if release:
        job_text = "\n".join(block)
        for token in (
            '--layer-root "${OPENQ4_AWAKENING_REPO}"',
            "--manifest --layer awakening)",
            '--expected-layer-commit "${OPENQ4_AWAKENING_SHA}"',
        ):
            if token not in job_text:
                fail(f"{name} {job}: the staged layer's provenance check is missing {token!r}")


def check_packaging(name: str, step_name: str) -> None:
    for _, block in jobs(read(name)).items():
        for step, lines in steps(block):
            if step == step_name:
                body = "\n".join(lines)
                if REQUIRE_LAYER not in body:
                    fail(f"{name} {step_name!r}: packaging must pass {REQUIRE_LAYER!r}")
                return
    fail(f"{name}: no packaging step named {step_name!r}")


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
        if found & excluded:
            fail(f"{name}: {sorted(found & excluded)} must not fetch the layer")

    for name, step_name in PACKAGING.items():
        check_packaging(name, step_name)

    release = (WORKFLOWS / "manual-release.yml").read_text(encoding="utf-8")
    for token in (
        # the Linux debug-symbol split covers the layer's modules
        '".install/q4xbase/game-sp_${{ matrix.binary_arch }}.so"',
        '".install/q4xbase/game-mp_${{ matrix.binary_arch }}.so"',
        # macOS embeds the layer and loads its own module from Contents/Frameworks/q4xbase
        '".install/q4xbase/game-sp_${{ matrix.binary_arch }}.dylib"',
        'layer_sp_module="${module_dir}/q4xbase/game-sp_${{ matrix.binary_arch }}.dylib"',
        "+set fs_game q4xbase",
        "/openQ4.app/Contents/Frameworks/q4xbase/game-sp_${{ matrix.binary_arch }}.dylib'",
    ):
        if token not in release:
            fail(f"manual-release.yml must ship q4xbase ({token!r})")

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
