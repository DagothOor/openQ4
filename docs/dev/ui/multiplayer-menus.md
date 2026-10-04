# Retained multiplayer menus

The retained multiplayer menus replace the stock full-screen multiplayer menu
with one card over the live, softened match (section 14.18 of the
[visual specification](../ui-visual-design.md), requirement `FLOW-046`). The
Escape card's shell came first: the card, its header, the eight-tab strip, the
prompt bar, the Disconnect confirmation, the softening and its release, and the
session and game plumbing that let the card cover the game's own menu. The
Team, Players, Vote, Settings, Voice and Server pages are built on it; Match
and Admin still hand off to their stock pages, so the Escape card stays
opt-in. The Welcome card covers the connect-time join offer with its Join,
Server, Players and Settings pages, all built, so it presents by default.
Match follows in a later increment (the plan's B9); Admin waits for text
fields, and its stock page's password check now works (B7).

## The gate

`ui_retainedMultiplayer` (default 0) opts into both cards. `ui_retained` alone
includes a card only once none of its pages hands off any more: the session
lists the pages that still do in `RETAINED_MP_ESCAPE_MISSING_PAGES`, today
Match and Admin, and `RETAINED_MP_WELCOME_MISSING_PAGES`, now empty, and
`tools/tests/ui_retained_gate.py` keeps each list equal to its document's
hand-off pages (its `stock_<page>` programs). The Welcome card therefore
presents with `ui_retained` alone, which is on by default; `ui_retained 0`
keeps the classic join panel. A page that is built may still hand off what it
cannot edit yet (`classic_<page>`, the Settings page's name and clan) without
counting as missing. Players never see a mix of card and stock pages unless
they opt in.

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
- the game names the card (`retainedMultiplayerVariant`): Welcome while the
  player has not answered the join offer (the offer stands, or `ui_joined` is
  still 0 while a player without `ui_autoJoin` spectates; a player with
  `ui_autoJoin` never sees the offer), Escape otherwise; and that card's gate
  is on;
- the game answers `retainedMultiplayerCover` with the protocol the session
  expects (`mp.protocol` 1) and allows the cover now (`mp.cover_allowed`). It
  refuses in an Arena Campaign match, which keeps its own menu. Over the join
  offer the card's softening replaces the join panel's blur, which comes back
  if the stock menu takes the offer over.

Otherwise the stock menu presents. Like the other retained screens, the card
falls back to the stock menu for the session when its document is not
installed (quietly), cannot load (one warning) or stops drawing (one warning),
when a mod supplies its own `guis/mpmain.gui`, and when the game module does
not answer the protocol, as an older or a mod's game module would not. A
game module that does not name the card gets Escape, which its join offer
refuses. Whatever keeps the stock menu keeps it only for that opening; the
next asks the game again.

Each frame the session asks the game for the card's state
(`retainedMultiplayerState`). The game writes only the keys that changed and a
new `mp.revision`, and the session publishes the card only when the revision
moves. Closing the menu, opening the main menu, or anything else that takes the
screen retires the card (`retainedMultiplayerUncover`); the game then draws its
menu again. A map change retires it without a release and opens the next
map's card on its first page; the document itself loads inside each
multiplayer level load.

`ui_retainedStatus` reports each card's gate as `multiplayer=` (Escape) and
`welcome=`, and the covering card as `mp=escape` or `mp=welcome` (`mp=-`
otherwise); `openq4_retainedGui` addresses the card while it covers.

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

### The Vote page

The running vote comes first, beside the call a player can make:

- **The running vote.** Who called it ("CALLED BY" and the player), what it
  changes, one line each in the stock vote menu's words and order (up to
  six), the time left in the value color and the tally, then Vote Yes and
  Vote No, each with the key bound to it (F1 and F2 by default). On a remote
  client the time left counts the vote's 30 seconds (20 for a console vote)
  from when the vote reached it. Once the player has voted, both ballots lock
  and say so; spectators and a managed match get their own reasons. A ballot
  closes the menu, as the stock buttons do. With no vote running the column
  says so.
- **The call.** NEW VOTE lists the fields the drafted game type uses, one
  setting row each: the map and the game type, each a list that unfolds under
  its row; the time limit and the mode's own limit (frags, captures, the
  tournament's rounds or the Dead Zone's control time), each a slider that
  Left and Right step (Page Up and Page Down by ten); team balance and
  shuffle in team modes, restart, and buying where the mode has a buy menu,
  each a check box; and the player to kick, a list that leads with "No one".
  At most nine rows show. A field the server forbids (`si_voteFlags`) stays,
  dimmed with a padlock after its label, and the heading says it is locked by
  the server. Call Vote follows, unavailable with its reason while voting is
  off on the server, in a managed match (whose votes are Match Control
  proposals), for a spectator, while a vote runs, or until something differs
  from the server's settings.

