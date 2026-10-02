#!/usr/bin/env python3
"""The ui_retained gate and the stock fallback of every retained screen.

Compiles the production retained-screen session code (title and pause home
screens, hand-offs, session verbs, loading selection, the campaign selectors
and the status report) against counted engine/UI doubles, and checks the
source contracts that keep the gate complete:

* ui_retained defaults to 1 and is archived; while it is 0 no retained
  screen is reachable. ui_retainedSystem opts into the SYSTEM page, which
  ui_retained includes only once it offers every setting of the stock SYSTEM
  page; the list of settings it still lacks matches the two pages;
* each screen presents its stock GUI instead when its retained document is
  not installed (quietly) or cannot load (reported once), when the legacy
  main menu lacks a page the home screens hand off to, or when its view
  fails; the fallback holds for the session and ui_retainedStatus lists it;
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
from lang_table_encoding import font_code_points

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
#include <set>
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
template<typename T> struct idList : std::vector<T> {
    int Num() const { return static_cast<int>(this->size()); }
    void Append(const T& v) { this->push_back(v); }
    int FindIndex(const T& v) const { for (size_t i = 0; i < this->size(); ++i) if ((*this)[i] == v) return static_cast<int>(i); return -1; }
    int AddUnique(const T& v) { const int i = FindIndex(v); if (i >= 0) return i; Append(v); return Num() - 1; }
    void Clear() { this->clear(); }
};
using idStrList = idList<idStr>;
struct fileTIME_T { int index; ID_TIME_T timeStamp; };
struct Common {
    std::string output; std::vector<std::string> warnings, developer; int time = 1000, quits = 0;
    int GetPresentationTime() const { return time; }
    void Printf(const char* fmt, ...) { char text[2048]; va_list args; va_start(args, fmt); std::vsnprintf(text, sizeof(text), fmt, args); va_end(args); output += text; }
    void DPrintf(const char* fmt, ...) { char text[2048]; va_list args; va_start(args, fmt); std::vsnprintf(text, sizeof(text), fmt, args); va_end(args); developer.push_back(text); }
    void Warning(const char* fmt, ...) { char text[2048]; va_list args; va_start(args, fmt); std::vsnprintf(text, sizeof(text), fmt, args); va_end(args); warnings.push_back(text); }
    void Quit() { ++quits; }
    const struct LanguageDict* GetLanguageDict() const;
} commonObject, *common = &commonObject;
// The installed files the session can find, and the Awakening content probe.
struct idCampaignContentInfo { bool ready = true, present = true; idStr missing; };
#define MAX_STRING_CHARS 1024
struct FileSystem {
    std::set<std::string> files;
    std::map<std::string, std::string> screenshots; // a map's own levelshot; the stock search ends at the generic .tga
    int ReadFile(const char* path, void**, ID_TIME_T*) { return files.count(path) ? 64 : -1; }
    void FindMapScreenshot(const char* map, char* buffer, int length) {
        const auto found = screenshots.find(map);
        std::snprintf(buffer, length, "%s", found == screenshots.end() ? "gfx/guis/loadscreens/generic.tga" : found->second.c_str());
    }
    idCampaignContentInfo GetAwakeningContentInfo() { return {}; }
} fileSystemObject, *fileSystem = &fileSystemObject;
struct ArenaCampaign { int selectors = 0; void OpenSelector() { ++selectors; } } arenaCampaign;
struct idDict {
    std::map<std::string, std::string> values;
    const char* GetString(const char* key, const char* fallback = "") const { const auto found = values.find(key); return found == values.end() ? fallback : found->second.c_str(); }
};
struct MapSpawnData { idDict serverInfo; };
static std::map<std::string, idDict> mapDecls;
static bool Session_GetMapDeclDict(const char* map, const char*, idDict& out) {
    const auto found = mapDecls.find(map); if (found == mapDecls.end()) return false; out = found->second; return true;
}
static bool Session_FileExistsInSearchPaths(const char* path) { return fileSystemObject.files.count(path) != 0; }
struct LanguageDict {
    const char* GetString(const char* key) const {
        return !std::strcmp(key, "#str_230046") ? "in mission" : !std::strcmp(key, "#str_230048") ? "saved %d min ago" :
               !std::strcmp(key, "#str_230049") ? "saved %d h ago" : !std::strcmp(key, "#str_230050") ? "saved just now" : key;
    }
} languageObject;
const LanguageDict* Common::GetLanguageDict() const { return &languageObject; }
static const char* Session_GetSkillName() { return "Corporal"; }
struct idUserInterface;
struct Game {
    std::vector<std::string> commands; std::function<void(idUserInterface*)> publish;
    void HandleMainMenuCommands(const char* command, idUserInterface* gui) { commands.push_back(command); if (publish) publish(gui); }
} gameObject, *game = &gameObject;
struct CVar { bool value = false; bool GetBool() const { return value; } } ui_retained, ui_retainedSystem;
enum { SE_NONE = 0, CMD_EXEC_APPEND = 1 };
struct sysEvent_t { int evType = SE_NONE; };
struct idUserInterface {
    std::string source; bool active = false, failed = false; int activations = 0, deactivations = 0;
    std::vector<std::string> named; std::map<std::string, std::string> state;
    explicit idUserInterface(const char* name) : source(name) {}
    const char* Name() const { return source.c_str(); }
    const char* Activate(bool value, int) { active = value; ++(value ? activations : deactivations); return ""; }
    void HandleNamedEvent(const char* name) { named.push_back(name); }
    const char* HandleEvent(const sysEvent_t*, int) { return ""; }
    void SetStateBool(const char* key, bool value) { state[key] = value ? "1" : "0"; }
    void SetStateInt(const char* key, int value) { state[key] = std::to_string(value); }
    struct StateView {
        const std::map<std::string, std::string>& values;
        int GetInt(const char* key, const char* fallback) const { const auto found = values.find(key); return std::atoi(found == values.end() ? fallback : found->second.c_str()); }
        bool GetBool(const char* key, const char* fallback = "0") const { return GetInt(key, fallback) != 0; }
        const char* GetString(const char* key, const char* fallback = "") const { const auto found = values.find(key); return found == values.end() ? fallback : found->second.c_str(); }
    };
    StateView State() const { return {state}; }
    void SetStateString(const char* key, const char* value) { state[key] = value; }
    void SetStateFloat(const char* key, float value) { state[key] = std::to_string(value); }
    float cursorX = 320, cursorY = 240;
    float CursorX() { return cursorX; }
    float CursorY() { return cursorY; }
    void StateChanged(int) {}
};
enum { AXIS_SIDE = 0, AXIS_FORWARD = 1 };
static int stickX = 0, stickY = 0;
static bool Sys_GetJoystickAxisState(int axis, int& value) { value = axis == AXIS_SIDE ? stickX : stickY; return true; }
static int MenuControllerAbs(int value) { return value < 0 ? -value : value; }
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
static std::vector<std::string> precached, reloaded;
static void UI_RetainedPrecacheImage(const char* source) { precached.push_back(source); }
static void UI_RetainedReloadImage(const char* source) { reloaded.push_back(source); }
// Windows a mod's own main menu lacks, and a retained view that stopped drawing.
static std::set<std::string> legacyMissing;
static bool UI_LegacyWindowExists(idUserInterface*, const char* window) { return !legacyMissing.count(window); }
static bool UI_RetainedViewFailed(idUserInterface* gui) { return gui->failed; }
static const char* Sys_TimeStampToStr(ID_TIME_T) { return "29 Sep 2026 12:40"; }
struct sessionMenuSaveDescription_t { idStr saveName, description, screenshot; bool noOverwrite = false; };
static std::string describedShot; // an autosave names its loadscreen; other saves name none
static bool Session_MenuReadSaveDescription(const idStr& slot, sessionMenuSaveDescription_t& out) {
    out.saveName = slot; out.description = "Air Defense Bunker"; out.screenshot = describedShot; return true;
}
static const char* va(const char* fmt, ...) {
    static char text[1024]; va_list args; va_start(args, fmt); std::vsnprintf(text, sizeof(text), fmt, args); va_end(args); return text;
}
class idSessionLocal {
public:
    idUserInterface *guiActive = nullptr, *guiMainMenu = nullptr, *guiTest = nullptr;
    idUserInterface *guiRetainedHome = nullptr, *guiRetainedTitle = nullptr, *guiRetainedPause = nullptr, *guiRetainedPauseStrogg = nullptr;
    int retainedPauseStrogg = -1;
    ID_TIME_T retainedNewestSave = 0;
    idUserInterface* guiRetainedReleasing = nullptr; int retainedReleaseUntil = 0;
    bool retainedHomeReturning = false;
    idStrList retainedStock;
    int retainedHandoffUntil = 0;
    float retainedPointerX = 0, retainedPointerY = 0;
    bool mapSpawned = false, multiplayer = false;
    int exits = 0, pauseStates = 0, drains = 0, saveLists = 0;
    std::vector<std::string> dispatched, loadedGames, played;
    std::vector<std::string> saves;
    bool IsMultiplayer() { return multiplayer; }
    void ExitMenu() { ++exits; guiActive = nullptr; }
    void PumpApplicationActions(idUserInterface*) { ++drains; }
    void DispatchCommand(idUserInterface* gui, const char* command) { CHECK(gui == guiMainMenu); dispatched.push_back(command); }
    void HandleMainMenuCommands(const char* command) { played.push_back(command); }
    void LoadGame(const char* slot) { loadedGames.push_back(slot); }
    void GetSaveGameList(idStrList& files, idList<fileTIME_T>& times) {
        ++saveLists;
        for (size_t i = 0; i < saves.size(); ++i) { files.Append(idStr(saves[i])); times.Append({static_cast<int>(i), 100 - static_cast<ID_TIME_T>(i)}); }
    }
    idStr currentMapName = idStr("game/airdefense1");
    void PublishRetainedPauseState(idUserInterface*);
    MapSpawnData mapSpawnData;
    idStr RetainedPauseShot(const char*) const;
    void UpdateRetainedHome(); bool RetainedHomeInputBlocked() const; void RetainedHomeFrameEvent();
    void HandleRetainedSessionRequest(idUserInterface*, const char*);
    void OpenCampaignSelector(bool);
    void SelectCampaign(const char*) {}
    void StartMenu() {}
    void SetGUI(idUserInterface* gui, void*) { guiActive = gui; }
    idUserInterface* SelectRetainedLoadingGui(idUserInterface*, bool);
    idUserInterface* FindRetainedGui(const char*, bool, bool);
    idUserInterface* RetainedHomeDocument(idUserInterface*&, const char*);
    bool RetainedPauseIsStrogg();
    bool RetainedSystemAvailable() const;
    void PreloadRetainedScreens(); void PrepareRetainedLevel(const char*, bool); void PrecacheRetainedLevelImages();
    void ReportRetainedScreens();
};
'''

MAIN = r'''
static const char* const DOCUMENTS[] = {"guis/menu/title.q4ui", "guis/menu/pause.q4ui", "guis/menu/pause_strogg.q4ui", "guis/loading/loading.q4ui",
    "guis/menu/singleplayer.q4ui", "guis/menu/campaigns.q4ui", "guis/menu/settings/system.q4ui"};
// The documents that fell back to their stock screens, in order.
static std::vector<std::string> Stock(const idSessionLocal& session) {
    return std::vector<std::string>(session.retainedStock.begin(), session.retainedStock.end());
}
static idSessionLocal Session(bool gate, bool inGame = false) {
    managerObject = Manager{}; commonObject = Common{}; commands = CommandSystem{}; legacy.clear(); legacyActions.clear(); precached.clear(); stickX = stickY = 0;
    legacyActionAvailable = true; preview = false; ui_retained.value = gate; ui_retainedSystem.value = false;
    fileSystemObject.files = std::set<std::string>(std::begin(DOCUMENTS), std::end(DOCUMENTS)); arenaCampaign = ArenaCampaign{};
    legacyMissing.clear(); reloaded.clear(); describedShot = "savegames/quick.tga"; mapDecls.clear(); fileSystemObject.screenshots.clear();
    gameObject = Game{};
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
        CHECK(commonObject.output.find("OPENQ4_RETAINED enabled=0 system=0 home=- title=0 pause=0 strogg=0 handoff=0 release=0 views=0 stock=-") != std::string::npos);
        // Off, the campaign selectors are the stock ones and nothing retained loads.
        s.OpenCampaignSelector(false); CHECK(arenaCampaign.selectors == 1 && managerObject.loads.empty());
        s.OpenCampaignSelector(true); CHECK((managerObject.loads == std::vector<std::string>{"guis/campaign_menu.gui"}));
        CHECK(!s.RetainedSystemAvailable());
        managerObject.loads.clear(); s.guiActive = s.guiMainMenu;
        ui_retainedSystem.value = true;
        CHECK(Session_RetainedSystemEnabled() && !Session_RetainedScreensEnabled() && s.RetainedSystemAvailable());
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
        // A held look stick leads; released, the lean returns to the pointer.
        stickX = -127; s.RetainedHomeFrameEvent(); CHECK(title->state["pointer_x"] == std::to_string(-1.0f));
        stickX = 10; s.RetainedHomeFrameEvent(); CHECK(title->state["pointer_x"] == std::to_string(1.0f));
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
        CHECK(s.guiRetainedHome && std::string(s.guiRetainedHome->Name()) == "guis/menu/pause.q4ui" && s.guiRetainedHome->state["pause_level"] == "game/airdefense1");
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
        CHECK((precached == std::vector<std::string>{"gfx/guis/loadscreens/generic"}) && managerObject.loads.size() == 3);
        CHECK(managerObject.loads.back() == "guis/menu/pause_strogg.q4ui");  // either family may pause the level
        auto late = Session(true); late.PrepareRetainedLevel("game/airdefense1", false); // the gate switched on after startup
        CHECK((managerObject.loads == std::vector<std::string>{"guis/menu/pause.q4ui", "guis/menu/pause_strogg.q4ui"}) && precached.size() == 1);
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
        CHECK((Stock(title) == std::vector<std::string>{"guis/menu/title.q4ui"}));
    }
    {   // A document that is not installed falls back quietly, screen by screen.
        auto s = Session(true); fileSystemObject.files.erase("guis/menu/title.q4ui");
        s.UpdateRetainedHome(); s.UpdateRetainedHome();
        CHECK(s.guiRetainedHome == nullptr && managerObject.loads.empty() && commonObject.warnings.empty());
        CHECK(commonObject.developer.size() == 1 && commonObject.developer[0].find("not installed") != std::string::npos);
        s.ReportRetainedScreens(); CHECK(commonObject.output.find("views=0 stock=guis/menu/title.q4ui\n") != std::string::npos);
        s.mapSpawned = true; s.UpdateRetainedHome(); // the pause screen is installed and still presents
        CHECK(s.guiRetainedHome && std::string(s.guiRetainedHome->Name()) == "guis/menu/pause.q4ui");
        idUserInterface generic("guis/loading/generic.gui"); fileSystemObject.files.erase("guis/loading/loading.q4ui");
        CHECK(s.SelectRetainedLoadingGui(&generic, false) == &generic && commonObject.warnings.empty());
        CHECK(s.retainedStock.Num() == 2 && managerObject.loads.size() == 1);
    }
    {   // A main menu without every page the home screens hand off to keeps its own
        // home screen, as a mod's own menu would; the loading screens still present.
        auto s = Session(true); legacyMissing = {"main_b_demos"};
        s.PreloadRetainedScreens(); s.UpdateRetainedHome(); s.mapSpawned = true; s.UpdateRetainedHome();
        CHECK(s.guiRetainedHome == nullptr && managerObject.loads.empty() && commonObject.warnings.empty());
        CHECK((Stock(s) == std::vector<std::string>{"guis/menu/title.q4ui", "guis/menu/pause.q4ui"}));
        CHECK(commonObject.developer.size() == 2 && commonObject.developer[0].find("'main_b_demos'") != std::string::npos);
        idUserInterface generic("guis/loading/generic.gui");
        CHECK(s.SelectRetainedLoadingGui(&generic, false) != &generic);
    }
    {   // A view that failed to come back after a renderer restart hands the screen back for good.
        auto s = Session(true); s.UpdateRetainedHome(); auto* title = s.guiRetainedHome; CHECK(title && title->active);
        title->failed = true; s.UpdateRetainedHome();
        CHECK(s.guiRetainedHome == nullptr && !title->active && s.guiRetainedTitle == nullptr);
        CHECK(commonObject.warnings.size() == 1 && commonObject.warnings[0].find("stopped drawing") != std::string::npos);
        s.UpdateRetainedHome(); s.PreloadRetainedScreens();
        CHECK(s.guiRetainedHome == nullptr && managerObject.loads.size() == 2 && commonObject.warnings.size() == 1); // title, then pause
    }
    {   // The campaign selectors: the retained ones while installed, the stock ones otherwise.
        auto s = Session(true); s.OpenCampaignSelector(false);
        CHECK(s.guiActive && std::string(s.guiActive->Name()) == "guis/menu/singleplayer.q4ui" && arenaCampaign.selectors == 0);
        s.OpenCampaignSelector(true);
        CHECK(std::string(s.guiActive->Name()) == "guis/menu/campaigns.q4ui" && s.guiActive->state["awakening_ready"] == "1");
        CHECK(!managerObject.flags[0].unique && managerObject.flags[0].shared);
        auto missing = Session(true);
        fileSystemObject.files.erase("guis/menu/singleplayer.q4ui"); fileSystemObject.files.erase("guis/menu/campaigns.q4ui");
        missing.OpenCampaignSelector(false); CHECK(arenaCampaign.selectors == 1 && managerObject.loads.empty());
        missing.OpenCampaignSelector(true); CHECK(std::string(missing.guiActive->Name()) == "guis/campaign_menu.gui");
        missing.OpenCampaignSelector(false); CHECK(arenaCampaign.selectors == 2 && commonObject.warnings.empty());
        auto broken = Session(true); managerObject.fail = true; broken.OpenCampaignSelector(false);
        CHECK(arenaCampaign.selectors == 1 && commonObject.warnings.size() == 1);
    }
    {   // The gate alone keeps the stock SYSTEM page while the retained one lacks stock settings;
        // ui_retainedSystem opts into it until it falls back.
        auto s = Session(true); CHECK(RETAINED_SYSTEM_MISSING_SETTINGS[0] != NULL && !s.RetainedSystemAvailable());
        ui_retainedSystem.value = true; CHECK(s.RetainedSystemAvailable());
        s.retainedStock.Append("guis/menu/settings/system.q4ui"); CHECK(!s.RetainedSystemAvailable());
    }
    {   // CONTINUE shows a save's own screenshot, freshly read, only when it exists.
        auto s = Session(true); s.saves = {"quick"}; describedShot = ""; fileSystemObject.files.insert("savegames/quick.tga");
        s.UpdateRetainedHome();
        CHECK(s.guiRetainedHome->state["menu_continue_shot"] == "savegames/quick.tga");
        CHECK((reloaded == std::vector<std::string>{"savegames/quick.tga"}));
        auto bare = Session(true); bare.saves = {"quick"}; describedShot = ""; bare.UpdateRetainedHome();
        CHECK(bare.guiRetainedHome->state["menu_continue"] == "1" && bare.guiRetainedHome->state["menu_continue_shot"].empty() && reloaded.empty());
        auto autosave = Session(true); autosave.saves = {"autosave"}; describedShot = "gfx/guis/loadscreens/airdefense";
        autosave.UpdateRetainedHome(); CHECK(autosave.guiRetainedHome->state["menu_continue_shot"] == "gfx/guis/loadscreens/airdefense");
    }
    {   // The level block's levelshot follows the loading screen's choice and falls through missing pictures.
        auto s = Session(true, true);
        mapDecls["game/airdefense2"] = idDict{{{"loadimage", "gfx/guis/loadscreens/airdefense"}}};
        mapDecls["game/airdefense1"] = idDict{{{"loadgui", "guis/loading/intro.gui"}}};
        mapDecls["game/building_b"] = idDict{{{"loadimage", "gfx/guis/loadscreens/missing"}}};
        for (const char* file : {"gfx/guis/loadscreens/airdefense.tga", "gfx/guis/loadscreens/e3_load.tga", "gfx/guis/loadscreens/defstation.tga"})
            fileSystemObject.files.insert(file);
        fileSystemObject.screenshots["game/building_b"] = "gfx/guis/loadscreens/defstation.tga";
        CHECK(s.RetainedPauseShot("game/airdefense2") == "gfx/guis/loadscreens/airdefense");
        CHECK(s.RetainedPauseShot("game/airdefense1") == "gfx/guis/loadscreens/e3_load");
        CHECK(s.RetainedPauseShot("game/building_b") == "gfx/guis/loadscreens/defstation.tga"); // its loadimage is not installed
        CHECK(s.RetainedPauseShot("game/unknown") == "gfx/guis/loadscreens/generic");
    }
    {   // The level block asks the game for the open objectives and the time in the mission.
        auto s = Session(true, true);
        mapDecls["game/airdefense1"] = idDict{{{"name", "Air Defense Bunker"}, {"objectives", "Reach the bunker."}}};
        gameObject.publish = [](idUserInterface* gui) {
            gui->SetStateInt("pause_objective_count", 2); gui->SetStateString("pause_objective_0", "Destroy the battery");
            gui->SetStateString("pause_objective_1", "Reach the bunker"); gui->SetStateInt("pause_mission_seconds", 2530);
        };
        s.UpdateRetainedHome(); auto* pause = s.guiRetainedHome;
        CHECK(pause && (gameObject.commands == std::vector<std::string>{"retainedPauseFamily", "retainedPauseState"}));
        CHECK(pause->state["pause_level"] == "Air Defense Bunker" && pause->state["pause_detail"] == "Corporal");
        CHECK(pause->state["pause_objective_count"] == "2" && pause->state["pause_objective_0"] == "Destroy the battery");
        CHECK(pause->state["pause_stats"] == "0:42:10 in mission");
        // With a save, the time line adds how long ago the newest one was written:
        // read once inside the level load, so opening the pause lists no files.
        auto saved = Session(true, true); saved.saves = {"quick", "older"}; mapDecls["game/airdefense1"] = idDict{};
        gameObject.publish = [](idUserInterface* gui) { gui->SetStateInt("pause_mission_seconds", 2530); };
        saved.PrepareRetainedLevel("game/airdefense1", false);
        CHECK(saved.saveLists == 1 && saved.retainedNewestSave == 100);
        saved.UpdateRetainedHome();
        CHECK(saved.guiRetainedHome->state["pause_stats"].rfind("0:42:10 in mission \xc2\xb7 saved ", 0) == 0);
        saved.ExitMenu(); saved.UpdateRetainedHome(); saved.guiActive = saved.guiMainMenu; saved.UpdateRetainedHome();
        CHECK(saved.saveLists == 1);
        // A level without saves, or a load with the gate off, shows no save age.
        auto unsaved = Session(true, true); unsaved.PrepareRetainedLevel("game/airdefense1", false);
        gameObject.publish = [](idUserInterface* gui) { gui->SetStateInt("pause_mission_seconds", 2530); };
        unsaved.UpdateRetainedHome();
        CHECK(unsaved.retainedNewestSave == 0 && unsaved.guiRetainedHome->state["pause_stats"] == "0:42:10 in mission");
        auto gateOff = Session(false, true); gateOff.saves = {"quick"}; gateOff.PrepareRetainedLevel("game/airdefense1", false);
        CHECK(gateOff.saveLists == 0 && gateOff.retainedNewestSave == 0);
        CHECK(std::string(Session_RetainedSaveAge(1000, 1030).c_str()) == "saved just now");
        CHECK(std::string(Session_RetainedSaveAge(1000, 1000 + 4 * 60 + 59).c_str()) == "saved 4 min ago");
        CHECK(std::string(Session_RetainedSaveAge(1000, 1000 + 3 * 3600 + 10).c_str()) == "saved 3 h ago");
        CHECK(std::string(Session_RetainedSaveAge(2000, 1000).c_str()) == "saved just now"); // a clock set back
        // A game module that publishes nothing leaves the map's summary and no time line.
        auto quiet = Session(true, true); mapDecls["game/airdefense1"] = idDict{{{"objectives", "Reach the bunker."}}};
        quiet.UpdateRetainedHome();
        CHECK(quiet.guiRetainedHome->state["pause_objective_count"] == "0" && quiet.guiRetainedHome->state["pause_stats"].empty());
        CHECK(quiet.guiRetainedHome->state["pause_objectives"] == "Reach the bunker.");
    }
    {   // After Kane's stroggification the pause takes the Strogg family. The game
        // answers once a level, and the Marine pause stands in when the Strogg
        // pause cannot present.
        auto s = Session(true, true);
        gameObject.publish = [](idUserInterface* gui) { gui->SetStateBool("pause_strogg", true); };
        s.UpdateRetainedHome(); auto* strogg = s.guiRetainedHome;
        CHECK(strogg && std::string(strogg->Name()) == "guis/menu/pause_strogg.q4ui" && strogg == s.guiRetainedPauseStrogg);
        CHECK(strogg->active && strogg->named.back() == "open" && strogg->state["pause_level"] == "game/airdefense1");
        CHECK((gameObject.commands == std::vector<std::string>{"retainedPauseFamily", "retainedPauseState"}));
        CHECK((managerObject.loads == std::vector<std::string>{"guis/menu/pause_strogg.q4ui"}));
        s.HandleRetainedSessionRequest(strogg, "resume"); CHECK(s.exits == 1);
        s.UpdateRetainedHome(); CHECK(s.guiRetainedHome == nullptr && !strogg->active);
        CHECK(strogg->named.back() == "release" && s.guiRetainedReleasing == strogg);  // either family releases the softened view
        s.guiActive = s.guiMainMenu; s.UpdateRetainedHome();
        CHECK(s.guiRetainedHome == strogg && std::count(gameObject.commands.begin(), gameObject.commands.end(), "retainedPauseFamily") == 1);
        CHECK(s.guiRetainedReleasing == nullptr && strogg->named.back() == "open");  // pausing again during the release reopens it
        s.ReportRetainedScreens(); CHECK(commonObject.output.find("pause=0 strogg=1 handoff=0") != std::string::npos);
        // Each level asks again: a Marine level pauses in the Marine family.
        s.ExitMenu(); s.UpdateRetainedHome(); s.PrepareRetainedLevel("game/airdefense1", false);
        gameObject.publish = nullptr; s.guiActive = s.guiMainMenu; s.UpdateRetainedHome();
        CHECK(s.guiRetainedHome && std::string(s.guiRetainedHome->Name()) == "guis/menu/pause.q4ui");
        CHECK(std::count(gameObject.commands.begin(), gameObject.commands.end(), "retainedPauseFamily") == 2);
        // A Strogg view that stopped drawing hands over to the Marine pause.
        s.ExitMenu(); s.UpdateRetainedHome(); s.PrepareRetainedLevel("game/recomp", false);
        gameObject.publish = [](idUserInterface* gui) { gui->SetStateBool("pause_strogg", true); };
        strogg->failed = true; s.guiActive = s.guiMainMenu; s.UpdateRetainedHome();
        CHECK(s.guiRetainedHome && std::string(s.guiRetainedHome->Name()) == "guis/menu/pause.q4ui" && s.guiRetainedPauseStrogg == nullptr);
        CHECK(commonObject.warnings.size() == 1 && commonObject.warnings[0].find("stopped drawing") != std::string::npos);
        CHECK((Stock(s) == std::vector<std::string>{"guis/menu/pause_strogg.q4ui"}));
        // Not installed, it falls back quietly to the Marine pause.
        auto missing = Session(true, true); fileSystemObject.files.erase("guis/menu/pause_strogg.q4ui");
        gameObject.publish = [](idUserInterface* gui) { gui->SetStateBool("pause_strogg", true); };
        missing.UpdateRetainedHome();
        CHECK(missing.guiRetainedHome && std::string(missing.guiRetainedHome->Name()) == "guis/menu/pause.q4ui" && commonObject.warnings.empty());
        CHECK((Stock(missing) == std::vector<std::string>{"guis/menu/pause_strogg.q4ui"}));
        // The title never asks the game.
        auto title = Session(true); title.UpdateRetainedHome(); CHECK(gameObject.commands.empty());
    }
    {   // RESUME closes the pause screen at once, but the closed screen keeps
        // drawing over the running game for 250 ms while the softened view
        // releases; anything else taking the screen ends the release.
        auto s = Session(true, true); s.UpdateRetainedHome(); auto* pause = s.guiRetainedHome;
        CHECK(pause && std::string(pause->Name()) == "guis/menu/pause.q4ui" && s.guiRetainedReleasing == nullptr);
        s.HandleRetainedSessionRequest(pause, "resume"); s.UpdateRetainedHome();
        CHECK(s.guiRetainedHome == nullptr && !pause->active && pause->deactivations == 1);
        CHECK(pause->named.back() == "release" && s.guiRetainedReleasing == pause && s.retainedReleaseUntil == commonObject.time + 250);
        s.ReportRetainedScreens(); CHECK(commonObject.output.find("home=- title=0 pause=1 strogg=0 handoff=0 release=1") != std::string::npos);
        commonObject.time += 249; s.UpdateRetainedHome(); CHECK(s.guiRetainedReleasing == pause && !pause->active);
        commonObject.time += 1; s.UpdateRetainedHome(); CHECK(s.guiRetainedReleasing == nullptr && pause->activations == 1);
        // A disconnect or a level load ends it at once.
        s.guiActive = s.guiMainMenu; s.UpdateRetainedHome(); s.ExitMenu(); s.UpdateRetainedHome(); CHECK(s.guiRetainedReleasing == pause);
        s.mapSpawned = false; s.UpdateRetainedHome(); CHECK(s.guiRetainedReleasing == nullptr);
        s.mapSpawned = true; s.guiActive = s.guiMainMenu; s.UpdateRetainedHome(); s.ExitMenu(); s.UpdateRetainedHome();
        s.PrepareRetainedLevel("game/airdefense1", false); CHECK(s.guiRetainedReleasing == nullptr);
        // The pause handing over to another screen, and the title closing, release nothing.
        s.guiActive = s.guiMainMenu; s.UpdateRetainedHome(); idUserInterface other("guis/msg.gui"); s.guiActive = &other;
        s.UpdateRetainedHome(); CHECK(s.guiRetainedHome == nullptr && s.guiRetainedReleasing == nullptr && pause->named.back() != "release");
        auto title = Session(true); title.UpdateRetainedHome(); auto* home = title.guiRetainedHome;
        title.mapSpawned = true; title.ExitMenu(); title.UpdateRetainedHome();  // CONTINUE: the title closes into a level
        CHECK(home && std::string(home->Name()) == "guis/menu/title.q4ui" && title.guiRetainedReleasing == nullptr && home->named.back() != "release");
    }
    {   // The Objectives page: the game lists every objective screenshot of the level,
        // which resolves inside the load, and a published screenshot shows only when
        // it is a plain, installed image name.
        auto s = Session(true, true);
        for (const char* file : {"gfx/objectives/airdefense_obj_1.tga", "gfx/objectives/airdefense_obj_2.tga"}) fileSystemObject.files.insert(file);
        gameObject.publish = [](idUserInterface* gui) {
            gui->SetStateInt("level_image_count", 3); gui->SetStateString("level_image_0", "gfx/objectives/airdefense_obj_1");
            gui->SetStateString("level_image_1", "gfx/objectives/missing"); gui->SetStateString("level_image_2", "../escape");
            gui->SetStateInt("pause_objective_count", 3);
            gui->SetStateString("pause_objective_shot_0", "gfx/objectives/airdefense_obj_2");
            gui->SetStateString("pause_objective_shot_1", "gfx/objectives/missing");
            gui->SetStateString("pause_objective_shot_2", "../escape");
        };
        s.PrecacheRetainedLevelImages(); CHECK(precached.empty() && gameObject.commands.empty()); // no pause document loaded yet
        s.PrepareRetainedLevel("game/airdefense1", false); precached.clear();
        s.PrecacheRetainedLevelImages();
        CHECK((gameObject.commands == std::vector<std::string>{"retainedLevelImages"}));
        CHECK((precached == std::vector<std::string>{"gfx/objectives/airdefense_obj_1"}));
        s.UpdateRetainedHome(); auto* pause = s.guiRetainedHome;
        CHECK(pause && pause->state["pause_objective_shot_0"] == "gfx/objectives/airdefense_obj_2");
        CHECK(pause->state["pause_objective_shot_1"].empty() && pause->state["pause_objective_shot_2"].empty());
        auto off = Session(false, true); off.PrepareRetainedLevel("game/airdefense1", false); off.PrecacheRetainedLevelImages();
        CHECK(precached.empty() && gameObject.commands.empty()); // the gate off loads no pause, so nothing resolves
    }
    std::printf("ui_retained gate: %d checks passed\n", checks);
}
'''


# Stock SYSTEM rows that drive a setting through the session or a GUI
# variable rather than a cvar binding.
STOCK_SYSTEM_SESSION_ROWS = {'set_sys_screensize': 'r_mode', 'set_sys_specular': 'r_skipSpecular', 'set_sys_bump': 'r_skipBump',
                             'set_sys_sky': 'r_skipSky', 'set_sys_ambient': 'r_forceAmbient'}
# Stock SYSTEM controls that navigate the page instead of changing a setting.
STOCK_SYSTEM_PAGE_CONTROLS = {'set_sys_section_choice'}


def stock_system_settings() -> set[str]:
    """Every setting the stock SYSTEM page offers a control for."""
    gui = (ROOT / 'content/baseoq4/pak0/guis/menu/settings/system.gui').read_text(encoding='utf-8', errors='replace')
    gui = re.sub(r'/\*.*?\*/', '', re.sub(r'//[^\n]*', '', gui), flags=re.S)
    settings = set()
    definitions = list(re.finditer(r'\b(?:windowDef|choiceDef|sliderDef|editDef|listDef|bindDef)\s+(\w+)', gui))
    for index, definition in enumerate(definitions):
        if not re.match(r'(?:choiceDef|sliderDef|editDef)', definition.group(0)) or definition.group(1) in STOCK_SYSTEM_PAGE_CONTROLS:
            continue
        span = gui[definition.end():definitions[index + 1].start() if index + 1 < len(definitions) else len(gui)]
        cvar = re.search(r'\bcvar\s+"?(\w+)"?', span)
        row = re.match(r'(set_sys_\w+?)_val', definition.group(1))
        if cvar:
            if cvar.group(1) != 'gui_set_sys_scroll':
                settings.add(cvar.group(1))
        elif row and row.group(1) in STOCK_SYSTEM_SESSION_ROWS:
            settings.add(STOCK_SYSTEM_SESSION_ROWS[row.group(1)])
        else:
            raise AssertionError(f'stock SYSTEM control {definition.group(1)} binds no cvar; map it in STOCK_SYSTEM_SESSION_ROWS')
    return settings


def retained_system_controls() -> set[str]:
    """Every setting the retained SYSTEM page has a control for: the drafts control values read."""
    text = (ROOT / 'content/baseoq4/pak0/guis/menu/settings/system.q4ui').read_text(encoding='utf-8')
    document = json.loads(re.sub(r'^\s*//.*$', '', text, flags=re.M))
    found = set()

    def expressions(value):
        if isinstance(value, dict):
            state = value.get('state')
            if isinstance(state, str) and state.startswith('settings.draft.'):
                found.add(state[len('settings.draft.'):])
            for item in value.values():
                expressions(item)
        elif isinstance(value, list):
            for item in value:
                expressions(item)

    def walk(node):
        control = node.get('control')
        if isinstance(control, dict) and 'value' in control:
            expressions(control['value'])
        for child in node.get('children', []):
            walk(child)

    walk(document['root'])
    return found


def cpp_allowlist(text: str) -> set[str]:
    block = function_body(text, 'bool SessionMenuCommand(')
    return set(re.findall(r'"([A-Za-z][A-Za-z0-9]*)"', block.split('{', 2)[2]))


FACES = r'''
#include <cstdint>
#include <cstdio>
#include <iostream>
#include <string>
'''

FACES_MAIN = r'''
int main() {
    for (const char* family : {"marine", "lowpixel", "r_strogg", "strogg", "chain", "Marine", "unknown"})
        std::printf("family %s %s\n", family, FontFamily(family).c_str());
    unsigned scalar = 0;
    while (std::cin >> scalar) std::printf("%u %u\n", scalar, static_cast<unsigned>(RuneScalar(scalar)));
    return 0;
}
'''


def check_strogg_faces(compiler: str, directory: Path) -> int:
    """The Strogg pause names the r_strogg and strogg faces, and every label's
    rune copy draws through the host's fold. Compile both host functions and
    check that the faces resolve to themselves, and that every code point of
    the shipped string tables, and every code point below U+FFFF, folds to a
    code point the rune face covers or to a space."""
    host = (ROOT / 'src/ui/RetainedUI.cpp').read_text(encoding='utf-8')
    source = directory / 'faces.cpp'
    binary = directory / 'faces.exe'
    source.write_text(FACES + function_body(host, 'static std::string FontFamily(') + '\n' +
                      function_body(host, 'static std::uint32_t RuneScalar(') + FACES_MAIN, encoding='utf-8')
    subprocess.run([compiler, '-std=c++20', '-Wall', '-Wextra', str(source), '-o', str(binary)], check=True)
    shipped = set()
    for table in (ROOT / 'content/baseoq4/pak0/strings').glob('*.lang'):
        shipped.update(ord(ch) for ch in table.read_text(encoding='utf-8'))
    scalars = sorted(shipped | {s for s in range(0x20, 0x10000) if not 0xD800 <= s <= 0xDFFF})
    result = subprocess.run([str(binary)], input='\n'.join(map(str, scalars)), capture_output=True, text=True, timeout=60, check=True)
    lines = result.stdout.splitlines()
    families = dict(line.split()[1:] for line in lines if line.startswith('family '))
    assert families == {'marine': 'marine', 'lowpixel': 'lowpixel', 'r_strogg': 'r_strogg', 'strogg': 'strogg',
                        'chain': 'chain', 'Marine': 'chain', 'unknown': 'chain'}, families
    runes = font_code_points(ROOT / 'content/baseoq4/pak0/fonts/strogg.ttf')
    folded = dict(tuple(map(int, line.split())) for line in lines if not line.startswith('family '))
    assert set(folded) == set(scalars)
    missing = sorted(hex(s) for s, f in folded.items() if f != 0x20 and f not in runes)
    assert not missing, f'rune copies would draw the face\'s ? for {missing[:16]}'
    assert all(folded[s] == s for s in range(0x41, 0x5B)) and all(folded[s] == s for s in range(0x30, 0x3A)), 'letters and digits keep their runes'
    for blank in (0x21, 0x2019, 0x2026, 0x300, 0x3000):
        assert folded[blank] == 0x20, f'punctuation U+{blank:04X} must be blank in the runes'
    return len(scalars)


def main() -> int:
    menu = (ROOT / 'src/framework/Session_menu.cpp').read_text(encoding='utf-8')
    session = (ROOT / 'src/framework/Session.cpp').read_text(encoding='utf-8')
    adapter = (ROOT / 'src/ui/UserInterfaceRetained.cpp').read_text(encoding='utf-8')

    # The gate itself: on by default and archived, so a player's choice of the
    # stock screens persists.
    assert 'idCVar ui_retained( "ui_retained", "1", CVAR_GUI | CVAR_BOOL | CVAR_ARCHIVE, ' in menu, 'ui_retained must default to 1 and be archived'
    assert 'ui_retainedSystem( "ui_retainedSystem", "0", CVAR_GUI | CVAR_BOOL' in menu
    assert 'return ui_retainedSystem.GetBool() || ( Session_RetainedScreensEnabled() && RETAINED_SYSTEM_MISSING_SETTINGS[0] == NULL );' in menu
    # The SYSTEM page joins the gate once it has a control for every setting of
    # the stock page; the list of what it lacks must say exactly that.
    missing = re.search(r'RETAINED_SYSTEM_MISSING_SETTINGS\[\] = \{([^}]*)\};', menu).group(1)
    listed = {name.lower() for name in re.findall(r'"([A-Za-z_0-9]+)"', missing)}
    assert missing.strip().endswith('NULL'), 'the missing-settings list must stay NULL-terminated'
    # CVar names are case-insensitive (the stock page binds r_multisamples).
    actual = {name.lower() for name in stock_system_settings()} - {name.lower() for name in retained_system_controls()}
    assert listed == actual, f'RETAINED_SYSTEM_MISSING_SETTINGS lists {sorted(listed)}; the retained SYSTEM page lacks {sorted(actual)}'
    assert 'if ( !Session_RetainedSystemEnabled() || systemGuiTransition' in function_body(menu, 'bool idSessionLocal::OpenSystemSettings(')
    assert 'guiMainMenu->SetStateBool( "retainedSystem", RetainedSystemAvailable() );' in menu
    # Every retained document path in the session is behind the gate.
    for source, name in ((menu, 'Session_menu.cpp'), (session, 'Session.cpp')):
        for match in re.finditer(r'"([^"]+\.q4ui)"', source):
            path = match.group(1)
            allowed = {'guis/menu/settings/system.q4ui', 'guis/menu/title.q4ui', 'guis/menu/pause.q4ui', 'guis/menu/pause_strogg.q4ui',
                       'guis/loading/loading.q4ui', 'guis/menu/singleplayer.q4ui', 'guis/menu/campaigns.q4ui'}
            assert path in allowed, f'{name} names an ungated retained document {path}'
    # Every retained document loads through FindRetainedGui, which falls back to
    # the stock screen; the SYSTEM page and the campaign selectors fall back too.
    assert not re.search(r'uiManager->FindGui\(\s*(?:RETAINED_|"[^"]+\.q4ui")', menu + session), 'retained documents load only through FindRetainedGui'
    find_retained = function_body(menu, 'idUserInterface *idSessionLocal::FindRetainedGui(')
    assert 'uiManager->FindGui( path, true, !shared, shared )' in find_retained and 'retainedStock.Append( path );' in find_retained
    system_open = function_body(menu, 'bool idSessionLocal::OpenSystemSettings(')
    assert 'FindRetainedGui( RETAINED_SYSTEM_GUI, false, false )' in system_open and 'retainedStock.Append( RETAINED_SYSTEM_GUI );' in system_open
    main_menu = function_body(menu, 'void idSessionLocal::HandleMainMenuCommands(')
    system_click = main_menu[main_menu.index('if ( !idStr::Icmp( cmd, "openRetainedSystem" ) ) {'):]
    system_click = system_click[:system_click.index('return;')]
    assert 'if ( !OpenSystemSettings() && !RetainedSystemAvailable() ) {' in system_click
    assert 'UI_RunLegacyWindowAction( guiMainMenu, "set_b_system", false, command )' in system_click, 'a failed SYSTEM page must open the stock one'
    home_document = function_body(menu, 'idUserInterface *idSessionLocal::RetainedHomeDocument(')
    assert 'UI_RetainedViewFailed( home )' in home_document and 'retainedStock.AddUnique( path );' in home_document
    assert 'retainedStock.Clear();' in function_body(session, 'void idSessionLocal::Clear(')
    campaign_selector = function_body(menu, 'void idSessionLocal::OpenCampaignSelector(')
    assert 'Session_RetainedScreensEnabled() ?' in campaign_selector and 'arenaCampaign.OpenSelector();' in campaign_selector
    assert 'FindGui( "guis/campaign_menu.gui"' in campaign_selector
    assert menu.count('RETAINED_TITLE_GUI') == 3 and menu.count('RETAINED_PAUSE_GUI') == 4 and menu.count('RETAINED_LOADING_GUI') == 2
    assert menu.count('RETAINED_PAUSE_STROGG_GUI') == 3
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
    # The Strogg pause: the session asks the game the command the game answers.
    game = (ROOT / 'src/game/Game_local.cpp').read_text(encoding='utf-8')
    assert 'game->HandleMainMenuCommands( "retainedPauseFamily", guiMainMenu );' in function_body(menu, 'bool idSessionLocal::RetainedPauseIsStrogg(')
    family = game[game.index('!idStr::Icmp( menuCommand, "retainedPauseFamily" )'):]
    family = family[:family.index('}')]
    assert 'gui->SetStateBool( "pause_strogg", player != NULL && player->spawnArgs.GetBool( "strogg" ) );' in family
    assert 'retainedPauseStrogg = -1;' in function_body(menu, 'void idSessionLocal::PrepareRetainedLevel(')
    # The Objectives page's screenshots resolve inside the load, after the game
    # spawns the map and before the media are finished.
    change = function_body(session, 'void idSessionLocal::ExecuteMapChange(')
    assert change.index('game->SpawnPlayer( i, false, NULL );') < change.index('PrecacheRetainedLevelImages();') < \
        change.index('renderSystem->EndLevelLoad();') < change.index('declManager->EndLevelLoad();')
    images = game[game.index('!idStr::Icmp( menuCommand, "retainedLevelImages" )'):]
    assert 'ent->IsType( idObjective::GetClassType() )' in images[:images.index('gui->SetStateInt( "level_image_count", images );')]
    assert 'player->inventory.objectiveNames[ i ].screenshot' in images[:images.index('gui->SetStateInt( "level_image_count", images );')]
    draw = session[session.index('} else if ( mapSpawned ) {'):]
    draw = draw[:draw.index('} else {')]
    assert draw.index('gameDraw = game->Draw( GetLocalClientNum() );') < draw.index('renderSystem->WriteDemoPics();') < \
        draw.index('guiRetainedReleasing->Redraw( presentationTime );')
    assert session.count('guiRetainedReleasing->Redraw(') == 1
    release_ms = int(re.search(r'static const int RETAINED_RELEASE_MSEC = (\d+);', menu).group(1))
    for name in ('pause', 'pause_strogg'):
        text = (ROOT / f'content/baseoq4/pak0/guis/menu/{name}.q4ui').read_text(encoding='utf-8')
        document = json.loads(re.sub(r'^\s*//.*$', '', text, flags=re.M))
        release = next(item for item in document['timelines'] if item['id'] == 'release')
        assert release['durationMs'] == release_ms, name
        # Every activation after a release shows the screen again, whether
        # open or returnHome follows.
        reset = document['events']['onActivate'][0]
        assert reset['op'] == 'if' and reset['condition'] == {'state': 'pause.released'}, name
        assert {'op': 'setState', 'values': {'pause.released': False}} in reset['then'], name
    saving = function_body(session, 'bool idSessionLocal::SaveGame(')
    assert saving.index('operationGuard.Complete();') < saving.index('retainedNewestSave = time( NULL );') < saving.index('return true;', saving.index('operationGuard.Complete();'))

    # Documents: current with their generator, verbs allowlisted and handled.
    generator = subprocess.run([sys.executable, str(ROOT / 'tools/ui/build_retained_screens.py'), '--check'], capture_output=True, text=True)
    assert generator.returncode == 0, generator.stderr
    allowlist = cpp_allowlist(adapter)
    handled = set(re.findall(r'\{ "([A-Za-z][A-Za-z0-9]*)",\s+"main_b_', menu)) | set(re.findall(r'!idStr::Icmp\( request, "([A-Za-z][A-Za-z0-9]*)" \)', menu))
    assert allowlist == handled, f'allowlist {sorted(allowlist)} differs from session handlers {sorted(handled)}'
    for relative in ('content/baseoq4/pak0/guis/menu/title.q4ui', 'content/baseoq4/pak0/guis/menu/pause.q4ui',
                     'content/baseoq4/pak0/guis/menu/pause_strogg.q4ui', 'content/baseoq4/pak0/guis/loading/loading.q4ui',
                     'content/baseoq4/pak0/guis/menu/singleplayer.q4ui', 'content/baseoq4/pak0/guis/menu/campaigns.q4ui'):
        text = (ROOT / relative).read_text(encoding='utf-8')
        document = json.loads(re.sub(r'^\s*//.*$', '', text, flags=re.M))
        assert document.get('canvas') == {'height': 720}, relative
        if 'pause' in relative:
            assert [child['id'] for child in document['root']['children']] == ['scene-softfocus', 'scrim', 'chrome'], relative
            layers = [child['id'] for child in document['root']['children'][2]['children']]
            assert layers.index('objectives-bar') < layers.index('band-top') < layers.index('objectives'), relative
        for action in document.get('actions', {}).values():
            assert action['operation'] == 'session.menu' and action['arguments']['command'] in allowlist, relative
    # No game or legacy content names a retained document.
    for folder in (ROOT / 'content', ROOT / 'src/game', ROOT / 'src/mpgame'):
        if not folder.exists():
            continue
        for path in folder.rglob('*'):
            if path.suffix.lower() in {'.gui', '.def', '.cfg', '.script', '.mtr', '.cpp', '.h'} and path.is_file():
                assert '.q4ui' not in path.read_text(encoding='utf-8', errors='replace'), f'{path} names a retained document'

    # Behaviour: the production session code against counted doubles.
    start = menu.index('static const char *const RETAINED_TITLE_GUI')
    tables = menu[start:menu.index('// Legacy pop-ups drawn over the home state', start)]
    gate_start = menu.index('static bool Session_RetainedScreensEnabled( void ) {')
    gate_functions = menu[gate_start:menu.index('static const int MENU_CONTROLLER_AXIS_THRESHOLD', gate_start)]
    assert 'RETAINED_SYSTEM_GUI' in gate_functions
    bodies = [gate_functions, tables] + [function_body(menu, signature) for signature in (
        'static bool Session_RetainedHomePopup(', 'static const char *Session_RetainedHomeMissingPage(',
        'static void Session_PublishRetainedTitleState(', 'idUserInterface *idSessionLocal::FindRetainedGui(',
        'bool idSessionLocal::RetainedSystemAvailable(', 'void idSessionLocal::OpenCampaignSelector(',
        'bool idSessionLocal::RetainedHomeInputBlocked(',
        'void idSessionLocal::UpdateRetainedHome(', 'idUserInterface *idSessionLocal::RetainedHomeDocument(',
        'bool idSessionLocal::RetainedPauseIsStrogg(', 'void idSessionLocal::RetainedHomeFrameEvent(',
        'void idSessionLocal::HandleRetainedSessionRequest(', 'idUserInterface *idSessionLocal::SelectRetainedLoadingGui(',
        'void idSessionLocal::PreloadRetainedScreens(', 'void idSessionLocal::PrepareRetainedLevel(',
        'void idSessionLocal::ReportRetainedScreens(')]
    bodies += [function_body(session, signature) for signature in (
        'static bool Session_ImageInstalled(', 'idStr idSessionLocal::RetainedPauseShot(',
        'void idSessionLocal::PrecacheRetainedLevelImages(', 'static idStr Session_RetainedSaveAge(',
        'void idSessionLocal::PublishRetainedPauseState(')]
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
        if result.returncode == 0:
            print(f'ui_retained gate: the Strogg faces resolve and {check_strogg_faces(compiler, Path(directory))} code points fold onto the rune face')
        return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
