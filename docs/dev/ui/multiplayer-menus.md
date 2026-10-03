# Retained multiplayer menus

The retained multiplayer menus replace the stock full-screen multiplayer menu
with one card over the live, softened match (section 14.18 of the
[visual specification](../ui-visual-design.md), requirement `FLOW-046`). This
increment builds the Escape card's shell: the card, its header, the eight-tab
strip, the prompt bar, the Disconnect confirmation, the softening and its
release, and the session and game plumbing that let the card cover the game's
own menu. Every page still hands off to its stock page, so the card stays
opt-in. The Welcome card and the pages themselves follow in later increments
(the plan's B2 to B9).

## The gate

`ui_retainedMultiplayer` (default 0) opts into the card. `ui_retained` alone
includes it only once no page hands off any more: the session lists the
Escape pages that still do in `RETAINED_MP_ESCAPE_MISSING_PAGES`, today all
eight, and `tools/tests/ui_retained_gate.py` keeps that list equal to the
document's hand-off pages (its `stock_<page>` programs). Players never see a
mix of card and stock pages unless they opt in.

## The cover

The game keeps its menu. `mpmain.gui` stays the active GUI, with its state, its
commands, its legacy pages and the Match Control adapter, so the game sees no
difference except that the menu stops drawing. The session presents the card
over it while all of these hold (`idSessionLocal::UpdateRetainedMultiplayer`):

- the gate or the opt-in is on, a multiplayer map is spawned, and the active
  GUI is the game's multiplayer menu (`guis/mpmain.gui`, drawn over the game);
  the chat, buy and summary screens are other GUIs and are never covered;
- no test GUI or retained preview is open, and no stock page has taken this
  opening over (below);
- the game answers `retainedMultiplayerCover` with the protocol the session
  expects (`mp.protocol` 1) and allows the cover now (`mp.cover_allowed`). The
  game refuses while the connect-time join offer stands, since the card has no
  Welcome variant yet and the stock join card keeps that opening, and in an
  Arena Campaign match, which keeps its own menu.

Otherwise the stock menu presents. Like the other retained screens, the card
falls back to the stock menu for the session when its document is not
installed (quietly), cannot load (one warning) or stops drawing (one warning),
when a mod supplies its own `guis/mpmain.gui`, and when the game module does
not answer the protocol, as an older or a mod's game module would not. A
refused cover holds only for that opening.

Each frame the session asks the game for the card's state
(`retainedMultiplayerState`). The game writes only the keys that changed and a
new `mp.revision`, and the session publishes the card only when the revision
moves. Closing the menu, opening the main menu, or anything else that takes the
screen retires the card (`retainedMultiplayerUncover`); the game then draws its
menu again. A map change retires it without a release and opens the next
map's card on its first page; the document itself loads inside each
multiplayer level load.

`ui_retainedStatus` reports the opt-in as `multiplayer=` and the covering card
as `mp=escape` (`mp=-` otherwise); `openq4_retainedGui` addresses the card
while it covers.

## The card

The card is the section 6 card: a black body at 0.94 inside one
`marine.rail.card` rail, 12 dp cuts at the top-trailing and bottom-leading
corners and 3 dp cuts at the other two. It is centered on the projection
center at every view, 477 dp tall.

- **Header.** The white 0.16 wash in the light plate's shape, the 1 dp rule,
  the 8 dp triangle and the map in Marine 20 dp; trailing it the mode, the
  clock in the value color and the score, "MARINES 12 - 9 STROGG" with the
  player's team first in team modes and the player's place and score in the
  others. The title takes whatever the trailing texts leave and clips there.
- **Tab strip.** Eight tabs, Team, Players, Vote, Match, Settings, Voice,
  Server and Admin, as short labels written for the strip in every language,
  Marine 14 dp. The active tab rises 30 dp with its 3 dp leading flare and its
  18 dp 45-degree shoulder, #5A652A from 1.00 to 0.60 inside a white outline,
  and breaks the baseline under it; a #5A652A wash fades below the strip over
  one tab height. Inactive labels sit at 0.55 and rise to 0.85 on hover; focus
  turns a label orange. Q and E keycaps at the strip's ends switch tabs.
- **Pages.** Content is inset 24 dp. Each page says it opens in the classic
  multiplayer menu and offers that as its primary action, an in-game plate
  (b6_light, 0.62 for the primary action and 0.28 for others, 1.00 with the
  orange marker when focused).
- **Prompt bar.** Inside the card's bottom inset: Resume on Escape, Tabs on Q
  and E, Select on Enter, then Main Menu and Disconnect as actions at the
  trailing end. Disconnect asks first in the stock confirmation, which
  soft-focuses the card and the view beneath it.

### Width

The specified 648 dp cannot hold eight tabs: with the active tab's flare and
shoulder each tab needs its label plus 31 dp, and even the shortest English
labels need about 800 dp at 14 dp, so the Escape card grows to the widest
language's fitted strip. `tools/ui/retained_mp_menus.py` measures every
language's labels in the shipped Marine face, sizes the card to the widest
strip plus a 2 % margin, today 890 dp (Hungarian), and fails the build if a
language would need more than a 4:3 view allows (928 dp, 16 dp from each
side). Each tab is as wide as its label in the running language, and the tabs
share the remainder.

## Input

The card owns the menu's input while it covers it. Q and E, and the gamepad
shoulders, switch tabs (the document's `onTabPrevious` and `onTabNext`), as do
the strip's keycaps and the tabs themselves; the strip wraps both ways. A
switch is at once: the arriving page fades in over 150 ms while the leaving
page fades out and takes no input, and the arriving page's primary action
takes focus. Back closes the Disconnect confirmation first, then resumes the
match. A function key the card leaves alone runs its binding, as over the
stock menu, so F1 and F2 still vote.

The card's verbs are the stock menu's own commands with its selection sound:

| Verb | Game command |
| --- | --- |
| `mpClose` (Resume, Back) | `play main_menu_selection ; close` |
| `mpMainMenu` | `play main_menu_selection ; mainMenu` |
| `mpDisconnect` (after the confirmation) | `play main_menu_selection ; disconnect` |
| `mpStockPage` | the stock page's own button, by `card.stock_page` |

A hand-off presents the stock menu at once and presses the page's button as
soon as the menu's opening shows it, within 500 ms; the stock menu then keeps
the menu until it closes. The session refuses the card's verbs from any other
GUI and every other verb from the card.

## Motion

Opening ramps the softening (`modal.softfocus`: a 5 u blur at 0.80 saturation,
never dimmed) over 250 ms while the card rises 12 dp and fades in over 150 ms,
easing out. Every way out closes the card at once. Closing the menu over the
running game releases the softening over 250 ms while the session keeps
drawing the closed card's backdrop, as the pause screen does; the next
activation brings it back. Under reduced motion the card does not rise, and
the softening and the fade take 80 ms. Without softening (the renderer cannot,
or `ui_retainedOpaqueBacking 1`) a centred darkening scrim with a vignette
stands in.

## Decisions taken provisionally

The plan left these to the owner. The card is opt-in, so each can still change
without affecting players:

- **Width (D8).** As above: the card grows past 648 dp to fit the strip.
- **Tab labels (D7).** Marine 14 dp, short labels written for the strip; the
  active label is white.
- **Softening (D1).** `modal.softfocus` values, with a centred scrim and
  vignette in one layer as the fallback.
- **Prompt bar (D4).** Only the global prompts, with Main Menu and Disconnect
  as actions; section 14.18 governs over `WID-019`.
- **Motion (D6).** No card exit motion; reduced motion as above.
- **Tabs per map (D18).** The card remembers its tab while a map runs and
  starts each map on Team.

## Validation

- `tools/tests/ui_retained_gate.py` compiles the cover, the retirement, the
  verbs and the hand-off against counted doubles: the gate and the opt-in,
  every fallback, a refused cover, the revision-driven publishing, Resume's
  release in the same frame, Main Menu without one, the hand-off and its
  500 ms wait, out-of-range pages, a map change, the screens that are never
  covered and the refused verbs. It also pins the missing-pages list to the
  document, the stock buttons to the generator, the game's side of the
  protocol, and the frame, input and draw order.
- `openq4-ui-retained-screens` loads the card into the real runtime: centered
  and the same size at 1280x720, 1920x1080 and 1024x768, the opening and its
  reduced-motion form, the tab programs and their wrap, the cross-fade with
  the leaving page out of reach, the hand-off and Back actions, the prompt bar
  and the confirmation, the header's clipping title, and the release.
- A live probe on a Team DM listen server with bots (hidden window, console
  verbs only) opens the card over the match on OpenGL in English, Hungarian
  and Russian and on Vulkan in German: the card covers the menu, the tabs
  switch and wrap, Back closes the confirmation and then resumes with the
  release, and a hand-off opens the stock Players page.

Evidence: `.tmp/ui/retained-mp-escape/validation-evidence.json`, SHA-256
`39b8f759d2e6445b321c64507f125dcc015334dbbcb6ffaf0bb363df6e3255cf`.

The card's acceptance continues under `FLOW-046`.

## Known limitations

- Every page hands off to its stock page, and the stock menu then keeps the
  menu until it closes; the card does not come back over it.
- There is no Welcome card: the connect-time join offer keeps the stock join
  card.
- The prompt bar shows keyboard keycaps only; controller glyphs wait for the
  glyph families (`INP-011`).
- Narrower views than 4:3 (5:4, portrait) do not scale the card down yet
  (`LAY-021`).
- The multiplayer smokes that capture stock pages do not pin `ui_retained 0`;
  they need to once the card joins the default.