The call is the game's: each opening of the menu drafts it again from the
server's settings, and a row's control asks the game to change one field.
The game checks every value against its field's rules (a map the drafted
game type plays, a game type the vote offers, a limit inside its setting's
range, a player on the server), so the row shows only what the game accepts.
Changing the game type lists only the maps it plays; a drafted map it cannot
play gives way to the first that can. Call Vote sends only the fields that
differ from the server's, since the server refuses a whole vote for one
unchanged field. The page opens on Vote Yes while the player can vote, and on
its first row otherwise.

### The Settings page

The player's appearance, the other players' and the way to the rest of the
settings:

- **Player.** The name and the clan tag, each a row that hands off to the
  classic Settings page, since the card has no text fields yet; the model, a
  list of the models the mode and the player's team allow; the rail color,
  the seven stock swatches, the one the player's tint matches by hue standing
  taller; and the handicap, a slider from 1 to 100.
- **Controls, Game Options and System.** Plates that leave for the main
  menu's pages, as the classic page's buttons do (decision D13).
- **Opponents and teammates.** A table: the model forced on them (Off or a
  model), their outline, rim light and brightskin (Off, Low, Medium or High),
  the effect and brightskin colors (eight each), then the outline's width for
  both. The teammates' column shows only in team modes; elsewhere a note says
  why. Each list holds the classic page's own values.

The model lists and the swatches belong to the game, which builds the lists as
the classic page does and sets the model for a row (`retained appearance
<slot> <row>`) or the tint for a swatch (`retained rail <row>`). The other
rows set their settings through the adapter's `settings.player.set` and read
them back from the settings themselves. The page opens on the name.

### The Voice page

Send Voice, Receive Voice and Voice Echo as check boxes, the receive volume
(0 to 1) and the microphone's input volume (0 to 10) as sliders; then the key
bound to push to talk ("Not bound" when there is none) with Controls to
rebind it, and the microphone's level and Test Microphone, unavailable with
the reason "Voice chat is not available." while voice chat does not work.

### The Welcome card

The Welcome card covers the menu the game opens when a player joins without
`ui_autoJoin`, and the menu key opens it again until the player answers: Esc
(Spectate on the prompt bar) closes it and leaves the player spectating, while
joining a team, the game or the tournament, or choosing Spectate on the page,
answers the offer, and the menu key opens Escape from then on. The header holds
the server's welcome ("WELCOME TO" and its name) and the player count; the
prompt bar has Spectate, Tabs and Select, then Main Menu and Leave Server,
which asks first in the stock confirmation.

- **Join.** The mode and map, then the match state, the time left in the value
  color, the limit and the player count. Team modes show the two team cards,
  each the plate that joins its team: the header band in the team's color with
  its name and score, its player count and, in CTF, its flag's state (at
  base, taken or dropped). A team the stock balance rule refuses dims with its
  lock and reason and shakes when chosen. Auto join follows, focused, naming
  the team it picks, then Spectate. Deathmatch shows the three leaders with
  their scores, then Join game, focused, and Spectate; Tourney shows the arenas
  in play with their scores and joining or leaving the tournament.
- **Server.** The Escape card's Server page.
- **Players.** The Escape card's lists, the speaker and friend symbols, score
  and ping, spectators below, with nothing to choose: its tab keeps the focus.
