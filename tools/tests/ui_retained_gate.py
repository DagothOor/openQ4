#!/usr/bin/env python3
"""The ui_retained gate: no retained (RmlUi) screen is reachable while it is 0.

Compiles the production retained-screen session code (title and pause home
screens, hand-offs, session verbs, loading selection and the status report)
against counted engine/UI doubles, and checks the source contracts that keep
the gate complete:

* ui_retained defaults to 0 and is not archived; ui_retainedSystem alone
  opts into only the SYSTEM page, and ui_retained includes it;
* every retained document path in the session is reached only behind the gate;
* the retained documents request only session verbs the adapter allowlists
  and the session handles, and they are up to date with their generator;
* no game or legacy content names a retained document.

Renderer output, physical input and in-game presentation are qualified by the
engine captures in docs/dev/ui/retained-screens.md, not by this test.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from filesystem_case_segments import function_body

ROOT = Path(__file__).resolve().parents[2]

SUPPORT = r'''
#include <cassert>
#include <cctype>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <map>
#include <memory>
#include <string>
#include <vector>
static int checks = 0;
#define CHECK(x) do { ++checks; if (!(x)) { std::fprintf(stderr, "check failed line %d: %s\n", __LINE__, #x); std::abort(); } } while (false)
#define ID_TIME_T long long
struct idStr : std::string {
    using std::string::string;
    idStr() = default;
    idStr(const std::string& value) : std::string(value) {}
    idStr& operator=(const char* value) { assign(value); return *this; }
    int Length() const { return static_cast<int>(size()); }
    static int Icmp(const char* a, const char* b) {
        while (*a && *b && std::tolower(*a) == std::tolower(*b)) { ++a; ++b; }
        return std::tolower(*a) - std::tolower(*b);
    }
};
template<typename T> struct idList : std::vector<T> { int Num() const { return static_cast<int>(this->size()); } void Append(const T& v) { this->push_back(v); } };
using idStrList = idList<idStr>;
struct fileTIME_T { int index; ID_TIME_T timeStamp; };
struct Common {
    std::string output; std::vector<std::string> warnings; int time = 1000, quits = 0;
    int GetPresentationTime() const { return time; }
    void Printf(const char* fmt, ...) { char text[2048]; va_list args; va_start(args, fmt); std::vsnprintf(text, sizeof(text), fmt, args); va_end(args); output += text; }
    void Warning(const char* fmt, ...) { char text[2048]; va_list args; va_start(args, fmt); std::vsnprintf(text, sizeof(text), fmt, args); va_end(args); warnings.push_back(text); }
    void Quit() { ++quits; }
} commonObject, *common = &commonObject;
struct CVar { bool value = false; bool GetBool() const { return value; } } ui_retained, ui_retainedSystem;
enum { SE_NONE = 0, CMD_EXEC_APPEND = 1 };
struct sysEvent_t { int evType = SE_NONE; };
struct idUserInterface {
    std::string source; bool active = false; int activations = 0, deactivations = 0;
    std::vector<std::string> named; std::map<std::string, std::string> state;
    explicit idUserInterface(const char* name) : source(name) {}
    const char* Name() const { return source.c_str(); }
    const char* Activate(bool value, int) { active = value; ++(value ? activations : deactivations); return ""; }
    void HandleNamedEvent(const char* name) { named.push_back(name); }
    const char* HandleEvent(const sysEvent_t*, int) { return ""; }
    void SetStateBool(const char* key, bool value) { state[key] = value ? "1" : "0"; }
    void SetStateString(const char* key, const char* value) { state[key] = value; }
    void SetStateFloat(const char* key, float value) { state[key] = std::to_string(value); }
    float cursorX = 320, cursorY = 240;
    float CursorX() { return cursorX; }
    float CursorY() { return cursorY; }
    void StateChanged(int) {}
};
struct idMath {
    static float ClampFloat(float low, float high, float value) { return value < low ? low : value > high ? high : value; }
    static float Fabs(float value) { return value < 0 ? -value : value; }
};
struct Manager {
    std::vector<std::unique_ptr<idUserInterface>> storage; std::vector<std::string> loads; bool fail = false;
    struct Flags { bool autoLoad, unique, shared; }; std::vector<Flags> flags;
    idUserInterface* FindGui(const char* path, bool autoLoad, bool unique, bool shared) {
        loads.push_back(path); flags.push_back({autoLoad, unique, shared});
        if (fail) return nullptr;
        storage.push_back(std::make_unique<idUserInterface>(path)); return storage.back().get();
    }
} managerObject, *uiManager = &managerObject;
struct CommandSystem { std::vector<std::string> buffered; void BufferCommandText(int, const char* text) { buffered.push_back(text); } } commands, *cmdSystem = &commands;
// The legacy main menu's desktop variables, as presentation queries read them.
static std::map<std::string, int> legacy;
static bool MainMenuWindowStateIsNonZero(idUserInterface*, const char* name) { return legacy[name] != 0; }
static bool MainMenuWindowStateEqualsInt(idUserInterface*, const char* name, int value) { return legacy[name] == value; }
static bool preview = false;
static bool RetainedUI_IsOpen() { return preview; }
static int RetainedUI_ViewCount() { return static_cast<int>(managerObject.storage.size()); }
static std::vector<std::string> legacyActions;
static bool legacyActionAvailable = true;
static bool UI_RunLegacyWindowAction(idUserInterface*, const char* window, bool back, idStr& command) {
    CHECK(!back); legacyActions.push_back(window); command = "play main_menu_selection"; return legacyActionAvailable;
}
static bool UI_RetainedImageSource(const char* source) { return source && !std::strstr(source, ".."); }
static std::vector<std::string> precached;
static void UI_RetainedPrecacheImage(const char* source) { precached.push_back(source); }
static const char* Sys_TimeStampToStr(ID_TIME_T) { return "29 Sep 2026 12:40"; }
struct sessionMenuSaveDescription_t { idStr saveName, description, screenshot; bool noOverwrite = false; };
static bool Session_MenuReadSaveDescription(const idStr& slot, sessionMenuSaveDescription_t& out) {
    out.saveName = slot; out.description = "Air Defense Bunker"; out.screenshot = "savegames/quick.tga"; return true;
}
static const char* va(const char* fmt, ...) {
    static char text[1024]; va_list args; va_start(args, fmt); std::vsnprintf(text, sizeof(text), fmt, args); va_end(args); return text;
}
static bool Session_RetainedScreensEnabled() { return ui_retained.GetBool(); }
static bool Session_RetainedSystemEnabled() { return Session_RetainedScreensEnabled() || ui_retainedSystem.GetBool(); }
class idSessionLocal {
public:
    idUserInterface *guiActive = nullptr, *guiMainMenu = nullptr, *guiTest = nullptr;
    idUserInterface *guiRetainedHome = nullptr, *guiRetainedTitle = nullptr, *guiRetainedPause = nullptr;
    bool retainedHomeReturning = false, retainedTitleFailed = false, retainedPauseFailed = false, retainedLoadingFailed = false;
    int retainedHandoffUntil = 0;
    float retainedPointerX = 0, retainedPointerY = 0;
    bool mapSpawned = false, multiplayer = false;
    int exits = 0, pauseStates = 0, drains = 0;
    std::vector<std::string> dispatched, loadedGames, played;
    std::vector<std::string> saves;
    bool IsMultiplayer() { return multiplayer; }
    void ExitMenu() { ++exits; guiActive = nullptr; }
    void PumpApplicationActions(idUserInterface*) { ++drains; }
    void DispatchCommand(idUserInterface* gui, const char* command) { CHECK(gui == guiMainMenu); dispatched.push_back(command); }
    void HandleMainMenuCommands(const char* command) { played.push_back(command); }
    void LoadGame(const char* slot) { loadedGames.push_back(slot); }
    void GetSaveGameList(idStrList& files, idList<fileTIME_T>& times) {
        for (size_t i = 0; i < saves.size(); ++i) { files.Append(idStr(saves[i])); times.Append({static_cast<int>(i), 100 - static_cast<ID_TIME_T>(i)}); }
    }
    void PublishRetainedPauseState(idUserInterface*) { ++pauseStates; }
    idStr RetainedPauseShot(const char*) const { return "gfx/guis/loadscreens/generic"; }
    void UpdateRetainedHome(); bool RetainedHomeInputBlocked() const; void RetainedHomeFrameEvent();
    void HandleRetainedSessionRequest(idUserInterface*, const char*);
    idUserInterface* SelectRetainedLoadingGui(idUserInterface*, bool);
    void PreloadRetainedScreens(); void PrepareRetainedLevel(const char*, bool);
    void ReportRetainedScreens();
};
'''

MAIN = r'''
static idSessionLocal Session(bool gate, bool inGame = false) {
    managerObject = Manager{}; commonObject = Common{}; commands = CommandSystem{}; legacy.clear(); legacyActions.clear(); precached.clear();
    legacyActionAvailable = true; preview = false; ui_retained.value = gate; ui_retainedSystem.value = false;
    static idUserInterface menu("guis/mainmenu.gui"); menu = idUserInterface("guis/mainmenu.gui");
    idSessionLocal session; session.guiActive = session.guiMainMenu = &menu; session.mapSpawned = inGame;
    legacy["desktop::curr"] = 0; legacy["desktop::active"] = 0; legacy["desktop::dest"] = 0;
    return session;
}
int main() {
    {   // Gate off: the stock interface presents everything and nothing retained loads.
        auto s = Session(false);
        for (int frame = 0; frame < 4; ++frame) s.UpdateRetainedHome();
        CHECK(s.guiRetainedHome == nullptr && managerObject.loads.empty());
        idUserInterface stock("guis/loading/generic.gui");
        CHECK(s.SelectRetainedLoadingGui(&stock, false) == &stock && managerObject.loads.empty());
        s.PreloadRetainedScreens(); s.PrepareRetainedLevel("game/airdefense1", false);
        CHECK(managerObject.loads.empty() && precached.empty());
        s.HandleRetainedSessionRequest(s.guiMainMenu, "quit");
        CHECK(commonObject.quits == 0 && legacyActions.empty());
        s.ReportRetainedScreens();
        CHECK(commonObject.output.find("OPENQ4_RETAINED enabled=0 system=0 home=- title=0 pause=0 handoff=0 views=0") != std::string::npos);
        ui_retainedSystem.value = true;
        CHECK(Session_RetainedSystemEnabled() && !Session_RetainedScreensEnabled());
        s.UpdateRetainedHome(); CHECK(s.guiRetainedHome == nullptr && managerObject.loads.empty());
    }
    {   // Title: presents over the legacy home state, describes the newest save.
        auto s = Session(true); s.saves = {"quick", "autosave"};
        legacy["desktop::video_check"] = 1; s.UpdateRetainedHome();
        CHECK(s.guiRetainedHome == nullptr && managerObject.loads.empty()); // logo videos stay legacy
        legacy["desktop::video_check"] = 0; s.UpdateRetainedHome();
        CHECK(s.guiRetainedHome && std::string(s.guiRetainedHome->Name()) == "guis/menu/title.q4ui");
        CHECK(managerObject.loads.size() == 1 && managerObject.flags[0].autoLoad && managerObject.flags[0].unique && !managerObject.flags[0].shared);
        CHECK(s.guiRetainedHome->active && s.guiRetainedHome->named.back() == "open");
        CHECK(s.guiRetainedHome->state["menu_continue"] == "1" && s.guiRetainedHome->state["menu_continue_title"] == "Air Defense Bunker");
        CHECK(s.guiRetainedHome->state["menu_continue_shot"] == "savegames/quick.tga");
        s.UpdateRetainedHome(); CHECK(managerObject.loads.size() == 1 && s.guiRetainedHome->activations == 1);
        auto* title = s.guiRetainedHome;
        // Depth: the pointer reaches the title in -1..1, and only when it moves.
        title->cursorX = 640; title->cursorY = 120; s.RetainedHomeFrameEvent();
        CHECK(title->state["pointer_x"] == std::to_string(1.0f) && title->state["pointer_y"] == std::to_string(-0.5f));
        title->state.erase("pointer_x"); s.RetainedHomeFrameEvent(); CHECK(!title->state.count("pointer_x"));
        // A page hand-off runs the legacy home button's own action.
        s.HandleRetainedSessionRequest(title, "loadGame");
        CHECK(legacyActions.back() == "main_b_loadgame" && title->named.back() == "depart");
        // Its label carries into the page's title slot as the bands dock.
        CHECK(title->named.size() >= 2 && title->named[title->named.size() - 2] == "carry_loadGame");
        CHECK(s.dispatched.back() == "play main_menu_selection" && s.RetainedHomeInputBlocked());
        legacy["desktop::active"] = 1; legacy["desktop::dest"] = 2;
        commonObject.time += 549; s.UpdateRetainedHome(); CHECK(s.guiRetainedHome == title);
        commonObject.time += 2; s.UpdateRetainedHome(); CHECK(s.guiRetainedHome == nullptr && !title->active);
        legacy["desktop::curr"] = 2; legacy["desktop::active"] = 0; s.UpdateRetainedHome(); CHECK(s.guiRetainedHome == nullptr);
        // Back on the page: the retained title returns with the bands at once.
        legacy["desktop::active"] = 1; legacy["desktop::dest"] = 0; s.UpdateRetainedHome();
        CHECK(s.guiRetainedHome == title && title->named.back() == "returnHome" && !s.RetainedHomeInputBlocked());
        CHECK(managerObject.loads.size() == 1);
        // Closing a home pop-up only reveals the content.
        s.HandleRetainedSessionRequest(title, "mods"); CHECK(legacyActions.back() == "main_b_mods" && title->named.back() == "departPopup");
        CHECK(title->named[title->named.size() - 2] != "carry_mods"); // a pop-up leaves the title where it is
        commonObject.time += 201; legacy["desktop::curr"] = 5; legacy["desktop::active"] = 0; s.UpdateRetainedHome(); CHECK(s.guiRetainedHome == nullptr);
        legacy["desktop::active"] = 1; legacy["desktop::dest"] = 0; s.UpdateRetainedHome(); CHECK(s.guiRetainedHome == title && title->named.back() == "open");
        // Session verbs never become console text; quit uses the stock path.
        s.HandleRetainedSessionRequest(title, "continue"); CHECK(s.loadedGames == std::vector<std::string>{"quick"});
        idUserInterface stranger("guis/other.q4ui"); s.HandleRetainedSessionRequest(&stranger, "quit"); CHECK(commonObject.quits == 0);
        s.HandleRetainedSessionRequest(title, "resume"); CHECK(s.exits == 0); // the title has no game to resume
        s.HandleRetainedSessionRequest(title, "unknown"); CHECK(commonObject.warnings.back().find("unhandled session request") != std::string::npos);
        legacyActionAvailable = false; s.HandleRetainedSessionRequest(title, "credits"); CHECK(!s.RetainedHomeInputBlocked());
        CHECK(commonObject.warnings.back().find("unavailable from the current menu") != std::string::npos);
        s.HandleRetainedSessionRequest(title, "quit"); CHECK(commonObject.quits == 1 && s.exits == 1);
        s.UpdateRetainedHome(); CHECK(s.guiRetainedHome == nullptr && !title->active); // the menu closed
    }
    {   // No save: CONTINUE stays hidden and has nothing to load.
        auto s = Session(true); s.UpdateRetainedHome();
        CHECK(s.guiRetainedHome->state["menu_continue"] == "0");
        s.HandleRetainedSessionRequest(s.guiRetainedHome, "continue"); CHECK(s.loadedGames.empty());
    }
    {   // Single-player pause and its verbs; multiplayer keeps the stock in-game menu.
        auto s = Session(true, true); s.UpdateRetainedHome();
        CHECK(s.guiRetainedHome && std::string(s.guiRetainedHome->Name()) == "guis/menu/pause.q4ui" && s.pauseStates == 1);
        auto* pause = s.guiRetainedHome;
        s.HandleRetainedSessionRequest(pause, "quitToMenu"); CHECK(commands.buffered == std::vector<std::string>{"disconnect\n"});
        s.HandleRetainedSessionRequest(pause, "restartLevel"); CHECK(legacyActions.back() == "main_b_difficulty");
        commonObject.time += 600; legacy["desktop::active"] = 0; legacy["desktop::dest"] = 0; s.UpdateRetainedHome();
        s.HandleRetainedSessionRequest(pause, "resume"); CHECK(s.exits == 1);
        s.UpdateRetainedHome(); CHECK(s.guiRetainedHome == nullptr && !pause->active);
        auto mp = Session(true, true); mp.multiplayer = true; mp.UpdateRetainedHome();
        CHECK(mp.guiRetainedHome == nullptr && managerObject.loads.empty());
        auto test = Session(true); idUserInterface probe("guis/probe.gui"); test.guiTest = &probe; test.UpdateRetainedHome();
        CHECK(test.guiRetainedHome == nullptr && managerObject.loads.empty());
        auto open = Session(true); preview = true; open.UpdateRetainedHome(); CHECK(open.guiRetainedHome == nullptr);
    }
    {   // Startup and single-player level loads resolve the screens and the pause levelshot.
        auto s = Session(true); s.PreloadRetainedScreens();
        CHECK((managerObject.loads == std::vector<std::string>{"guis/menu/title.q4ui", "guis/menu/pause.q4ui"}) && s.guiRetainedHome == nullptr);
        s.UpdateRetainedHome(); CHECK(managerObject.loads.size() == 2 && s.guiRetainedHome == s.guiRetainedTitle);
        s.PrepareRetainedLevel("mp/q4dm1", true); CHECK(precached.empty());
        s.PrepareRetainedLevel("game/airdefense1", false);
        CHECK((precached == std::vector<std::string>{"gfx/guis/loadscreens/generic"}) && managerObject.loads.size() == 2);
        auto late = Session(true); late.PrepareRetainedLevel("game/airdefense1", false); // the gate switched on after startup
        CHECK((managerObject.loads == std::vector<std::string>{"guis/menu/pause.q4ui"}) && precached.size() == 1);
    }
    {   // Loading: stock screens only, one shared instance, and a failed load reports once.
        auto s = Session(true); idUserInterface generic("guis/loading/generic.gui"), intro("guis/loading/intro.gui"), custom("guis/map/mylevel.gui");
        CHECK(s.SelectRetainedLoadingGui(&custom, false) == &custom && managerObject.loads.empty());
        auto* retained = s.SelectRetainedLoadingGui(&intro, true);
        CHECK(retained != &intro && std::string(retained->Name()) == "guis/loading/loading.q4ui");
        CHECK(!managerObject.flags[0].unique && managerObject.flags[0].shared);
        CHECK(retained->state["loading_mp"] == "1" && retained->state["loading_intro"] == "1" && retained->state["loading_ready"] == "0");
        auto failing = Session(true); managerObject.fail = true;
        CHECK(failing.SelectRetainedLoadingGui(&generic, false) == &generic && failing.SelectRetainedLoadingGui(&generic, false) == &generic);
        CHECK(managerObject.loads.size() == 1 && commonObject.warnings.size() == 1);
        auto title = Session(true); managerObject.fail = true; title.UpdateRetainedHome(); title.UpdateRetainedHome();
        CHECK(title.guiRetainedHome == nullptr && managerObject.loads.size() == 1 && commonObject.warnings.size() == 1);
    }
    std::printf("ui_retained gate: %d checks passed\n", checks);
}
'''


def cpp_allowlist(text: str) -> set[str]:
    block = function_body(text, 'bool SessionMenuCommand(')
    return set(re.findall(r'"([A-Za-z]+)"', block.split('{', 2)[2]))


def main() -> int:
    menu = (ROOT / 'src/framework/Session_menu.cpp').read_text(encoding='utf-8')
    session = (ROOT / 'src/framework/Session.cpp').read_text(encoding='utf-8')
    adapter = (ROOT / 'src/ui/UserInterfaceRetained.cpp').read_text(encoding='utf-8')

    # The gate itself.
    assert 'idCVar ui_retained( "ui_retained", "0", CVAR_GUI | CVAR_BOOL, ' in menu, 'ui_retained must default to 0 and stay unarchived'
    assert 'ui_retainedSystem( "ui_retainedSystem", "0", CVAR_GUI | CVAR_BOOL' in menu
    assert 'return Session_RetainedScreensEnabled() || ui_retainedSystem.GetBool();' in menu
    assert 'if ( !Session_RetainedSystemEnabled() || systemGuiTransition' in function_body(menu, 'bool idSessionLocal::OpenSystemSettings(')
    assert 'guiMainMenu->SetStateBool( "retainedSystem", Session_RetainedSystemEnabled() );' in menu
    # Every retained document path in the session is behind the gate.
    for source, name in ((menu, 'Session_menu.cpp'), (session, 'Session.cpp')):
        for match in re.finditer(r'"([^"]+\.q4ui)"', source):
            path = match.group(1)
            allowed = {'guis/menu/settings/system.q4ui', 'guis/menu/title.q4ui', 'guis/menu/pause.q4ui', 'guis/loading/loading.q4ui'}
            assert path in allowed, f'{name} names an ungated retained document {path}'
    assert menu.count('FindGui( "guis/menu/settings/system.q4ui"') == 1
    assert menu.count('RETAINED_TITLE_GUI') == 3 and menu.count('RETAINED_PAUSE_GUI') == 4 and menu.count('RETAINED_LOADING_GUI') == 2
    for signature in ('void idSessionLocal::PreloadRetainedScreens(', 'void idSessionLocal::PrepareRetainedLevel('):
        assert 'if ( !Session_RetainedScreensEnabled()' in function_body(menu, signature), f'{signature} must be gated'
    assert 'PreloadRetainedScreens();' in function_body(session, 'void idSessionLocal::Init(')
    # The loading phase line and prompt device publish only while the retained
    # loading screen presents the load, which only the gate can select.
    for signature in ('void idSessionLocal::SetRetainedLoadingPhase(', 'void idSessionLocal::PublishRetainedLoadingCount(',
                      'void idSessionLocal::PublishRetainedLoadingDevice('):
        assert 'if ( !retainedLoadingActive || guiLoading == NULL' in function_body(session, signature), signature
    loading = function_body(session, 'void idSessionLocal::LoadLoadingGui(')
    assert session.count('retainedLoadingActive = true;') == 1 and loading.index('if ( retainedLoading ) {') < loading.index('retainedLoadingActive = true;')
    assert 'PrepareRetainedLevel( spawnMapPath, isMultiplayerLoad );' in function_body(session, 'void idSessionLocal::LoadLoadingGui(')
    update = function_body(menu, 'void idSessionLocal::UpdateRetainedHome(')
    assert 'const bool context = Session_RetainedScreensEnabled() &&' in update
    # The home is updated before the frame pump's no-GUI return, so closing
    # the menu (resume) retires the pause screen instead of leaving it drawn.
    frame = function_body(menu, 'void idSessionLocal::GuiFrameEvents(')
    assert frame.index('UpdateRetainedHome();') < frame.index('ClearMenuControllerRepeatState();\n\t\treturn;\n\t}\n\n\tif ( guiActive ) {'), \
        'GuiFrameEvents must update the retained home before returning without a GUI'
    assert 'if ( !Session_RetainedScreensEnabled() || legacy == NULL ) {' in function_body(menu, 'idUserInterface *idSessionLocal::SelectRetainedLoadingGui(')
    assert 'guiLoading = SelectRetainedLoadingGui( guiLoading, isMultiplayerLoad );' in function_body(session, 'void idSessionLocal::LoadLoadingGui(')
    assert 'if ( guiRetainedHome != NULL && guiActive == guiMainMenu ) {' in function_body(menu, 'void idSessionLocal::MenuEvent(')
    assert '"ui_retainedStatus", Session_RetainedStatus_f' in session

    # Documents: current with their generator, verbs allowlisted and handled.
    generator = subprocess.run([sys.executable, str(ROOT / 'tools/ui/build_retained_screens.py'), '--check'], capture_output=True, text=True)
    assert generator.returncode == 0, generator.stderr
    allowlist = cpp_allowlist(adapter)
    handled = set(re.findall(r'\{ "([A-Za-z]+)",\s+"main_b_', menu)) | set(re.findall(r'!idStr::Icmp\( request, "([A-Za-z]+)" \)', menu))
    assert allowlist == handled, f'allowlist {sorted(allowlist)} differs from session handlers {sorted(handled)}'
    for relative in ('content/baseoq4/pak0/guis/menu/title.q4ui', 'content/baseoq4/pak0/guis/menu/pause.q4ui', 'content/baseoq4/pak0/guis/loading/loading.q4ui'):
        text = (ROOT / relative).read_text(encoding='utf-8')
        document = json.loads(re.sub(r'^\s*//.*$', '', text, flags=re.M))
        assert document.get('canvas') == {'height': 720}, relative
        for action in document.get('actions', {}).values():
            assert action['operation'] == 'session.menu' and action['arguments']['command'] in allowlist, relative
    # No game or legacy content names a retained document.
    for folder in (ROOT / 'content', ROOT.parent / 'openQ4-game' / 'src'):
        if not folder.exists():
            continue
        for path in folder.rglob('*'):
            if path.suffix.lower() in {'.gui', '.def', '.cfg', '.script', '.mtr', '.cpp', '.h'} and path.is_file():
                assert '.q4ui' not in path.read_text(encoding='utf-8', errors='replace'), f'{path} names a retained document'

    # Behaviour: the production session code against counted doubles.
    start = menu.index('static const char *const RETAINED_TITLE_GUI')
    tables = menu[start:menu.index('// Legacy pop-ups drawn over the home state', start)]
    bodies = [tables] + [function_body(menu, signature) for signature in (
        'static bool Session_RetainedHomePopup(', 'static idUserInterface *Session_FindRetainedGui(',
        'static void Session_PublishRetainedTitleState(', 'bool idSessionLocal::RetainedHomeInputBlocked(',
        'void idSessionLocal::UpdateRetainedHome(', 'void idSessionLocal::RetainedHomeFrameEvent(',
        'void idSessionLocal::HandleRetainedSessionRequest(', 'idUserInterface *idSessionLocal::SelectRetainedLoadingGui(',
        'void idSessionLocal::PreloadRetainedScreens(', 'void idSessionLocal::PrepareRetainedLevel(',
        'void idSessionLocal::ReportRetainedScreens(')]
    compiler = next((found for name in ('clang++', 'g++', 'c++') if (found := shutil.which(name))), None)
    if not compiler:
        raise RuntimeError('C++ compiler required')
    (ROOT / '.tmp').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ui-retained-gate-', dir=ROOT / '.tmp') as directory:
        source = Path(directory) / 'gate.cpp'
        binary = Path(directory) / 'gate.exe'
        source.write_text(SUPPORT + '\n'.join(bodies) + MAIN, encoding='utf-8')
        subprocess.run([compiler, '-std=c++20', '-Wall', '-Wextra', '-Wno-unused-function', str(source), '-o', str(binary)], check=True)
        result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=60)
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
