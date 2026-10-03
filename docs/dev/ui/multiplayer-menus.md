# Retained multiplayer menus

The retained multiplayer menus replace the stock full-screen multiplayer menu
with one card over the live, softened match (section 14.18 of the
[visual specification](../ui-visual-design.md), requirement `FLOW-046`). The
Escape card's shell came first: the card, its header, the eight-tab strip, the
prompt bar, the Disconnect confirmation, the softening and its release, and the
session and game plumbing that let the card cover the game's own menu. The
Team, Players and Server pages are built on it; the other five pages still
hand off to their stock pages, so the card stays opt-in. The Welcome card and
the other pages follow in later increments (the plan's B4 to B9).

## The gate

`ui_retainedMultiplayer` (default 0) opts into the card. `ui_retained` alone
includes it only once no page hands off any more: the session lists the
Escape pages that still do in `RETAINED_MP_ESCAPE_MISSING_PAGES`, today
Vote, Match, Settings, Voice and Admin, and
`tools/tests/ui_retained_gate.py` keeps that list equal to the
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
- **Pages.** Content is inset 24 dp. Actions are in-game plates (b6_light,
  0.62 for the primary action and 0.28 for others, 1.00 with the orange marker
  when focused). A page not built yet says it opens in the classic
  multiplayer menu and offers that as its primary action.
- **Prompt bar.** Inside the card's bottom inset: Resume on Escape, Tabs on Q
  and E, Select on Enter, then Main Menu and Disconnect as actions at the
  trailing end. Disconnect asks first in the stock confirmation, which
  soft-focuses the card and the view beneath it.

### The Team page

The game decides what the Team page offers, from the local player's state:

| Player | Actions |
| --- | --- |
| On a team | Switch team, with the team sizes it would leave; Spectate; Ready |
| Spectating a team mode | Join the team auto join would pick; join the other team |
| Playing another mode | Spectate; Ready |
| Spectating another mode | Join game |

Above them a band in the team's color (#6AA42B Marine, #FF7B04 Strogg,
#999999 for spectators, #8B964B elsewhere) names the team with its score and
both teams' sizes; in deathmatch it gives the player's score and place. The
last three chat lines close the page.

An action the game cannot take now stays in place, dimmed, with a lock after
its label and the reason under it in #E46D56: a team the balance rule
refuses or the player is already on (the stock "too many players" and
"already on" messages), spectating a server that does not allow it, and Ready
outside a warm-up that uses it. Choosing one shakes it for 300 ms and pulses
its reason, and nothing else happens. An available action records its slot
and runs `mpTeamAction`; the game derives the slot's action again from the
player's state, refuses it if it is no longer available, and otherwise joins,
spectates or readies and closes the menu, as the stock buttons do.

### The Players page

The team lists stand beside the selected player's statistics. Each list opens
with a band in its team's color (#6AA42B Marine, #FF7B04 Strogg, #999999 for
spectators, #8B964B for everyone outside team modes) holding the title and the
team's score, then lists its players in the scoreboard's rows (section 14.14):
a band at 0.08, or 0.29 with the marker for the player's own row; the speaker,
crossed in red when the player is muted; the friend silhouette, 0.125 when the
player is not a friend; the name, the score and the ping. The name, score and
ping headings run once above the lists. The player's own team comes first
(Marines while spectating), then the other team, then the spectators, whose
band shows only while there are any. Each row is 24 dp and shrinks with the
others, down to 14 dp, to share what the bands leave, so sixteen players and
three bands fit the page; the generator fails if they would not.

A list keeps its order while the menu stays open and sorts again by score only
when the menu opens or the list's players change, so a row never moves under
the cursor while scores change. The page opens on the player's own row and
statistics. Choosing a row shows that player's statistics and lights the row in
olive: their name in a band in their team's color; kills, deaths and score;
accuracy for the machinegun through the napalm launcher, each icon in its
weapon color code (Appendix B.4) and dimmed until the weapon has fired; and the
awards' medals with their counts, dimmed until earned, with Capture, Assist and
Defense only in flag modes. Medals stay bitmaps, and the document's pictures
load with it inside the level load. A remote client asks the server for
statistics older than five seconds, one request at a time, as the stock page
does, and shows "-" until the answer arrives.

Mute and Friend close the page, in-game plates labelled as the stock page
labels them (MUTE PLAYER or UNMUTE PLAYER, ADD FRIEND or REMOVE FRIEND). On the
player's own row both are unavailable, dimmed with their lock and reason, and
shake when chosen. Muting is the stock mute, which also tells the server.
There is no friends service on PC (the engine's is empty), so a friend is the
player's own mark, shown in the lists and on the scoreboard while the map runs;
the stock page's Friend button keeps the same mark now.

### The Server page

The server's name and address, its message (`si_motd`, three lines) in
#FFFF8D, the rules in two columns (mode, map, limits, players, friendly fire,
team balance and the next map in `si_mapCycle`) and the map rotation, the
current map in orange. Each column's labels take the width of the longest in
any language. The page has no actions; its tab keeps the focus.

### The game's data

The game publishes everything the card shows through one cache, writing a key
only when it changes and moving `mp.revision` when anything did:

- the header: `mp.title`, `mp.mode`, `mp.clock`, `mp.score`;
- the Team page: `mp.team.band`, `mp.team.band_color`, `mp.team.band_score`,
  `mp.team.band_detail`, `mp.action<0-2>.{shown,available,label,reason,detail}`
  and `mp.chat<0-2>`;
- the Server page: `mp.server.{name,address,message}`, `mp.rule<0-6>`,
  `mp.rotation<0-15>`, `mp.rotation_count` and `mp.rotation_current`;
- the Players page: per list (`a` the player's own team or everyone, `b` the
  other team, `s` the spectators) `mp.players.<list>.{shown,title,color,score,count}`
  and sixteen rows `mp.players.<list><0-15>.{client,name,score,ping,local,friend,muted}`;
  the statistics `mp.stat.{client,name,color,kills,deaths,score,flag_mode}`,
  `mp.stat.acc<0-9>` and `mp.stat.award<0-7>`; and Mute and Friend as
  `mp.mute.*` and `mp.friend.*`, shaped like the Team page's actions.

Player and server text (player names, the server's name and message, the
chat) is cleaned as the loading screen's server card cleans it: colour codes,
controls and malformed UTF-8 dropped, its lines and bytes bounded, and a
leading `#str_` broken so a name never translates.

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
| `mpTeamAction` | `play main_menu_selection ; retained team <slot>`, by `card.team_action` |
| `mpSelectPlayer` | `play main_menu_selection ; retained select <client>`, by `card.client` |
| `mpMute` | `play main_menu_selection ; retained mute <client>`, by `card.client` |
| `mpFriend` | `play main_menu_selection ; retained friend <client>`, by `card.client` |

A row records its player's client number before it asks, and Mute and Friend
record the selected player's. The session refuses a client outside the
server's slots; the game acts only on a client with a row now, never mutes or
befriends the player's own row, and none of the three closes the menu.

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
- **Players page.** Rows run 14 to 24 dp, tighter than the held scoreboard,
  so sixteen players fit beside the statistics without scrolling; the lists
  hold their order while the menu stays open; Mute and Friend refuse the
  player's own row; and Friend is the player's own mark, since PC has no
  friends service.

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

The Team and Server pages add:

- gate cases for `mpTeamAction`: the slot the card records reaches the game as
  `retained team <slot>`, the menu closes when the game acts and stays open
  when it refuses, and slots outside the three are refused; pins that the
  game derives the slot's action again before acting and closes the menu
  after it, and that the session, the game and the document agree on three
  slots;
- native checks of the Team page (the band's color, an available action with
  its detail, an unavailable one dimmed with its lock and reason, an empty
  slot hidden, the action an available slot asks for, the shake instead for
  an unavailable one) and the Server page (the rotation's current map in
  orange, only the rotation's maps shown, the message above the rules, the
  tab keeping the focus);
- a generator check that every action label, with each team's name, fits its
  plate in every language;
- a live probe on a Team DM listen server with a server message and a map
  cycle: the band and the actions as a team player, the balance rule
  refusing a switch with its reason, Ready during the warm-up, Spectate
  taken through the game and closing the menu, the spectator's two join
  actions, a join closing the menu again, and the Server page's message,
  rules, next map and rotation.

Evidence: `.tmp/ui/retained-mp-team-server/validation-evidence.json`, SHA-256
`470d27af66c563373136d5db16f862eb0d3f1c935e3b1dfe6609896f18b56fb3`.

The Players page adds:

- gate cases for `mpSelectPlayer`, `mpMute` and `mpFriend`: the client the
  card records reaches the game as `retained select|mute|friend <client>`
  without closing the menu, and a client outside the server's slots is
  refused; pins that the game acts only on a listed client, never mutes or
  befriends the player's own row and keeps the menu open, that the game and
  the document agree on the lists, rows, weapons and awards, and that the
  stock Friend button keeps the same mark;
- native checks of the page: each list's rows and band color, the player's
  own row brighter and marked, the selected player lit, muted and friend
  symbols, the statistics beside the lists, the widest pitch for a few
  players, sixteen players sharing what the bands leave, rows holding 14 dp
  past sixteen, an idle weapon and an unearned award dimmed, flag awards only in flag modes, the statistics in
  the player's team color, Mute refusing the player's own row with its
  reason, a row asking for its player, and Mute and Friend asking for the
  selected one; arriving on the page focuses the selected player's row;
- generator checks that Mute and Friend in either form, their reasons and the
  statistics headings fit in every language, and that sixteen players and
  three bands fit the page;
- live probes with bots on listen servers: Team DM in English, CTF in
  Hungarian and DM in German on Vulkan (the lists, the statistics with
  accuracy and awards, selecting a bot, muting and befriending it and taking
  both back, the selection back on the player when the menu reopens), the
  spectators' band during a warm-up, and a second client over loopback whose
  statistics come from the server.

Evidence: `.tmp/ui/retained-mp-players/validation-evidence.json`, SHA-256
`6ef9ecdea0cd0d453a3485185bdffa0562cd091d703969aa96244f2febccefb6`.

The card's acceptance continues under `FLOW-046`.

## Known limitations

- Five pages hand off to their stock pages, and the stock menu then keeps the
  menu until it closes; the card does not come back over it.
- Choosing an unavailable action does not announce its reason to the
  accessibility text backing yet, and a controller gives no rumble.
- The Team page has no Tourney queue or arena controls; Tourney offers what
  deathmatch does.
- The stock team-refusal messages are English in French and Italian, whose
  tables lack them.
- Voice chat does not work yet (capture and playback are off), so Mute records
  the choice and tells the server without anything to silence.
- Mute and friend marks belong to a client slot, as the stock page's do: a
  player who takes a departed player's slot inherits them until the map
  changes.
- The lists have no BOT tag, dead-player mark or network-quality bars (the
  remastered scoreboard's additions), and the rows' pitch never scrolls: a
  server past sixteen clients clips the last rows.
- Left and right move focus between the lists and the statistics; they do not
  switch tabs as section 14.18 asks (decision D2 is open).
- There is no Welcome card: the connect-time join offer keeps the stock join
  card.
- The prompt bar shows keyboard keycaps only; controller glyphs wait for the
  glyph families (`INP-011`).
- Narrower views than 4:3 (5:4, portrait) do not scale the card down yet
  (`LAY-021`).
- The multiplayer smokes that capture stock pages do not pin `ui_retained 0`;
  they need to once the card joins the default.