- **Settings.** The name, clan, model and rail color rows of the Escape
  card's Settings page, then the crosshair: a slider through the stock
  picker's twenty crosshairs, 0 for each weapon's own ("By weapon"), the
  chosen one shown beside it (`retained crosshair <index>`). Controls, Game
  Options and System follow, standing for All settings.

The game publishes the Welcome card's keys with the rest: `mp.welcome.title`,
`mp.welcome.players`, `mp.welcome.match`, `mp.welcome.state`,
`mp.welcome.limit`, `mp.welcome.team_mode`, `mp.welcome.team<0-1>.{score,count,flag}`,
`mp.welcome.leader<0-2>.{name,score}`, `mp.welcome.arena<0-3>` and
`mp.welcome.arena_count`, and the Join page's four actions as
`mp.join<0-3>.{shown,available,label,reason,detail}`, which the game derives
again when one is chosen.

### The Server page

The server's name and address, its message (`si_motd`, three lines) in
#FFFF8D, the rules in two columns (mode, map, limits, players, friendly fire,
team balance and the next map in `si_mapCycle`) and the map rotation, the
current map in orange. Each column's labels take the width of the longest in
any language. The page has no actions; its tab keeps the focus.

### The Admin page

The Admin page hands off to the stock page until the card has text fields for
the password and the console. The stock page asks for the server's
remote-console password and sends `rcon verifyRconPass` when the player
chooses Accept, then waits for the game to hear the answer
(`idGame::ProcessRconReturn`), which opens the admin controls or returns to
Join Team. Quake 4's engine answered that check; openQ4's ran it as an unknown
command and never passed an answer on, so the page waited for good. Now:

- the server answers the check with the stock "rcon verified" string
  (`#str_107250`) without running anything, once the password is accepted
  (`idAsyncServer::ExecuteRemoteConsoleCommand`, rcon2 and legacy alike);
