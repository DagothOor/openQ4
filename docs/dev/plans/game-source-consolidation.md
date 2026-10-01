# Game source consolidation and campaign selection

Status: implementation in progress, 1 October 2026.

The game libraries and Awakening single-player additions move into openQ4.
`openQ4-game` and `openQ4-game-awakening` become historical, read-only
repositories after their retirement notices and the replacement are published.

## Required result

- Preserve the existing worktree in a separate commit before migration.
- Preserve the imported source histories, original notices, SDK EULA and credits.
- Build the canonical `src/game` and `src/mpgame` directly from this checkout;
  builds, tests, CI and packages must not require either companion checkout.
- Compile Awakening's existing independently implemented SP classes, weapons,
  effects and script events into `game_sp`. Do not import the reconstruction or
  the expansion's multiplayer layer.
- Keep stock class spawning and saved object representations unchanged when
  Quake 4 is active. Scope Awakening class substitutions to its active campaign.
- Discover expansion content without mounting it or mistaking packaged metadata
  or old game binaries for a playable installation. Support loose and PK4 data
  under configured roots, plus an explicitly configured external content root.
- Present localized campaign selection in the existing single-player menu.
  Preserve the Arena Campaign option. Keep saves, Continue and autosaves in the
  existing `baseoq4` and `q4xbase` namespaces.
- Switch campaigns through a complete content reload, preserving the pending
  launch/menu request. Restore base content before multiplayer or Arena begins.
- Never load obsolete expansion modules or the leaked game binary. Preserve the
  user's original content and saves during upgrades.
- Keep all runtime modules under `baseoq4`, refresh release documentation and
  package notices, and make the SDK-derived source licence scope explicit.
- Publish retirement documentation to both companion repositories, archive
  them, and verify the resulting remote state.

## Validation

Record the source/build identity and savegames before migration. Verify the
Windows integrated build and stage; standalone engine-only and game-only
configurations; platform/packaging/CI contracts; stock SP with the expansion
absent and present; all thirteen expansion maps and save/restore; campaign
switches, class substitution, declaration precedence, module selection and
multiplayer/Arena isolation. Check both OpenGL and Vulkan where runtime evidence
is available. Promote the useful temporary Awakening checks into maintained
tests, with portable paths and engine-issued captures.

Source relocation must not change serialization. Existing saves from the
current supported save format must remain loadable. The alpha's missing assets,
unreachable features and invalid authored script calls remain documented content
limitations; they do not justify regressions in stock Quake 4.

## Licence and provenance boundary

This is a source consolidation, not a relicensing of id Software's SDK. Engine
GPL notices and accompanying Additional Terms remain intact. SDK-derived game
sources and their additions retain the SDK EULA and require the full game.
The licensing inventory must distinguish these scopes and must not suggest that
adding an EULA notice settles compatibility of linked distributions. No new
rights-holder permission or legal compatibility opinion is asserted here.

## Evidence

- Existing worktree snapshot: `98e453662704a79df722bc2f4696ddba8c42de03`.
- Base game import source: `4d87dbdb6934307988b371d3c794190a1380f322`.
- Awakening import source: `c49842986c0a519feeebc68d78e6f5509d99c3a7`.
- Build, runtime and migration evidence: to be recorded as each gate completes.
