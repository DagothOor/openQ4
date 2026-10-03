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
#include <algorithm>
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
#define BASE_GAMEDIR "q4base"
#define OPENQ4_GAMEDIR "baseoq4"
struct idFile {};
struct CVarSystem {
    std::map<std::string, std::string> strings;
    const char* GetCVarString(const char* name) const { const auto found = strings.find(name); return found == strings.end() ? "" : found->second.c_str(); }
    bool GetCVarBool(const char* name) const { return std::string(GetCVarString(name)) == "1"; }
} cvarSystemObject, *cvarSystem = &cvarSystemObject;
struct FileSystem {
    std::set<std::string> files;
    std::map<std::string, std::set<std::string>> gameDirFiles; // what each game directory itself supplies
    idFile file; int opens = 0, closes = 0;
    idFile* OpenFileRead(const char* path, bool, const char* gameDir) {
        ++opens; const auto found = gameDirFiles.find(gameDir ? gameDir : "");
        return found != gameDirFiles.end() && found->second.count(path) ? &file : nullptr;
    }
    void CloseFile(idFile* opened) { if (opened == &file) ++closes; }
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
enum { SE_NONE = 0, CMD_EXEC_APPEND = 1, SE_KEY = 2, SE_MOUSE = 3 };
enum { K_ESCAPE = 27, K_ENTER = 13, K_JOY4 = 200, K_JOY7 = 203, K_JOY8 = 204 };
struct sysEvent_t { int evType = SE_NONE, evValue = 0, evValue2 = 0; };
struct idUserInterface {
    std::string source; bool active = false, failed = false; int activations = 0, deactivations = 0;
    std::vector<std::string> named; std::map<std::string, std::string> state;
    explicit idUserInterface(const char* name) : source(name) {}
    const char* Name() const { return source.c_str(); }
    const char* Activate(bool value, int) { active = value; ++(value ? activations : deactivations); return ""; }
    void HandleNamedEvent(const char* name) { named.push_back(name); }
    std::vector<sysEvent_t> events;
    const char* HandleEvent(const sysEvent_t* event, int) { events.push_back(*event); return ""; }
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
    void SetCursor(float x, float y) { cursorX = x; cursorY = y; }
    void StateChanged(int) {}
};
enum { AXIS_SIDE = 0, AXIS_FORWARD = 1 };
static int stickX = 0, stickY = 0;
static bool vrInputFocus = false;
static bool VR_HasInputFocus() { return vrInputFocus; }
static bool Sys_GetJoystickAxisState(int axis, int& value) { value = axis == AXIS_SIDE ? stickX : stickY; return true; }
static int MenuControllerAbs(int value) { return value < 0 ? -value : value; }
struct idMath {
    static float ClampFloat(float low, float high, float value) { return value < low ? low : value > high ? high : value; }
    static float Fabs(float value) { return value < 0 ? -value : value; }
    static int ClampInt(int low, int high, int value) { return value < low ? low : value > high ? high : value; }
};
static int sysMilliseconds = 0;
static int Sys_Milliseconds() { return sysMilliseconds; }
struct Manager {
    std::vector<std::unique_ptr<idUserInterface>> storage; std::vector<std::string> loads; bool fail = false;
    struct Flags { bool autoLoad, unique, shared; }; std::vector<Flags> flags;
    idUserInterface* FindGui(const char* path, bool autoLoad, bool unique, bool shared) {
        loads.push_back(path); flags.push_back({autoLoad, unique, shared});
        if (fail) return nullptr;
        if (shared && !unique)  // the manager keeps one shared instance per path
            for (const auto& gui : storage) if (gui->source == path) return gui.get();
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
    idUserInterface* retainedSubpageFrom = nullptr; bool retainedSubpageDeeper = false; int retainedSubpageBegan = 0, retainedSubpageUntil = 0;
    idUserInterface* guiLoading = nullptr; bool retainedLoadingActive = false;
    int retainedLoadingTip = -1, retainedLoadingTipSlot = 0, retainedLoadingTipAt = 0; void PublishRetainedLoadingTip(bool);
    void BeginRetainedSubpage(idUserInterface*, bool); void UpdateRetainedSubpage(); bool RetainedSubpageEvent(const sysEvent_t*);
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
    std::vector<std::string> selected; int menus = 0;
    void SelectCampaign(const char* campaign) { selected.push_back(campaign); }
    void StartMenu() { ++menus; }
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
    fileSystemObject.gameDirFiles.clear(); fileSystemObject.opens = fileSystemObject.closes = 0; cvarSystemObject = CVarSystem{};
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
        // The VR pointer moves by its offset from the covered menu's cursor:
        // in VR that cursor follows the screen's, and only in VR.
        CHECK(s.guiMainMenu->cursorX == 320 && s.guiMainMenu->cursorY == 240);
        vrInputFocus = true; s.RetainedHomeFrameEvent(); vrInputFocus = false;
        CHECK(s.guiMainMenu->cursorX == 640 && s.guiMainMenu->cursorY == 120);
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
    {   // A mod's own copy of a stock loading screen stays; the stock screens of
        // openQ4, the stock game and the Awakening are replaced.
        auto s = Session(true); idUserInterface splevel("guis/loading/splevel.gui"), mplevel("guis/loading/mplevel.gui");
        cvarSystemObject.strings["fs_game"] = "mymod";
        fileSystemObject.gameDirFiles["mymod"] = {"guis/loading/splevel.gui"};
        CHECK(s.SelectRetainedLoadingGui(&splevel, false) == &splevel && managerObject.loads.empty() && commonObject.warnings.empty());
        CHECK(fileSystemObject.closes == 1 && commonObject.developer.size() == 1 &&
              commonObject.developer[0].find("'guis/loading/splevel.gui'") != std::string::npos);
        CHECK(s.SelectRetainedLoadingGui(&mplevel, true) != &mplevel);  // a stock screen the mod does not ship
        auto based = Session(true); idUserInterface intro("guis/loading/intro.gui");
        cvarSystemObject.strings["fs_game"] = "mymod"; cvarSystemObject.strings["fs_game_base"] = "mybase";
        fileSystemObject.gameDirFiles["mybase"] = {"guis/loading/intro.gui"};
        CHECK(based.SelectRetainedLoadingGui(&intro, false) == &intro);  // the mod's own base supplies it
        for (const char* firstParty : {"baseoq4", "q4base", "q4xbase", "Q4XBASE"}) {
            auto own = Session(true); idUserInterface generic("guis/loading/generic.gui");
            cvarSystemObject.strings["fs_game"] = firstParty; fileSystemObject.gameDirFiles[firstParty] = {"guis/loading/generic.gui"};
            CHECK(own.SelectRetainedLoadingGui(&generic, false) != &generic && fileSystemObject.opens == 0);
        }
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
    {   // Single player loading tips: the first when the screen presents, then the
        // next every 6 s in the other slot; multiplayer runs the arsenal instead.
        auto s = Session(true); idUserInterface loading("guis/loading/loading.q4ui"); s.guiLoading = &loading;
        s.PublishRetainedLoadingTip(true); CHECK(loading.named.empty());  // not presenting the load
        s.retainedLoadingActive = true; sysMilliseconds = 5;
        s.PublishRetainedLoadingTip(true);
        const std::string first = loading.state["loading_tip_a"];
        CHECK(loading.named.back() == "tipA" && first.rfind("#str_", 0) == 0 && loading.state["loading_tip_b"].empty());
        commonObject.time += 5999; s.PublishRetainedLoadingTip(false); CHECK(loading.named.size() == 1);
        commonObject.time += 1; s.PublishRetainedLoadingTip(false);
        const std::string second = loading.state["loading_tip_b"];
        CHECK(loading.named.back() == "tipB" && second.rfind("#str_", 0) == 0 && second != first && loading.state["loading_tip_a"] == first);
        commonObject.time += 6000; s.PublishRetainedLoadingTip(false);
        CHECK(loading.named.back() == "tipA" && loading.state["loading_tip_a"] != first && loading.state["loading_tip_a"] != second);
        sysMilliseconds = 6; s.PublishRetainedLoadingTip(true);  // a new load starts elsewhere in the list
        CHECK(loading.state["loading_tip_a"] != first && loading.state["loading_tip_b"].empty() && loading.named.back() == "tipA");
        loading.state["loading_mp"] = "1"; const size_t events = loading.named.size(); commonObject.time += 6000;
        s.PublishRetainedLoadingTip(false); s.PublishRetainedLoadingTip(true); CHECK(loading.named.size() == events);
    }
    {   // Single Player and its Campaign sub-page (spec 1.10): the leaving document
        // plays its half, the other presents at the hand-over (350 ms deeper, 300 ms
        // on Back), and input waits for it.
        auto s = Session(true); s.OpenCampaignSelector(false); auto* page = s.guiActive;
        s.HandleRetainedSessionRequest(page, "campaigns");
        CHECK(s.guiActive == page && page->named.back() == "subpageEnter" && s.retainedSubpageFrom == page && s.retainedSubpageDeeper);
        CHECK(s.retainedSubpageUntil == commonObject.time + 350);
        const size_t enterEvents = page->named.size();
        s.HandleRetainedSessionRequest(page, "campaignArena"); s.HandleRetainedSessionRequest(page, "campaigns");
        CHECK(s.guiActive == page && s.selected.empty() && page->named.size() == enterEvents);  // no second request mid-change
        // Input waits: a press is held, a release still reaches the page.
        sysEvent_t press; press.evType = SE_KEY; press.evValue = K_ENTER; press.evValue2 = 1;
        sysEvent_t release = press; release.evValue2 = 0;
        CHECK(s.RetainedSubpageEvent(&press) && page->events.empty());
        CHECK(s.RetainedSubpageEvent(&release) && page->events.size() == 1 && page->events[0].evValue2 == 0);
        commonObject.time += 349; s.UpdateRetainedSubpage(); CHECK(s.guiActive == page);
        commonObject.time += 1; s.UpdateRetainedSubpage(); auto* sub = s.guiActive;
        CHECK(sub && std::string(sub->Name()) == "guis/menu/campaigns.q4ui" && s.retainedSubpageFrom == nullptr);
        CHECK(!s.RetainedSubpageEvent(&press));  // the sub-page takes input again
        s.HandleRetainedSessionRequest(sub, "campaignBack");
        CHECK(s.guiActive == sub && sub->named.back() == "subpageLeave" && !s.retainedSubpageDeeper && s.retainedSubpageUntil == commonObject.time + 300);
        sysEvent_t back = press; back.evValue = K_ESCAPE;
        CHECK(s.RetainedSubpageEvent(&back) && s.retainedSubpageFrom == sub);  // Back does not reverse a Back
        commonObject.time += 300; s.UpdateRetainedSubpage();
        CHECK(s.guiActive == page && page->named.back() == "subpageReturn");
        // Back while going deeper reverses the change from where it stands, by
        // the distance the band has stepped since 50 ms: 150 ms at least ...
        s.HandleRetainedSessionRequest(page, "campaigns"); commonObject.time += 120;
        CHECK(s.RetainedSubpageEvent(&back) && page->named.back() == "subpageReverse150" && s.retainedSubpageFrom == nullptr && s.guiActive == page);
        s.UpdateRetainedSubpage(); CHECK(s.guiActive == page);
        // ... and 250 ms once it has stepped most of the way.
        s.HandleRetainedSessionRequest(page, "campaigns"); commonObject.time += 280;
        sysEvent_t pad = back; pad.evValue = K_JOY4;
        CHECK(s.RetainedSubpageEvent(&pad) && page->named.back() == "subpageReverse250");
        // Reduced motion hands over at once: the arrival's 80 ms fade is the change.
        cvarSystemObject.strings["ui_retainedReducedMotion"] = "1";
        s.HandleRetainedSessionRequest(page, "campaigns");
        CHECK(std::string(s.guiActive->Name()) == "guis/menu/campaigns.q4ui" && s.retainedSubpageFrom == nullptr && page->named.back() != "subpageEnter");
        s.HandleRetainedSessionRequest(s.guiActive, "campaignBack");
        CHECK(s.guiActive == page && page->named.back() == "subpageReturn" && s.retainedSubpageFrom == nullptr);
        cvarSystemObject.strings["ui_retainedReducedMotion"] = "0";
        // Anything else taking the screen abandons the change.
        s.HandleRetainedSessionRequest(page, "campaigns");
        idUserInterface other("guis/msg.gui"); s.guiActive = &other; s.UpdateRetainedSubpage();
        CHECK(s.retainedSubpageFrom == nullptr && s.guiActive == &other);
        // A sub-page that cannot present: its stock selector opens at once.
        auto stock = Session(true); stock.OpenCampaignSelector(false); auto* alone = stock.guiActive;
        fileSystemObject.files.erase("guis/menu/campaigns.q4ui");
        stock.HandleRetainedSessionRequest(alone, "campaigns");
        CHECK(std::string(stock.guiActive->Name()) == "guis/campaign_menu.gui" && stock.retainedSubpageFrom == nullptr && alone->named.empty());
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
    for (const char* family : {"marine", "lowpixel", "profont", "r_strogg", "strogg", "chain", "Marine", "unknown"})
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
    assert families == {'marine': 'marine', 'lowpixel': 'lowpixel', 'profont': 'profont', 'r_strogg': 'r_strogg', 'strogg': 'strogg',
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


CARD = r"""
#include <cctype>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <string>
#include <vector>
static int checks = 0;
#define CHECK(x) do { ++checks; if (!(x)) { std::fprintf(stderr, "check failed line %d: %s\n", __LINE__, #x); std::abort(); } } while (false)
#define BIT(n) (1 << (n))
#define S_ESCAPE_UNKNOWN BIT(0)
#define S_ESCAPE_COLOR BIT(1)
#define S_ESCAPE_COLORINDEX BIT(2)
#define S_ESCAPE_ICON BIT(3)
#define S_ESCAPE_COMMAND BIT(4)
#define S_ESCAPE_ALL ( S_ESCAPE_COLOR | S_ESCAPE_COLORINDEX | S_ESCAPE_ICON | S_ESCAPE_COMMAND )
const int C_COLOR_ESCAPE = '^';
class idStr {
public:
    std::string s;
    idStr() = default;
    idStr(const char* text) : s(text ? text : "") {}
    int Length() const { return static_cast<int>(s.size()); }
    const char* c_str() const { return s.c_str(); }
    char operator[](int i) const { return i >= 0 && i < Length() ? s[i] : '\0'; }
    idStr& operator+=(char c) { s += c; return *this; }
    idStr& operator+=(const char* text) { s += text; return *this; }
    idStr& operator+=(const idStr& text) { s += text.s; return *this; }
    void Append(const char* text, int length) { s.append(text, length); }
    void CapLength(int length) { if (length < Length()) s.resize(length); }
    void Insert(char c, int index) { s.insert(s.begin() + index, c); }
    static int IsEscape(const char* s, int* type = nullptr);
    static char* RemoveEscapes(char* string, int escapes = S_ESCAPE_ALL);
    // As Str.h: the static form over the buffer, then the length again.
    idStr& RemoveEscapes(int escapes = S_ESCAPE_ALL) {
        std::vector<char> buffer(s.begin(), s.end()); buffer.push_back('\0');
        RemoveEscapes(buffer.data(), escapes); s = buffer.data(); return *this;
    }
    static int Icmpn(const char* a, const char* b, int n) {
        for (int i = 0; i < n; ++i) {
            const int x = std::tolower(static_cast<unsigned char>(a[i])), y = std::tolower(static_cast<unsigned char>(b[i]));
            if (x != y) return x - y;
            if (!x) return 0;
        }
        return 0;
    }
    static int Icmp(const char* a, const char* b) { return Icmpn(a, b, 1 << 30); }
};
struct idDict {
    std::map<std::string, std::string> values;
    void Set(const char* key, const char* value) { values[key] = value; }
    const char* GetString(const char* key, const char* fallback = "") const {
        const auto found = values.find(key); return found == values.end() ? fallback : found->second.c_str();
    }
};
struct idUserInterface {
    std::map<std::string, std::string> state; int changes = 0;
    void SetStateString(const char* key, const char* value) { state[key] = value; }
    void SetStateBool(const char* key, bool value) { state[key] = value ? "1" : "0"; }
    void SetStateInt(const char* key, int value) { state[key] = std::to_string(value); }
    struct View {
        const std::map<std::string, std::string>& values;
        bool GetBool(const char* key) const { const auto found = values.find(key); return found != values.end() && std::atoi(found->second.c_str()) != 0; }
    };
    View State() const { return {state}; }
    void StateChanged(int) { ++changes; }
};
// The game module: game_mp answers the verb from the server info it is given.
struct Game {
    bool answers = true; std::vector<std::string> verbs;
    void HandleMainMenuCommands(const char* verb, idUserInterface* gui) {
        verbs.push_back(verb);
        if (!answers || std::strcmp(verb, "retainedLoadingServer")) return;
        const std::string mode = gui->state["query_si_gameType"];
        const bool teams = mode == "Team DM" || mode == "CTF";
        gui->SetStateString("server_gametype", teams ? "Team Deathmatch" : "Deathmatch");
        gui->SetStateString("server_limit", ("Frag Limit " + gui->state["query_si_fragLimit"]).c_str());
        gui->SetStateBool("server_team_mode", teams);
        gui->SetStateBool("server_answered", true);
    }
} gameObject, *game = &gameObject;
struct LangDict {
    const char* GetString(const char* key) const {
        static const std::map<std::string, std::string> table = {
            {"#str_230070", "+%d more"}, {"#str_230071", "Connecting: %d"}, {"#str_230072", "Spectating: %d"}};
        const auto found = table.find(key); return found == table.end() ? key : found->second.c_str();
    }
} languageObject;
struct Common {
    std::string output;
    const LangDict* GetLanguageDict() { return &languageObject; }
    int GetPresentationTime() { return 0; }
    void Printf(const char* fmt, ...) { char text[1024]; va_list args; va_start(args, fmt); std::vsnprintf(text, sizeof(text), fmt, args); va_end(args); output += text; }
} commonObject, *common = &commonObject;
struct CVarSystem { bool GetCVarBool(const char*) { return true; } } cvarSystemObject, *cvarSystem = &cvarSystemObject;
// idlib's va: four rotating buffers, so one call may nest another.
static const char* va(const char* fmt, ...) {
    static char buffers[4][1024]; static int index = 0; char* text = buffers[index++ & 3];
    va_list args; va_start(args, fmt); std::vsnprintf(text, 1024, fmt, args); va_end(args); return text;
}
class idSessionLocal {
public:
    idUserInterface* guiLoading = nullptr;
    static const int RETAINED_ROSTER_SLOTS = @SLOTS@;
    idStr retainedRosterName[RETAINED_ROSTER_SLOTS];
    int retainedRosterTeam[RETAINED_ROSTER_SLOTS] = {};
    int retainedRosterCount = 0, retainedRosterConnecting = 0;
    bool retainedRosterKnown = false;
    void ClearRetainedLoadingRoster(); void NoteRetainedLoadingPlayer(const idDict&); void NoteRetainedLoadingConnecting(int);
    void PublishRetainedLoadingServer(const idDict&);
};
"""

CARD_MAIN = r"""
static idDict Player(const char* name, const char* team = "Marine", const char* spectate = "Play") {
    idDict info; info.Set("ui_name", name); info.Set("ui_team", team); info.Set("ui_spectate", spectate); return info;
}
static std::string Clean(const char* text, int bytes = 256, int lines = 3) { return Session_RetainedPlayerText(text, bytes, lines).s; }
int main() {
    // The sanitizer: Quake 4's own escape grammar, then lines, bytes and UTF-8.
    CHECK(Clean("^1Red^7Name") == "RedName");
    CHECK(Clean("^c683Marine^iabcX^nqY^r") == "MarineXY");
    CHECK(Clean("100^^ fun") == "100^ fun");
    CHECK(Clean("One\nTwo\nThree\nFour", 256, 3) == "One\nTwo\nThree Four");
    CHECK(Clean("\n\nHello\n\n") == "Hello");
    CHECK(Clean("C:\\maps /n") == "C:\\maps /n");  // a backslash is text, as the console never sends one
    CHECK(Clean("Tab\there\x01\x7f!") == "Tab here!");
    CHECK(Clean("Line\none\ntwo", 256, 1) == "Line one two");
    CHECK(Clean("\xc3\x84\xc3\x84\xc3\x84", 5) == "\xc3\x84\xc3\x84");
    CHECK(Clean("a\xc3(b\xe2\x82") == "a(b");
    CHECK(Clean("\x80\xbf ok \xf8!") == "ok !");
    CHECK(Clean("#str_200197") == " #str_200197");
    CHECK(Clean("^2#str_1") == " #str_1");
    CHECK(Clean(nullptr).empty() && Clean("^7").empty());
    // At most the bytes asked for, never a split character, never more lines.
    for (int bytes = 0; bytes < 12; ++bytes) {
        const std::string text = Clean("Zo\xc3\xab \xd0\x96\xe2\x82\xac\xf0\x9f\x98\x80!", bytes);
        CHECK(static_cast<int>(text.size()) <= bytes);
        for (size_t i = 0; i < text.size(); ) {
            const unsigned char lead = static_cast<unsigned char>(text[i]);
            const size_t length = lead >= 0xf0 ? 4 : lead >= 0xe0 ? 3 : lead >= 0xc0 ? 2 : 1;
            CHECK(lead < 0x80 || lead >= 0xc0);
            CHECK(i + length <= text.size());
            i += length;
        }
    }
    idUserInterface loading; idSessionLocal session; session.guiLoading = &loading;
    idDict server; server.Set("si_gameType", "Team DM"); server.Set("si_fragLimit", "30");
    server.Set("si_motd", "^3Welcome^7 to the ^1test^7 server\nBe excellent");
    // A team match: three marines, two strogg, a spectator and two connecting.
    session.ClearRetainedLoadingRoster();
    for (const char* name : {"^1Kane", "Rhodes", "Strauss"}) session.NoteRetainedLoadingPlayer(Player(name));
    session.NoteRetainedLoadingPlayer(Player("Makron", "Strogg"));
    session.NoteRetainedLoadingPlayer(Player("Gladiator", "strogg"));
    session.NoteRetainedLoadingPlayer(Player("Watcher", "Marine", "Spectate"));
    session.NoteRetainedLoadingPlayer(Player("^7"));  // a name that is only escapes
    session.NoteRetainedLoadingConnecting(2);
    session.PublishRetainedLoadingServer(server);
    CHECK(gameObject.verbs.size() == 1 && gameObject.verbs[0] == "retainedLoadingServer");
    CHECK(loading.state["query_si_gameType"] == "Team DM" && loading.state["query_si_fragLimit"] == "30");
    CHECK(loading.state["server_gametype"] == "Team Deathmatch" && loading.state["server_limit"] == "Frag Limit 30");
    CHECK(loading.state["server_roster_known"] == "1" && loading.state["server_team_mode"] == "1");
    CHECK(loading.state["server_team_a"] == "Kane\nRhodes\nStrauss" && loading.state["server_team_b"] == "Makron\nGladiator");
    CHECK(loading.state["server_players"].empty() && loading.state["server_roster_rows"] == "3");
    CHECK(loading.state["server_roster_extra"] == "Spectating: 1 \xc2\xb7 Connecting: 2");
    CHECK(loading.state["server_message"] == "Welcome to the test server\nBe excellent");
    CHECK(loading.changes == 1);
    CHECK(commonObject.output.find("RETAINED_LOADING_SERVER answered=1 teams=1 players=5 spectators=1 connecting=2 rows=3 message=") != std::string::npos);
    // Each load captures its own roster.
    CHECK(session.retainedRosterCount == 0 && session.retainedRosterConnecting == 0 && !session.retainedRosterKnown);
    // Eight marines: six names, then "+2 more" as the seventh row.
    for (int i = 0; i < 8; ++i) session.NoteRetainedLoadingPlayer(Player(("M" + std::to_string(i)).c_str()));
    session.PublishRetainedLoadingServer(server);
    CHECK(loading.state["server_team_a"] == "M0\nM1\nM2\nM3\nM4\nM5\n+2 more" && loading.state["server_team_b"].empty());
    CHECK(loading.state["server_roster_rows"] == "7" && loading.state["server_roster_extra"].empty());
    // Outside team modes one list holds everyone, whatever their ui_team.
    server.Set("si_gameType", "DM");
    session.NoteRetainedLoadingPlayer(Player("A")); session.NoteRetainedLoadingPlayer(Player("B", "Strogg"));
    session.PublishRetainedLoadingServer(server);
    CHECK(loading.state["server_team_mode"] == "0" && loading.state["server_players"] == "A\nB" && loading.state["server_roster_rows"] == "2");
    // A game that does not answer keeps the session's strings and one list.
    gameObject.answers = false; loading.state["server_gametype"] = "Team DM (session)";
    server.Set("si_gameType", "Team DM");
    session.NoteRetainedLoadingPlayer(Player("A")); session.NoteRetainedLoadingPlayer(Player("B", "Strogg"));
    session.PublishRetainedLoadingServer(server);
    CHECK(loading.state["server_gametype"] == "Team DM (session)" && loading.state["server_team_mode"] == "0");
    CHECK(loading.state["server_players"] == "A\nB" && loading.state["server_team_a"].empty());
    gameObject.answers = true;
    // A load that knows no players (a fresh connection) shows none.
    session.PublishRetainedLoadingServer(server);
    CHECK(loading.state["server_roster_known"] == "0" && loading.state["server_roster_rows"] == "0");
    // Only players still connecting: the line stands alone.
    session.NoteRetainedLoadingConnecting(3);
    session.PublishRetainedLoadingServer(server);
    CHECK(loading.state["server_roster_known"] == "1" && loading.state["server_roster_rows"] == "0" &&
          loading.state["server_roster_extra"] == "Connecting: 3");
    // The store keeps at most its slots, and long names stop at 48 bytes.
    for (int i = 0; i < 40; ++i) session.NoteRetainedLoadingPlayer(Player(std::string(60, 'x').c_str()));
    CHECK(session.retainedRosterCount == idSessionLocal::RETAINED_ROSTER_SLOTS && session.retainedRosterName[0].Length() == 48);
    session.ClearRetainedLoadingRoster();
    // No message, no line.
    server.Set("si_motd", "^7");
    session.PublishRetainedLoadingServer(server);
    CHECK(loading.state["server_message"].empty());
    std::printf("ui_retained gate: %d server card checks passed\n", checks);
    return 0;
}
"""


def check_server_card(compiler: str, directory: Path) -> None:
    """The loading server card's players and message (section 14.17): compile
    the production sanitizer, roster store and publish with idlib's own escape
    parser, then pin where the network code captures the roster and where the
    game resolves the mode."""
    session = (ROOT / 'src/framework/Session.cpp').read_text(encoding='utf-8')
    header = (ROOT / 'src/framework/Session_local.h').read_text(encoding='utf-8')
    strings = (ROOT / 'src/idlib/Str.cpp').read_text(encoding='latin-1')
    slots = re.search(r'static const int\s+RETAINED_ROSTER_SLOTS = (\d+);', header).group(1)
    rows = re.search(r'static const int RETAINED_ROSTER_ROWS = \d+;', session).group(0)
    bodies = [function_body(strings, 'int idStr::IsEscape( const char *s, int* type )'),
              function_body(strings, 'char *idStr::RemoveEscapes( char *string, int escapes )'),
              function_body(session, 'static idStr Session_RetainedPlayerText('), rows]
    bodies += [function_body(session, f'void idSessionLocal::{name}(') for name in (
        'ClearRetainedLoadingRoster', 'NoteRetainedLoadingPlayer', 'NoteRetainedLoadingConnecting', 'PublishRetainedLoadingServer')]
    source = directory / 'card.cpp'
    binary = directory / 'card.exe'
    source.write_text(CARD.replace('@SLOTS@', slots) + '\n'.join(bodies) + CARD_MAIN, encoding='utf-8')
    subprocess.run([compiler, '-std=c++20', '-Wall', '-Wextra', '-Wno-unused-function', str(source), '-o', str(binary)], check=True)
    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=60)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    assert result.returncode == 0, 'the server card checks failed'
    # The generator's roster rows match the session's.
    generator = (ROOT / 'tools/ui/build_retained_screens.py').read_text(encoding='utf-8')
    assert re.search(r'^SERVER_ROSTER_ROWS = (\d+)$', generator, re.M).group(1) == re.search(r'= (\d+);', rows).group(1)
    # Every language has the roster lines, each with one count, and the
    # longest forms fit: "+N more" in a team column, spectators and players
    # connecting together across the card (Lowpixel, as the card sets them).
    sys.path.insert(0, str(ROOT / 'tools/ui'))
    import build_retained_screens as layout
    card_width = layout.U * 250 - 30
    for table in sorted((ROOT / 'content/baseoq4/pak0/strings').glob('*_openq4.lang')):
        text = table.read_text(encoding='utf-8')
        lines = {key: re.search(rf'"{key}"\s+"([^"]*)"', text) for key in ('#str_230070', '#str_230071', '#str_230072')}
        assert all(lines.values()), f'{table.name} lacks the server card roster lines'
        more, connecting, spectating = (lines[key].group(1) for key in ('#str_230070', '#str_230071', '#str_230072'))
        assert all(line.count('%d') == 1 and line.count('%') == 1 for line in (more, connecting, spectating)), table.name
        assert layout.text_width('lowpixel', more % 26, 14) <= (card_width - 12) / 2, f'{table.name}: "+N more" overflows a team column'
        extra = f'{spectating % 31} \u00b7 {connecting % 31}'
        assert layout.text_width('lowpixel', extra, 13) <= card_width, f'{table.name}: the spectators line overflows the card'
    # Where the roster comes from. The listen host notes everyone in the game,
    # bots included, before InitClient wipes their user info and before the
    # map loads; a client notes the players it knows on a map change before
    # InitGame clears them, and a fresh connection starts from none.
    server = (ROOT / 'src/framework/async/AsyncServer.cpp').read_text(encoding='utf-8')
    change = function_body(server, 'void idAsyncServer::ExecuteMapChange(')
    assert change.index('sessLocal.ClearRetainedLoadingRoster();') < change.index('InitClient( i, clients[i].clientId, clients[i].clientRate );')
    assert change.index('sessLocal.NoteRetainedLoadingConnecting( retainedConnecting );') < change.index('sessLocal.ExecuteMapChange();')
    assert change.index('InitLocalClient( 0, false );') < change.index('sessLocal.ClearRetainedLoadingRoster();')
    assert 'if ( i == localClientNum || clients[i].clientState == SCS_INGAME ) {' in change
    client = (ROOT / 'src/framework/async/AsyncClient.cpp').read_text(encoding='utf-8')
    unreliable = function_body(client, 'void idAsyncClient::ProcessUnreliableServerMessage(')
    gameinit = unreliable[unreliable.index('case SERVER_UNRELIABLE_MESSAGE_GAMEINIT:'):]
    assert gameinit.index('sessLocal.NoteRetainedLoadingPlayer( sessLocal.mapSpawnData.userInfo[ slot ] );') < \
        gameinit.index('InitGame( serverGameInitId, serverGameFrame, serverGameTime, serverSI );') < gameinit.index('sessLocal.ExecuteMapChange();')
    response = function_body(client, 'void idAsyncClient::ProcessConnectResponseMessage(')
    assert response.index('msg.ReadDeltaDict( serverSI, NULL );') < response.index('msg.IsReadOverflowed() || serverClientNum < 0') < \
        response.index('sessLocal.ClearRetainedLoadingRoster();') < response.index('AsyncClient_ReadConnectRoster( msg );') < \
        response.index('InitGame( serverGameInitId, serverGameFrame, serverGameTime, serverSI );') < response.index('sessLocal.ExecuteMapChange();')
    # A fresh connection learns the players from an optional block after the
    # server info: the server writes it before sending, and the client reads
    # it only behind its tag and length, so neither side breaks the other.
    connect = function_body(server, 'void idAsyncServer::ProcessConnectMessage(')
    assert connect.index('outMsg.WriteDeltaDict( sessLocal.mapSpawnData.serverInfo, NULL );') < \
        connect.index('AsyncServer_WriteConnectRoster( outMsg, clients, clientNum );') < connect.rindex('serverPort.SendPacket( from, outMsg.GetData(), outMsg.GetSize() );')
    writer = function_body(server, 'static void AsyncServer_WriteConnectRoster(')
    for token in ('if ( i == joiner ) {', 'clients[ i ].clientState == SCS_INGAME', 'NA_BOT ? idConnectRoster::FLAG_BOT',
                  'msg.GetRemainingSpace() >= size + 6', 'msg.WriteLong( static_cast<int>( idConnectRoster::TAG ) );'):
        assert token in writer, token
    reader = function_body(client, 'static void AsyncClient_ReadConnectRoster(')
    for token in ('msg.GetRemainingReadBits() < 48 || msg.ReadLong() != static_cast<int>( idConnectRoster::TAG )',
                  'size > static_cast<int>( idConnectRoster::MAX_BYTES ) || msg.GetRemainingReadBits() < size * 8',
                  '!idConnectRoster::Decode( block, size, roster )', 'sessLocal.NoteRetainedLoadingConnecting( roster.connecting );'):
        assert token in reader, token
    assert 'DisconnectFromServer' not in reader and 'disconnect' not in reader, 'a bad roster block must never end the connection'
    # The session publishes the card only on the retained screen, after the
    # stock strings it falls back to.
    loading = function_body(session, 'void idSessionLocal::LoadLoadingGui(')
    assert loading.index('guiLoading->SetStateString( "server_limit", limitText.c_str() );') < loading.index(
        'PublishRetainedLoadingServer( mapSpawnData.serverInfo );')
    assert 'if ( retainedLoading ) {\n\t\t\t\tPublishRetainedLoadingServer( mapSpawnData.serverInfo );' in loading.replace('\r\n', '\n')
    # game_mp names the mode and its limits from its own table, with the
    # rules the scoreboard uses, and the message is server info.
    mp = (ROOT / 'src/mpgame/Game_local.cpp').read_text(encoding='utf-8')
    verb = mp[mp.index('if ( !idStr::Icmp( menuCommand, "retainedLoadingServer" ) ) {'):]
    verb = verb[:verb.index('} else if ( !idStr::Icmp( menuCommand, "initCreateServerSettings" ) ) {')]
    for token in ('MPGameTypeByName( query.GetString( "si_gameType" ) )', 'MPResolveMatchLimitFor( query, info->type, limitLabel, limitValue );',
                  'MPGameTypeHasAny( info->type, GTF_TEAM )', 'common->GetLocalizedString( info->localizedName )',
                  'gui->SetStateBool( "server_answered", true );'):
        assert token in verb, token
    rules = (ROOT / 'src/mpgame/MultiplayerGame.cpp').read_text(encoding='utf-8')
    assert 'MPResolveMatchLimitFor( gameLocal.serverInfo, gameLocal.gameType, limitLabel, limitValue );' in \
        function_body(rules, 'static void MPResolveMatchLimit(')
    for module in ('src/mpgame/gamesys/SysCvar.cpp', 'src/game/gamesys/SysCvar.cpp'):
        cvars = (ROOT / module).read_text(encoding='utf-8')
        assert re.search(r'idCVar si_motd\(\s+"si_motd",\s+"",\s+CVAR_GAME \| CVAR_SERVERINFO \| PC_CVAR_ARCHIVE', cvars), module


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
                      'void idSessionLocal::PublishRetainedLoadingDevice(', 'void idSessionLocal::PublishRetainedLoadingTip('):
        assert 'if ( !retainedLoadingActive || guiLoading == NULL' in function_body(session, signature), signature
    loading = function_body(session, 'void idSessionLocal::LoadLoadingGui(')
    assert session.count('retainedLoadingActive = true;') == 1 and loading.index('if ( retainedLoading ) {') < loading.index('retainedLoadingActive = true;')
    # Tips: the first as the screen presents, then from the load's redraws;
    # every tip, in every shipped language, fits two lines.
    assert loading.index('retainedLoadingActive = true;') < loading.index('PublishRetainedLoadingTip( true );')
    assert 'PublishRetainedLoadingTip( false );' in function_body(session, 'void idSessionLocal::PacifierUpdate(')
    assert session.count('PublishRetainedLoadingTip( false );') == 1
    sys.path.insert(0, str(ROOT / 'tools' / 'ui'))
    import build_retained_screens as generator
    tips_table = session[session.index('static const char *const RETAINED_LOADING_TIPS[] = {'):]
    tips_table = tips_table[:tips_table.index('static const int RETAINED_LOADING_TIP_MSEC = 6000;') + len('static const int RETAINED_LOADING_TIP_MSEC = 6000;')]
    tip_keys = re.findall(r'"(#str_\d+)"', tips_table)
    assert len(tip_keys) == len(set(tip_keys)) >= 12, tip_keys
    for key in tip_keys + ['#str_230051']:
        texts = generator.localized(key)
        assert sorted(texts) == sorted(generator.LANGUAGES), (key, sorted(texts))
        if key != '#str_230051':
            for language, text in texts.items():
                assert len(generator.tip_lines(text)) <= 2, (key, language, generator.tip_lines(text))
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
    # The arsenal: the network system hands each spawned kind of item to the
    # retained loading screen, which shows as many as the stock row.
    network = (ROOT / 'src/framework/async/NetworkSystem.cpp').read_text(encoding='utf-8', errors='replace')
    icon_body = function_body(network, 'void idNetworkSystem::AddLoadingIcon(')
    assert icon_body.index('SetStateString( va( "load_icon_img_%d", numIcons ), icon );') < \
        icon_body.index('sessLocal.PublishRetainedLoadingIcon( numIcons, icon );')
    arsenal_count = int(re.search(r'static const int RETAINED_ARSENAL_ICONS = (\d+);', session).group(1))
    assert arsenal_count == 20 and 'if ( numIcons >= 20 ) {' in icon_body
    publish = function_body(session, 'void idSessionLocal::PublishRetainedLoadingIcon(')
    assert 'guiLoading->HandleNamedEvent( va( "arsenal%d", index ) );' in publish and '!retainedLoadingActive' in publish
    loading_text = (ROOT / 'content/baseoq4/pak0/guis/loading/loading.q4ui').read_text(encoding='utf-8')
    loading_doc = json.loads(re.sub(r'^\s*//.*$', '', loading_text, flags=re.M))
    fades = [item for item in loading_doc['timelines'] if item['id'].startswith('arsenal')]
    assert sorted(item['id'] for item in fades) == sorted(f'arsenal{index}' for index in range(1, arsenal_count + 1))
    assert all(item['durationMs'] == 150 for item in fades)
    # The sub-page change: the frame pump runs the hand-over, MenuEvent holds
    # input meanwhile, and the documents' halves last as long as the session
    # waits.
    pump = function_body(menu, 'void idSessionLocal::GuiFrameEvents(')
    assert pump.index('UpdateRetainedHome();') < pump.index('UpdateRetainedSubpage();') < pump.index('if ( guiTest ) {')
    menu_event = function_body(menu, 'void idSessionLocal::MenuEvent(')
    assert menu_event.index('if ( RetainedSubpageEvent( event ) ) {') < menu_event.index('HandleEvent(')
    waits = {name: int(re.search(rf'static const int RETAINED_SUBPAGE_{name}_MSEC = (\d+);', menu).group(1)) for name in ('DEEPER', 'BACK')}
    for name, event in (('singleplayer', 'subpageEnter'), ('campaigns', 'subpageLeave')):
        text = (ROOT / f'content/baseoq4/pak0/guis/menu/{name}.q4ui').read_text(encoding='utf-8')
        document = json.loads(re.sub(r'^\s*//.*$', '', text, flags=re.M))
        timelines = {item['id']: item for item in document['timelines']}
        assert timelines[event]['durationMs'] == waits['DEEPER' if event == 'subpageEnter' else 'BACK'], name
        assert document['events']['onDeactivate'][0] == {'op': 'playTimeline', 'timeline': 'rest'}, name
        # Rest returns everything a change moves, so a hidden document never
        # presents moved (the crumb's fitted scale rests in crumbRest).
        moved = {(track['node'], track['property']) for item in timelines.values()
                 if item['id'].startswith(('subpage', 'crumbEnter', 'crumbReturn')) for track in item['tracks']}
        rested = {(track['node'], track['property']) for item in timelines.values()
                  if item['id'] == 'rest' or item['id'].startswith('crumbRest') for track in item['tracks']}
        assert moved <= rested, (name, sorted(moved - rested))
    reversals = sorted(int(item['id'][len('subpageReverse'):]) for item in json.loads(re.sub(r'^\s*//.*$', '',
        (ROOT / 'content/baseoq4/pak0/guis/menu/singleplayer.q4ui').read_text(encoding='utf-8'), flags=re.M))['timelines']
        if item['id'].startswith('subpageReverse'))
    assert reversals == [150, 200, 250, 300], reversals
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
        'void idSessionLocal::HandleRetainedSessionRequest(', 'static bool Session_ModSuppliesFile(',
        'void idSessionLocal::BeginRetainedSubpage(', 'void idSessionLocal::UpdateRetainedSubpage(',
        'bool idSessionLocal::RetainedSubpageEvent(',
        'idUserInterface *idSessionLocal::SelectRetainedLoadingGui(',
        'void idSessionLocal::PreloadRetainedScreens(', 'void idSessionLocal::PrepareRetainedLevel(',
        'void idSessionLocal::ReportRetainedScreens(')]
    bodies.append(tips_table)
    bodies += [function_body(session, signature) for signature in (
        'static bool Session_ImageInstalled(', 'idStr idSessionLocal::RetainedPauseShot(',
        'void idSessionLocal::PrecacheRetainedLevelImages(', 'static idStr Session_RetainedSaveAge(',
        'void idSessionLocal::PublishRetainedLoadingTip(',
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
            check_server_card(compiler, Path(directory))
        return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
