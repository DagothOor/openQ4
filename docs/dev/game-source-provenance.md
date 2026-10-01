# Game source provenance

The canonical single-player and multiplayer game sources now live in this
repository's `src/game/` and `src/mpgame/`. Their licences and authorship are
unchanged by the move. [LICENSING.md](../../LICENSING.md) distinguishes the
SDK-derived game code from the engine's GPL-covered code and dependencies.

## Imports

- Base game: [openQ4-game at `4d87dbdb`](https://github.com/themuffinator/openQ4-game/tree/4d87dbdb6934307988b371d3c794190a1380f322).
  The `src/game/` and `src/mpgame/` trees were imported without source edits.
- Awakening additions: [openQ4-game-awakening at `c4984298`](https://github.com/themuffinator/openQ4-game-awakening/tree/c49842986c0a519feeebc68d78e6f5509d99c3a7).
  Its `src/shared/` and `src/game/` trees were imported into
  `src/game/awakening/`, preserving source bytes. Its multiplayer price layer
  is excluded from the unified game.
- Both complete source histories are merge parents of the import commit and
  remain reachable from openQ4's history. Historical source revisions and tags
  in the archived repositories remain useful for older releases.
- The original `EULA.Development Kit.rtf` is retained byte-for-byte at
  [`LICENSES/QUAKE-4-SDK-EULA.rtf`](../../LICENSES/QUAKE-4-SDK-EULA.rtf).

Subsequent modifications are identified by openQ4's commit history. Source
relocation does not grant an alternative licence or remove original notices.
The existing SDK-derived game implementations are credited to id Software,
Raven Software and the openQ4 contributors. The Awakening feature descriptions
also acknowledge Ritual Entertainment and Justin Marshall's preservation work.

## Reference boundary

The expansion's original binaries, decompilation and reconstructed source are
behaviour references only. No recovered proprietary implementation or code from
the reconstructed GPL tree is imported into these SDK-derived sources.
The implementation carries forward the independently written openQ4 layer.

Neither retail game data nor expansion data is committed or distributed with
the game-source move. Runtime discovery reads user-supplied content.