- the client hands that answer, or the bad-password reply (`#str_04847`, or
  Quake 4's `#str_104847`), to the game when it comes from the server the
  check went to, and answers false itself on the next frame when it refuses
  the check before sending (no password, one shorter than rcon2's 12 bytes,
  no port or address) or after rcon2's 10-second request timeout
  (`idAsyncClient::AnswerRconVerify`);
- the client hands the server's remote-console output to the game, as Quake 4
  did, so the stock page's console shows it.

The stock field takes 16 characters; a longer password set at the console
works when the player chooses Accept without typing in the field.
`tools/tests/async_rcon_verify_contract.py` compiles the client and server
code with stand-ins and drives both ends; `--mutations` reverts each rule.

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
  `mp.mute.*` and `mp.friend.*`, shaped like the Team page's actions;
- the Vote page: the running vote as `mp.vote.{running,caller,time,tally}`,
  `mp.vote.line<0-5>` and `mp.vote.line_count`, the ballots as
  `mp.vote.yes.*` and `mp.vote.no.*`, Call Vote as `mp.vote.call.*` (shaped
  like the Team page's actions); and the draft, each field's value as
  `mp.vote.<field>` with `mp.vote.<field>.{row_shown,row_allowed}`, the lists
  as `mp.vote.{map,gametype,kick}<row>` with their counts
  `mp.vote.{map,gametype,kick}_count` (the kick count includes "No one"),
  and `mp.vote.locked`.

- the Settings pages: `mp.settings.{name,clan,rail}`, each model list as
  `mp.model<slot>.<row>` with `mp.model<slot>_count`, the row it holds as
  `mp.model<slot>` and `mp.model<slot>.row_shown` (slot 2, the teammates', in
  team modes only), and the crosshair as `mp.crosshair`,
  `mp.crosshair_count` and `mp.crosshair_image`.

The session writes the names of the keys bound to the ballots and to push to
talk, `mp.keys.vote_yes`, `mp.keys.vote_no` and `mp.keys.voice_chat` with
their `_bound` flags, when the card opens: the engine's key lists name keys by
number, which only the stock GUIs draw. The pages read the player settings
they change from the settings themselves (`cvar.<name>` state, the lists' as
text).

Player and server text (player names, the server's name and message, the
chat) is cleaned as the loading screen's server card cleans it: colour codes,
controls and malformed UTF-8 dropped, its lines and bytes bounded, and a
leading `#str_` broken so a name never translates.

### Width

The specified 648 dp cannot hold eight tabs: with the active tab's flare and
shoulder each tab needs its label plus 31 dp, and even the shortest English
labels need about 800 dp at 14 dp, so the Escape card grows to the widest
language's fitted strip. Neither card's prompt bar fits the specified widths
either. `tools/ui/retained_mp_menus.py` measures every language's labels in
the shipped faces and sizes each card to the wider of its widest tab strip
(plus a 2 % margin) and its widest prompt bar (plus 4 dp) inside the card's
insets: today Escape is 907 dp and Welcome 873 dp, both set by the Spanish,
German and Ukrainian prompt bars. The build fails if a language would need
more than a 4:3 view allows (928 dp, 16 dp from each side). Each tab is as
wide as its label in the running language, and the tabs share the remainder.
The Welcome card keeps Escape's 477 dp height instead of its specified 402 dp,
since its Players and Server pages need the room.

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
| `mpWelcomeAction` | `play main_menu_selection ; retained welcome <slot>`, by `card.welcome_action` |
| `mpVoteYes`, `mpVoteNo` | `play main_menu_selection ; retained vote yes\|no` |
| `mpCallVote` | `play main_menu_selection ; retained callVote` |
| `mpRail` | `play main_menu_selection ; retained rail <row>`, by `card.rail` |
| `mpSettingsControls`, `mpSettingsGame`, `mpSettingsSystem` | `play main_menu_selection ; mainMenu fromMp_toControls\|fromMp_toGameoptions\|fromMp_toSystem` |

The Vote page's rows are value controls. Their actions use the adapter's
`session.menuValue` operation, which carries the control's new value with a
verb: `mpVoteMap`, `mpVoteGameType`, `mpVoteTimeLimit`, `mpVoteFragLimit`,
`mpVoteCaptureLimit`, `mpVoteTourneyLimit`, `mpVoteControlTime`,
`mpVoteBalance`, `mpVoteShuffle`, `mpVoteRestart`, `mpVoteBuying` and
`mpVoteKick`. The adapter accepts only these verbs, with a whole number from
-1 to 999 or a Boolean, and queues `<verb> <value>`; the session maps the
verb to its field (`RETAINED_MP_VOTE_FIELDS`, in the game's field order) and
sends `retained voteSet <field> <value>` without a sound, keeping the menu
open. A list sends its row (the kick list's "No one" is -1), a check box 1 or
0, a slider its value. The Settings pages' model lists and crosshair use the
same operation with `mpModelSelf`, `mpModelEnemy`, `mpModelTeam` and
`mpCrosshair` (`RETAINED_MP_APPEARANCE_VALUES`): the session sends `retained
appearance <slot> <row>` or `retained crosshair <index>` for a value of 0 or
more.

The other settings rows use the adapter's `settings.player.set` operation, a
literal setting with the control's value. The adapter allows only the
player settings these pages change, each with what its classic control
offers: the handicap's whole numbers from 1 to 100, the voice volumes' ranges,
the voice switches' Booleans, and each appearance list's own values (`0`,
`0.35`, `0.7` and `1` for the strengths, the eight stock colors, `1.0` to
`6.0` for the outline's width), which it compares as text.

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
- **Welcome (D10).** Welcome while `ui_joined` is 0 and the player spectates,
  or while the join offer stands; it re-offers after every map change, as the
  join card did.
- **Card sizes.** Each card fits its widest prompt bar; Welcome takes
  Escape's height (above).
- **Settings pages.** Opponents and teammates share one table rather than
  the classic page's tabs; labels take two lines at 14 dp, so the values
  keep their room in every language; the model lists hold 24 rows (the stock
  game has 18 models); the crosshair is a slider, not a picker with arrows;
  Welcome's All settings is Controls, Game Options and System, since the
  main menu has no settings landing to open; and name, clan and push to
  talk hand off until text and key binding fields exist.
- **Vote page.** The rows are the runtime's value controls: lists for the
  map, game type and kick, check boxes for balance, shuffle, restart and
  buying, sliders for the limits (time 0 to 60 minutes, frags 0 to 100,
  captures 1 to 50, tournament rounds 1 to 20, control time 10 to 600 seconds
  in tens; a server's setting outside a slider shows as it is until changed).
  Rows show only for the fields the drafted game type uses. The ballots and
  Call Vote close the menu, as the stock buttons do; the rows keep it open.
  The heading of the call reads NEW VOTE, so it never repeats the button.
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

The Welcome card adds:

- gate cases: the game naming the card for each opening, the Welcome card
  covering and latching its variant, `mpWelcomeAction` reaching the game as
  `retained welcome <slot>` and closing the menu when the game acts, slots
  outside the four refused, the Settings hand-off pressing the join panel's
  button while the offer stands and the menu column's afterwards, the Join
  page having no stock page, Escape again once the player answers, each
  card's own gate, and fallbacks holding for the opening; pins for the game's
  variant rule, the cover allowing the join offer and dropping its blur, the
  action runner closing the menu, both cards' missing pages and stock
  buttons, and four Join slots in the session, the game and the document;
- native checks of the card: centered at Escape's height inside a 4:3 view,
  Auto join focused, the team cards side by side, a refused card dimmed with
  its lock and reason and shaking instead of asking, an open card and Auto
  join asking with their slots, deathmatch's ranked leaders with Join game
  focused, Tourney's arenas, the Players rows without choices, the Settings
  hand-off, Back, Leave Server asking first and the prompt bar inside the
  card;
- the generator fitting each card to its widest tab strip and prompt bar in
  every language, and a gate audit that measures each card's prompt bar again
  from the generated document (the native test's host cannot see real text
  widths);
- live probes with bots and `ui_autoJoin 0`: Team DM in English (the join
  offer opening Welcome, a balance refusal, Back, the menu key opening
  Welcome again, Auto join, then Escape), DM in German on Vulkan, Tourney in
  French with the Settings hand-off after Back, and CTF with its flag states
  and the hand-off during the offer.

Evidence: `.tmp/ui/retained-mp-welcome/validation-evidence.json`, SHA-256
`1620a52f64b2971dabf170c00bbe91d50b1041ccdbad74a66e67feaa503d0887`.

The Vote page adds:

- gate cases: a row's request reaching the game quietly as
  `retained voteSet <field> <value>` with the menu open, the ballots and Call
  Vote closing it when the game acts, and malformed, unknown, prefixed and
  out-of-range requests refused; the keys bound to the ballots reaching the
  card by name when it opens, and an unnamed key left out; pins that the
  adapter's value verbs, the session's field table, the game's field order,
  its publisher and the document's rows agree, that the game casts a ballot
  only while the player can, checks each field without closing the menu,
  calls only the fields that differ and closes the menu after, and drafts the
  call again at each opening; and that the Vote page no longer hands off;
- adapter checks that a value verb carries a whole number from -1 to 999 or a
  Boolean, and only the Vote page's verbs may carry one;
- native checks of the page: no vote running and no ballots, the first row
  focused, the rows the drafted game type uses stacked above Call Vote, a
  locked row dimmed with its padlock and out of reach, Call Vote waiting with
  its reason, a slider, a check box and both lists requesting their verbs
  with the new values, the running vote's caller, lines, time left and tally,
  Vote Yes focused with the keys shown, the ballots locking once the player
  has voted, and the page out of reach from another tab;
- generator checks that every row label, ballot, reason, heading and running
  vote line fits in every language, and the stock maps' long names in the
  collapsed lists;
- live probes: a host and a remote client over loopback (Team DM, English on
  OpenGL and German on Vulkan) where the host steps the time limit up five
  minutes and calls the vote, the client sees the caller, the line, the time
  left and the tally, votes yes through the card and the vote passes; and a
  listen server drafting a CTF call from Team DM (the map giving way to a CTF
  map and the capture limit replacing the frag limit, the kick list with the
  bots), in Polish on Vulkan while spectating with two fields locked by the
  server, and in Russian with voting off and a Tourney draft.

Evidence: `.tmp/ui/retained-mp-vote/validation-evidence.json`, SHA-256
`c43517ab3160ddb9ff865380dc2a83374597aa5b0bb5d4f0daf575d3b0d08aa2`.

The Settings and Voice pages add:

- gate cases: a model list's row and the crosshair reaching the game quietly
  as `retained appearance <slot> <row>` and `retained crosshair <index>`, a
  swatch as `retained rail <row>`, a negative row and a swatch outside the
  seven refused, Controls, Game Options and System opening the main menu's
  pages, the push-to-talk key reaching the card by name, and a multiplayer
  level loading each card whose pages are all built; pins for the Welcome
  card's empty missing pages, Welcome only for players without
  `ui_autoJoin`, the Settings hand-off for name and clan, the model lists,
  swatches and appearance values agreeing between the game, the session, the
  adapter and the document, and the appearance commands keeping the menu
  open;
- adapter checks that a player setting takes only its classic control's
  values (whole numbers, ranges, Booleans, the lists' own text) and that no
  other setting may be set;
- native checks of the pages: the Escape card's Settings page opening on the
  name, its rows stacking above the plates, name and clan handing off, the
  chosen swatch standing taller and a swatch asking for its color, the
  handicap and an outline setting their settings, a teammate model asking for
  its row, the teammates' column only in team modes with the note otherwise,
  and System leaving for the main menu; the Voice page's switch and volume,
  its push-to-talk key or "Not bound", and its unavailable test; Welcome's
  Settings page and its crosshair slider and preview;
- generator checks that every label fits in two lines and every list value
  in its cell, in every language;
- live probes on listen servers with bots and `ui_autoJoin 0`: in English on
  OpenGL without the opt-in, the Welcome card presenting by default (its
  crosshair, swatch and model list), then the stock in-match menu; and in
  German on Vulkan with the opt-in, Welcome's Settings, then the Escape
  card's Settings page setting an outline and the handicap, and its Voice
  page.

Evidence: `.tmp/ui/retained-mp-settings/validation-evidence.json`, SHA-256
`ef740505998f2b64c757928e2c62e08fd34dda5a735a1645c369e9d817e83f8a`.

The card's acceptance continues under `FLOW-046`.

## Known limitations

- Match and Admin hand off to their stock pages, and the stock menu then
  keeps the menu until it closes; the card does not come back over it. So do
  the Settings pages' name and clan.
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
- The Welcome card's Join page has no Watch for Tourney's arenas and no
  place in the queue (neither has a model yet), and its team cards carry no
  faction mark.
- The Settings pages have no model preview (retained documents have no 3D
  view) and no text fields: name and clan open the classic page.
- The Voice page's settings take effect, but voice chat itself does not work
  yet, so its meter and test are unavailable.
- The crosshair slider runs to twenty, the stock list; a mod's longer list
  is reached only by the classic picker.
- On a remote client a running vote's time left counts from when the vote
  reached it, so it can read a little long; no message carries the server's.
- The kick list names its rows, and the game reads the row at the moment of
  the choice: a player leaving in that instant can shift the rows. The row
  then shows whom the call would kick before Call Vote sends it.
- The map list holds 48 maps; a server with more for one game type lists the
  first 48.
- Lists and check boxes take Left and Right as focus moves and change only on
  accept; sliders step with them (decision D2 is open). A list's value shows
  one frame after the game accepts it.
- A managed match's refusals on the Vote page have no live probe yet.
- The prompt bar shows keyboard keycaps only; controller glyphs wait for the
  glyph families (`INP-011`).
- Narrower views than 4:3 (5:4, portrait) do not scale the card down yet
  (`LAY-021`).
- The multiplayer smokes join with `ui_autoJoin 1`, so they never see the
  Welcome card; the smokes that capture stock in-match pages need to pin
  `ui_retained 0` once the Escape card joins the default.
