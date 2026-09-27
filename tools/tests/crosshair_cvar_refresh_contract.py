#!/usr/bin/env python3
"""Static contract checks for applying crosshair cvar changes to the cursor GUI at once."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOTS = ("src/game", "src/mpgame")
TEST_PATH = "tools/tests/crosshair_cvar_refresh_contract.py"
REFRESH = "static void Player_RefreshCrosshairGUI( idUserInterface *cursor, const rvWeapon *weapon, bool driving )"


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8").replace("\r\n", "\n")


def require(haystack: str, needle: str, context: str) -> None:
    if needle not in haystack:
        raise AssertionError(f"Missing {needle!r} in {context}")


def function(source: str, signature: str, context: str) -> str:
    start = source.find(signature)
    if start < 0:
        raise AssertionError(f"Missing function {signature!r} in {context}")
    opening = source.find("{", start + len(signature))
    if opening < 0:
        raise AssertionError(f"Missing body for {signature!r} in {context}")

    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1 : index]
    raise AssertionError(f"Unterminated body for {signature!r} in {context}")


def require_order(body: str, needles: tuple[str, ...], context: str) -> None:
    cursor = -1
    for needle in needles:
        index = body.find(needle, cursor + 1)
        if index < 0:
            raise AssertionError(f"Missing ordered token {needle!r} in {context}")
        cursor = index


def normalized(body: str) -> str:
    return " ".join(body.split())


def check_source_root(source_root: str) -> str:
    player_path = f"{source_root}/Player.cpp"
    player = read(player_path)

    # Only the modified flags are tested per drawn frame; the cursor is touched
    # when one of the three crosshair cvars changed, and the flags are cleared
    # only once the change reached the cursor.
    refresh = function(player, REFRESH, player_path)
    require_order(
        refresh,
        (
            "if ( !g_crosshairColor.IsModified() && !g_crosshairCustom.IsModified() && !g_crosshairCustomFile.IsModified() ) {",
            "return;",
            "if ( !driving ) {",
            "if ( weapon == NULL ) {",
            "return;",
            "weapon->UpdateCrosshairGUI( cursor );",
            'cursor->HandleNamedEvent( "weaponChange" );',
            "g_crosshairColor.ClearModified();",
            "g_crosshairCustom.ClearModified();",
            "g_crosshairCustomFile.ClearModified();",
        ),
        f"{player_path} Player_RefreshCrosshairGUI",
    )

    # After each cursor redraw: the first redraw runs the cursor GUI's onInit,
    # which would reset the colours the refresh applies.
    draw = function(player, "void idPlayer::DrawHUD( idUserInterface *_hud )", player_path)
    require_order(
        draw,
        (
            "vehicleController.UpdateCursorGUI( cursor );",
            "cursor->Redraw( gameLocal.time );",
            "Player_RefreshCrosshairGUI( cursor, weapon, true );",
            "cursor->Redraw( gameLocal.time );",
            "Player_RefreshCrosshairGUI( cursor, weapon, false );",
            "rvHitMarker::Draw();",
        ),
        f"{player_path} DrawHUD cursor refresh",
    )

    # The stock per-think refresh was Xbox 360 only and never ran on MP clients.
    think = function(player, "void idPlayer::Think( void )", player_path)
    if "g_crosshairColor.IsModified()" in think:
        raise AssertionError(f"{player_path} idPlayer::Think still polls g_crosshairColor; DrawHUD owns the refresh")

    return normalized(refresh)


def main() -> None:
    bodies = {source_root: check_source_root(source_root) for source_root in SOURCE_ROOTS}
    if bodies[SOURCE_ROOTS[0]] != bodies[SOURCE_ROOTS[1]]:
        raise AssertionError("SP/MP drift in Player_RefreshCrosshairGUI")

    workflow = read(".github/workflows/commit-validation.yml")
    if workflow.count(TEST_PATH) != 8:
        raise AssertionError("Crosshair cvar refresh contract must be compiled and run in all four static-check jobs")

    print("crosshair_cvar_refresh_contract: ok")


if __name__ == "__main__":
    main()
