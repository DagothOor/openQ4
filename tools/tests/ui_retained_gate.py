#!/usr/bin/env python3
"""The ui_retained gate and the stock fallback of every retained screen.

Compiles the production retained-screen session code (title and pause home
screens, hand-offs, session verbs, loading selection, the campaign selectors
and the status report) against counted engine/UI doubles, and checks the
source contracts that keep the gate complete:

* ui_retained defaults to 1 and is archived; while it is 0 no retained
  screen is reachable. ui_retainedSystem opts into the SYSTEM page, which
  ui_retained includes only once it offers every setting of the stock SYSTEM
  page and each one works there: the list of settings it lacks matches the
  two pages (a control counts for a setting only when its action writes it),
  and the list of settings it cannot yet apply, take typing for or change on
  every renderer matches those reasons as the code states them;
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
    static int Icmpn(const char* a, const char* b, int n) {
        for (int i = 0; i < n; ++i, ++a, ++b) { if (std::tolower(*a) != std::tolower(*b) || !*a) return std::tolower(*a) - std::tolower(*b); }
        return 0;
    }
    void StripLeading(char c) { while (!empty() && front() == c) erase(begin()); }
};
namespace openq4 { static int sessionChanges = 0; static void NativeInputBeforeSessionChange() { ++sessionChanges; } }
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
static const int MAX_ASYNC_CLIENTS = 32;
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
    // The multiplayer menu's commands, and its answer to each (nullptr: close).
    std::vector<std::string> guiCommands; std::function<const char*(const char*)> answer;
    const char* HandleGuiCommands(const char* command) { guiCommands.push_back(command); return answer ? answer(command) : "continue"; }
} gameObject, *game = &gameObject;
struct CVar { bool value = false; bool GetBool() const { return value; } } ui_retained, ui_retainedSystem, ui_retainedMultiplayer;
// Key bindings: a bound command's key as the key lists name it ("^ikHH"),
// and a key's name by number.
struct idKeyInput {
    static std::map<std::string, std::string>& Bound() { static std::map<std::string, std::string> bound; return bound; }
    static const char* KeysFromBinding(const char* bind) { const auto found = Bound().find(bind); return found != Bound().end() ? found->second.c_str() : "Unbound"; }
    static const char* KeyNumToString(int key, bool) { static std::string name; name = key == 0x8b ? "F1" : "#str_07133"; return name.c_str(); }
};
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
        int GetInt(const char* key, const char* fallback = "0") const { const auto found = values.find(key); return std::atoi(found == values.end() ? fallback : found->second.c_str()); }
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
    int stateChanges = 0;
    void StateChanged(int) { ++stateChanges; }
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
static bool welcomeAnswer = false;   // the game names the Welcome card
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
    // Home hand-offs run on the legacy main menu; a card hand-off runs on the
    // game's menu, and the card's own pump on the card.
    void DispatchCommand(idUserInterface* gui, const char* command) {
        CHECK(gui == guiMainMenu || gui == guiActive || gui == guiRetainedMultiplayer); dispatched.push_back(command);
    }
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
    void StartMenu() { ++menus; guiActive = guiMainMenu; }
    void SetGUI(idUserInterface* gui, void*) { guiActive = gui; }
    idUserInterface* SelectRetainedLoadingGui(idUserInterface*, bool);
    idUserInterface* FindRetainedGui(const char*, bool, bool);
    idUserInterface* RetainedHomeDocument(idUserInterface*&, const char*);
    bool RetainedPauseIsStrogg();
    bool RetainedSystemAvailable() const;
    void PreloadRetainedScreens(); void PrepareRetainedLevel(const char*, bool); void PrecacheRetainedLevelImages();
    void ReportRetainedScreens();
    idUserInterface *guiRetainedEscape = nullptr, *guiRetainedWelcome = nullptr, *guiRetainedMultiplayer = nullptr;
    bool retainedMultiplayerWelcome = false;
    bool retainedMultiplayerUncovered = false; int retainedMultiplayerRevision = -1;
    int retainedMultiplayerHandoff = -1, retainedMultiplayerHandoffUntil = 0;
    bool RetainedMultiplayerCovers() const; void UpdateRetainedMultiplayer(); void RetainedMultiplayerFrameEvent();
    void RetireRetainedMultiplayer(bool); void HandleRetainedMultiplayerRequest(idUserInterface*, const char*);
    void HandleGameMenuReturn(const char*);
    // The loading hold has its own compiled case (check_loading_hold).
    void FadeRetainedLoadingHold(const char*) {}
};
'''

MAIN = r'''
static const char* const DOCUMENTS[] = {"guis/menu/title.q4ui", "guis/menu/pause.q4ui", "guis/menu/pause_strogg.q4ui", "guis/loading/loading.q4ui",
    "guis/menu/singleplayer.q4ui", "guis/menu/campaigns.q4ui", "guis/menu/settings/system.q4ui", "guis/menu/mp_escape.q4ui",
    "guis/menu/mp_welcome.q4ui"};
// The documents that fell back to their stock screens, in order.
static std::vector<std::string> Stock(const idSessionLocal& session) {
    return std::vector<std::string>(session.retainedStock.begin(), session.retainedStock.end());
}
static idSessionLocal Session(bool gate, bool inGame = false) {
    managerObject = Manager{}; commonObject = Common{}; commands = CommandSystem{}; legacy.clear(); legacyActions.clear(); precached.clear(); stickX = stickY = 0;
    legacyActionAvailable = true; preview = false; ui_retained.value = gate; ui_retainedSystem.value = false; ui_retainedMultiplayer.value = false;
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
        CHECK(commonObject.output.find("OPENQ4_RETAINED enabled=0 system=0 multiplayer=0 welcome=0 home=- title=0 pause=0 strogg=0 handoff=0 release=0 mp=- views=0 stock=-") != std::string::npos);
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
        // A multiplayer level loads each card whose pages are all built.
        const size_t cards = (RETAINED_MP_ESCAPE_MISSING_PAGES[0] == NULL ? 1 : 0) + (RETAINED_MP_WELCOME_MISSING_PAGES[0] == NULL ? 1 : 0);
        s.PrepareRetainedLevel("mp/q4dm1", true); CHECK(precached.empty() && managerObject.loads.size() == 2 + cards);
        s.PrepareRetainedLevel("game/airdefense1", false);
        CHECK((precached == std::vector<std::string>{"gfx/guis/loadscreens/generic"}) && managerObject.loads.size() == 3 + cards);
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
    {   // The gate alone includes the SYSTEM page only once it lacks no stock setting and
        // each one works there; ui_retainedSystem opts into it until it falls back.
        const bool complete = RETAINED_SYSTEM_MISSING_SETTINGS[0] == NULL && RETAINED_SYSTEM_INCOMPLETE_SETTINGS[0] == NULL;
        auto s = Session(true); CHECK(s.RetainedSystemAvailable() == complete);
        s.ReportRetainedScreens(); CHECK(commonObject.output.find(complete ? "OPENQ4_RETAINED enabled=1 system=1 multiplayer=" : "OPENQ4_RETAINED enabled=1 system=0 multiplayer=") != std::string::npos);
        auto off = Session(false); CHECK(!off.RetainedSystemAvailable());
        ui_retainedSystem.value = true; CHECK(s.RetainedSystemAvailable() && off.RetainedSystemAvailable());
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
        s.ReportRetainedScreens(); CHECK(commonObject.output.find("home=- title=0 pause=1 strogg=0 handoff=0 release=1 mp=-") != std::string::npos);
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
    {   // The multiplayer card covers the game's in-match menu only through its
        // opt-in while pages still hand off; the game answers the cover protocol,
        // and anything it does not, or a menu other than mpmain.gui, keeps stock.
        static idUserInterface mpMenu("guis/mpmain.gui"), chat("guis/mpchat.gui");
        auto Mp = [&](bool gate, bool optIn) {
            auto s = Session(gate, true); s.multiplayer = true; ui_retainedMultiplayer.value = optIn;
            mpMenu = idUserInterface("guis/mpmain.gui"); mpMenu.state["gameDraw"] = "1"; s.guiActive = &mpMenu;
            chat = idUserInterface("guis/mpchat.gui"); chat.state["gameDraw"] = "1";
            gameObject.publish = [](idUserInterface* gui) {
                if (gameObject.commands.back() == "retainedMultiplayerVariant") gui->SetStateBool("mp.welcome", welcomeAnswer);
                if (gameObject.commands.back() == "retainedMultiplayerCover") { gui->SetStateInt("mp.protocol", 1); gui->SetStateBool("mp.cover_allowed", true); }
                if (gameObject.commands.back() != "retainedMultiplayerUncover") gui->SetStateInt("mp.revision", static_cast<int>(gameObject.commands.size()));
            };
            return s;
        };
        const bool complete = RETAINED_MP_ESCAPE_MISSING_PAGES[0] == NULL;
        {   auto s = Mp(true, false); s.UpdateRetainedMultiplayer();
            CHECK((s.guiRetainedMultiplayer != nullptr) == complete);  // the gate alone waits for every page
            auto off = Mp(false, false); off.UpdateRetainedMultiplayer(); off.PrepareRetainedLevel("mp/q4dm1", true);
            CHECK(off.guiRetainedMultiplayer == nullptr && managerObject.loads.empty() && gameObject.commands.empty());
        }
        auto s = Mp(true, true);
        idKeyInput::Bound()["_impulse28"] = "^iK8b"; idKeyInput::Bound()["_impulse29"] = "^ik8c";
        s.PrepareRetainedLevel("mp/q4dm1", true);  // loaded inside the level load
        CHECK((managerObject.loads == std::vector<std::string>{"guis/menu/mp_escape.q4ui", "guis/menu/mp_welcome.q4ui"}) &&
              s.guiRetainedEscape && s.guiRetainedEscape->state["card.tab"] == "0" && s.guiRetainedWelcome &&
              s.guiRetainedWelcome->state["card.tab"] == "0");
        CHECK(managerObject.flags[0].unique && !managerObject.flags[0].shared);
        s.UpdateRetainedMultiplayer();
        auto* card = s.guiRetainedMultiplayer;
        CHECK(card == s.guiRetainedEscape && s.RetainedMultiplayerCovers() && card->active && card->named.back() == "open");
        CHECK((gameObject.commands == std::vector<std::string>{"retainedMultiplayerVariant", "retainedMultiplayerCover"}) &&
              card->stateChanges == 1 && s.drains == 1 && !s.retainedMultiplayerWelcome);
        // The Vote page's ballots show their keys by name: one bound to a key the
        // engine names, one to a key it does not, and none unbound.
        CHECK(card->state["mp.keys.vote_yes"] == "F1" && card->state["mp.keys.vote_yes_bound"] == "1" &&
              card->state["mp.keys.vote_no"].empty() && card->state["mp.keys.vote_no_bound"] == "0" &&
              card->state["mp.keys.voice_chat"].empty() && card->state["mp.keys.voice_chat_bound"] == "0");
        s.ReportRetainedScreens(); CHECK(commonObject.output.find("multiplayer=1 ") != std::string::npos && commonObject.output.find(" mp=escape ") != std::string::npos);
        // Each frame asks the game for what changed; only a new revision publishes.
        s.UpdateRetainedMultiplayer(); CHECK(gameObject.commands.back() == "retainedMultiplayerState" && card->stateChanges == 2);
        gameObject.publish = nullptr; s.UpdateRetainedMultiplayer(); CHECK(card->stateChanges == 2 && card->activations == 1);
        // Home verbs from the card, and card verbs from elsewhere, are refused.
        s.HandleRetainedSessionRequest(card, "quit"); CHECK(commonObject.quits == 0 && commonObject.warnings.back().find("unhandled multiplayer request") != std::string::npos);
        idUserInterface stranger("guis/other.q4ui"); s.HandleRetainedSessionRequest(&stranger, "mpClose"); CHECK(gameObject.guiCommands.empty());
        // Resume: the game's own close, with its sound; the card releases the
        // softened view over the running game in the same frame.
        gameObject.answer = [](const char*) -> const char* { return nullptr; };
        s.HandleRetainedSessionRequest(card, "mpClose");
        CHECK((gameObject.guiCommands == std::vector<std::string>{"play main_menu_selection ; close"}) && s.guiActive == nullptr);
        CHECK(s.guiRetainedMultiplayer == nullptr && !card->active && card->named.back() == "release");
        CHECK(s.guiRetainedReleasing == card && s.retainedReleaseUntil == commonObject.time + 250 && gameObject.commands.back() == "retainedMultiplayerUncover");
        s.UpdateRetainedMultiplayer(); CHECK(s.guiRetainedMultiplayer == nullptr && card->deactivations == 1);
        // Main Menu leaves for the main menu with the match running: no release.
        s.guiActive = &mpMenu; gameObject.publish = [](idUserInterface* gui) { gui->SetStateInt("mp.protocol", 1); gui->SetStateBool("mp.cover_allowed", true); };
        s.UpdateRetainedMultiplayer(); CHECK(s.guiRetainedMultiplayer == card && card->activations == 2 && card->named.back() == "open");
        gameObject.answer = [](const char*) -> const char* { return "main"; };
        s.HandleRetainedSessionRequest(card, "mpMainMenu");
        CHECK(gameObject.guiCommands.back() == "play main_menu_selection ; mainMenu" && s.menus == 1 && s.guiActive == s.guiMainMenu);
        CHECK(s.guiRetainedMultiplayer == nullptr && card->named.back() == "open" && s.guiRetainedReleasing == card);  // the earlier release, not a new one
        // Disconnect, confirmed on the card, is the game's own disconnect.
        s.guiActive = &mpMenu; s.guiRetainedReleasing = nullptr; s.UpdateRetainedMultiplayer();
        gameObject.answer = [](const char*) -> const char* { return nullptr; };
        s.HandleRetainedSessionRequest(card, "mpDisconnect"); CHECK(gameObject.guiCommands.back() == "play main_menu_selection ; disconnect");
        // Opening the menu again covers it again.
        s.guiActive = &mpMenu; s.UpdateRetainedMultiplayer(); CHECK(s.guiRetainedMultiplayer == card);
        // A page in development hands off: the stock menu presents at once and
        // presses the page's button, and the card stays away until the menu closes.
        gameObject.answer = nullptr; card->state["card.stock_page"] = "2";
        s.HandleRetainedSessionRequest(card, "mpStockPage");
        CHECK(s.guiRetainedMultiplayer == nullptr && card->named.back() != "release" && s.retainedMultiplayerUncovered);
        CHECK(legacyActions.back() == "main_b_vote" && s.dispatched.back() == "play main_menu_selection" && s.retainedMultiplayerHandoff == -1);
        s.UpdateRetainedMultiplayer(); CHECK(s.guiRetainedMultiplayer == nullptr);
        s.guiActive = nullptr; s.UpdateRetainedMultiplayer(); CHECK(!s.retainedMultiplayerUncovered);
        s.guiActive = &mpMenu; s.UpdateRetainedMultiplayer(); CHECK(s.guiRetainedMultiplayer == card);
        // Before the menu's opening shows its column, the hand-off waits up to 500 ms.
        legacyActionAvailable = false; card->state["card.stock_page"] = "7"; s.HandleRetainedSessionRequest(card, "mpStockPage");
        CHECK(s.retainedMultiplayerHandoff == 7 && legacyActions.back() == "main_b_admin");
        commonObject.time += 499; s.UpdateRetainedMultiplayer(); CHECK(s.retainedMultiplayerHandoff == 7 && commonObject.warnings.size() == 1);
        legacyActionAvailable = true; s.UpdateRetainedMultiplayer(); CHECK(s.retainedMultiplayerHandoff == -1 && legacyActions.size() >= 3);
        legacyActionAvailable = false; s.guiActive = nullptr; s.UpdateRetainedMultiplayer(); s.guiActive = &mpMenu; s.UpdateRetainedMultiplayer();
        s.HandleRetainedSessionRequest(card, "mpStockPage"); commonObject.time += 500; s.UpdateRetainedMultiplayer();
        CHECK(s.retainedMultiplayerHandoff == -1 && commonObject.warnings.back().find("did not become available") != std::string::npos);
        legacyActionAvailable = true;
        // Out-of-range pages are refused and change nothing.
        s.guiActive = nullptr; s.UpdateRetainedMultiplayer(); s.guiActive = &mpMenu; s.UpdateRetainedMultiplayer();
        // The Team page's actions: the game derives the slot's action again and
        // closes the menu when it acts; an action it refuses now keeps it open.
        gameObject.answer = [](const char*) -> const char* { return "continue"; };
        card->state["card.team_action"] = "1"; s.HandleRetainedSessionRequest(card, "mpTeamAction");
        CHECK(gameObject.guiCommands.back() == "play main_menu_selection ; retained team 1" && s.guiRetainedMultiplayer == card);
        gameObject.answer = [](const char*) -> const char* { return nullptr; };
        s.HandleRetainedSessionRequest(card, "mpTeamAction");
        CHECK(s.guiActive == nullptr && s.guiRetainedMultiplayer == nullptr && card->named.back() == "release");
        s.guiActive = &mpMenu; s.guiRetainedReleasing = nullptr; s.UpdateRetainedMultiplayer(); CHECK(s.guiRetainedMultiplayer == card);
        const size_t asked = gameObject.guiCommands.size();
        for (const char* slot : {"-1", "3"}) {
            card->state["card.team_action"] = slot; s.HandleRetainedSessionRequest(card, "mpTeamAction");
            CHECK(gameObject.guiCommands.size() == asked && s.guiRetainedMultiplayer == card &&
                  commonObject.warnings.back().find("team action") != std::string::npos);
        }
        // The Match page names a Match Control action by index; the session sends
        // the game's own fixed token and the menu stays open. The refresh the
        // page asks as it opens makes no sound; an index past the table is refused.
        gameObject.answer = [](const char*) -> const char* { return "continue"; };
        card->state["card.match_op"] = "1"; s.HandleRetainedSessionRequest(card, "mpMatch");
        CHECK(gameObject.guiCommands.back() == "play main_menu_selection ; matchControl ready_toggle" && s.guiRetainedMultiplayer == card);
        card->state["card.match_op"] = "0"; s.HandleRetainedSessionRequest(card, "mpMatch");
        CHECK(gameObject.guiCommands.back() == "matchControl refresh");
        card->state["card.match_op"] = "7"; s.HandleRetainedSessionRequest(card, "mpMatch");
        CHECK(gameObject.guiCommands.back() == "play main_menu_selection ; matchControl arm_forfeit");
        card->state["card.match_op"] = "15"; s.HandleRetainedSessionRequest(card, "mpMatch");
        CHECK(gameObject.guiCommands.back() == "play main_menu_selection ; matchControl confirm");
        card->state["card.match_op"] = "16"; s.HandleRetainedSessionRequest(card, "mpMatch");
        CHECK(gameObject.guiCommands.back() == "play main_menu_selection ; matchControl cancel_confirm" && s.guiRetainedMultiplayer == card);
        card->state["card.match_op"] = "17"; s.HandleRetainedSessionRequest(card, "mpMatch");
        CHECK(gameObject.guiCommands.back() == "play main_menu_selection ; matchControl team_join_marine");
        card->state["card.match_op"] = "26"; s.HandleRetainedSessionRequest(card, "mpMatch");
        CHECK(gameObject.guiCommands.back() == "play main_menu_selection ; matchControl arm_roster_remove");
        card->state["card.match_op"] = "32"; s.HandleRetainedSessionRequest(card, "mpMatch");
        CHECK(gameObject.guiCommands.back() == "play main_menu_selection ; matchControl series_contestant_bind" && s.guiRetainedMultiplayer == card);
        const size_t matched = gameObject.guiCommands.size();
        for (const char* action : {"-1", "33", "99"}) {
            card->state["card.match_op"] = action; s.HandleRetainedSessionRequest(card, "mpMatch");
            CHECK(gameObject.guiCommands.size() == matched && s.guiRetainedMultiplayer == card &&
                  commonObject.warnings.back().find("match action") != std::string::npos);
        }
        // A Match Control list's row: the session sets the stock list's own
        // selection on the game's menu to it and sends the list's token, as the
        // stock list does, and the menu stays open. A list or a row outside
        // the tables is refused and selects nothing.
        card->state["card.match_list"] = "0"; card->state["card.match_row"] = "3"; s.HandleRetainedSessionRequest(card, "mpMatchSelect");
        CHECK(mpMenu.state["match_team_rows_sel_0"] == "3" &&
              gameObject.guiCommands.back() == "play main_menu_selection ; matchControl select_team_row" && s.guiRetainedMultiplayer == card);
        card->state["card.match_list"] = "1"; card->state["card.match_row"] = "0"; s.HandleRetainedSessionRequest(card, "mpMatchSelect");
        CHECK(mpMenu.state["match_replacement_rows_sel_0"] == "0" &&
              gameObject.guiCommands.back() == "play main_menu_selection ; matchControl select_replacement_row");
        card->state["card.match_list"] = "5"; card->state["card.match_row"] = "127"; s.HandleRetainedSessionRequest(card, "mpMatchSelect");
        CHECK(mpMenu.state["match_series_map_rows_sel_0"] == "127" &&
              gameObject.guiCommands.back() == "play main_menu_selection ; matchControl select_series_map");
        const size_t selected = gameObject.guiCommands.size();
        for (const auto& [list, row] : std::vector<std::pair<const char*, const char*>>{{"-1", "0"}, {"6", "0"}, {"0", "-1"}, {"0", "128"}}) {
            card->state["card.match_list"] = list; card->state["card.match_row"] = row; s.HandleRetainedSessionRequest(card, "mpMatchSelect");
            CHECK(gameObject.guiCommands.size() == selected && mpMenu.state["match_team_rows_sel_0"] == "3" && s.guiRetainedMultiplayer == card &&
                  commonObject.warnings.back().find("of match list") != std::string::npos);
        }
        // The role an invitation or an assignment gives waits on the game's
        // menu, as the stock choice's value does: nothing reaches the game.
        s.HandleRetainedSessionRequest(card, "mpMatchRole 3");
        CHECK(mpMenu.state["match_role_choice"] == "3" && gameObject.guiCommands.size() == selected && s.guiRetainedMultiplayer == card);
        for (const char* bad : {"mpMatchRole 0", "mpMatchRole 5", "mpMatchRole -1"}) {
            s.HandleRetainedSessionRequest(card, bad);
            CHECK(mpMenu.state["match_role_choice"] == "3" && gameObject.guiCommands.size() == selected &&
                  commonObject.warnings.back().find("match role") != std::string::npos);
        }
        s.HandleRetainedSessionRequest(card, "mpMatchRole x");
        CHECK(mpMenu.state["match_role_choice"] == "3" && commonObject.warnings.back().find("unhandled multiplayer request") != std::string::npos);
        // The Players page: the client a row or the statistics name reaches the
        // game as "retained select|mute|friend <client>", none of which closes
        // the menu; a client outside the server's slots is refused.
        gameObject.answer = [](const char*) -> const char* { return "continue"; };
        card->state["card.client"] = "4"; s.HandleRetainedSessionRequest(card, "mpSelectPlayer");
        CHECK(gameObject.guiCommands.back() == "play main_menu_selection ; retained select 4" && s.guiRetainedMultiplayer == card);
        s.HandleRetainedSessionRequest(card, "mpMute");
        CHECK(gameObject.guiCommands.back() == "play main_menu_selection ; retained mute 4" && s.guiRetainedMultiplayer == card);
        card->state["card.client"] = "31"; s.HandleRetainedSessionRequest(card, "mpFriend");
        CHECK(gameObject.guiCommands.back() == "play main_menu_selection ; retained friend 31" && s.guiRetainedMultiplayer == card);
        const size_t named = gameObject.guiCommands.size();
        for (const char* client : {"-1", "32"}) {
            card->state["card.client"] = client; s.HandleRetainedSessionRequest(card, "mpSelectPlayer");
            CHECK(gameObject.guiCommands.size() == named && s.guiRetainedMultiplayer == card &&
                  commonObject.warnings.back().find("named client") != std::string::npos);
        }
        // The Vote page: a drafted field's value control requests "<verb> <value>",
        // which reaches the game quietly as "retained voteSet <field> <value>" and
        // keeps the menu open; a ballot reaches it as "retained vote yes|no" and
        // Call Vote as "retained callVote", each closing the menu when the game
        // acts. A malformed or unknown request is refused.
        gameObject.answer = [](const char*) -> const char* { return "continue"; };
        s.HandleRetainedSessionRequest(card, "mpVoteMap 3");
        CHECK(gameObject.guiCommands.back() == "retained voteSet 0 3" && s.guiRetainedMultiplayer == card);
        s.HandleRetainedSessionRequest(card, "mpVoteKick -1"); CHECK(gameObject.guiCommands.back() == "retained voteSet 11 -1");
        s.HandleRetainedSessionRequest(card, "mpVoteControlTime 600"); CHECK(gameObject.guiCommands.back() == "retained voteSet 6 600");
        s.HandleRetainedSessionRequest(card, "mpVoteBalance 0"); CHECK(gameObject.guiCommands.back() == "retained voteSet 7 0");
        const size_t drafted = gameObject.guiCommands.size();
        for (const char* bad : {"mpVoteMap", "mpVoteMap 3.5", "mpVoteMap x", "mpVoteMap 1000", "mpVoteMap -2", "mpVoteNope 1",
                                "mpVoteMap  3", "mpVoteMap -", "mpVoteMap 3 4", "mpvotemap", "mpVote 3", "mpVoteMapX 3"}) {
            s.HandleRetainedSessionRequest(card, bad);
            CHECK(gameObject.guiCommands.size() == drafted && s.guiRetainedMultiplayer == card &&
                  commonObject.warnings.back().find("unhandled multiplayer request") != std::string::npos);
        }
        s.HandleRetainedSessionRequest(card, "mpVoteYes");
        CHECK(gameObject.guiCommands.back() == "play main_menu_selection ; retained vote yes" && s.guiRetainedMultiplayer == card);
        s.HandleRetainedSessionRequest(card, "mpCallVote");
        CHECK(gameObject.guiCommands.back() == "play main_menu_selection ; retained callVote" && s.guiRetainedMultiplayer == card);
        gameObject.answer = [](const char*) -> const char* { return nullptr; };
        s.HandleRetainedSessionRequest(card, "mpVoteNo");
        CHECK(gameObject.guiCommands.back() == "play main_menu_selection ; retained vote no" && s.guiActive == nullptr &&
              s.guiRetainedMultiplayer == nullptr && card->named.back() == "release");
        s.guiActive = &mpMenu; s.guiRetainedReleasing = nullptr; s.UpdateRetainedMultiplayer(); CHECK(s.guiRetainedMultiplayer == card);
        // The Settings pages: a model list's row and the crosshair reach the game
        // quietly as "retained appearance <slot> <row>" and "retained crosshair
        // <index>"; a swatch as "retained rail <row>"; Controls, Game Options and
        // System leave for the main menu's pages. A row below 0, and a swatch
        // outside the seven, are refused.
        gameObject.answer = [](const char*) -> const char* { return "continue"; };
        s.HandleRetainedSessionRequest(card, "mpModelSelf 3"); CHECK(gameObject.guiCommands.back() == "retained appearance 0 3");
        s.HandleRetainedSessionRequest(card, "mpModelTeam 0"); CHECK(gameObject.guiCommands.back() == "retained appearance 2 0");
        s.HandleRetainedSessionRequest(card, "mpCrosshair 20"); CHECK(gameObject.guiCommands.back() == "retained crosshair 20");
        card->state["card.rail"] = "6"; s.HandleRetainedSessionRequest(card, "mpRail");
        CHECK(gameObject.guiCommands.back() == "play main_menu_selection ; retained rail 6" && s.guiRetainedMultiplayer == card);
        const size_t styled = gameObject.guiCommands.size();
        s.HandleRetainedSessionRequest(card, "mpModelEnemy -1"); s.HandleRetainedSessionRequest(card, "mpCrosshair x");
        for (const char* rail : {"-1", "7"}) { card->state["card.rail"] = rail; s.HandleRetainedSessionRequest(card, "mpRail"); }
        CHECK(gameObject.guiCommands.size() == styled && s.guiRetainedMultiplayer == card);
        gameObject.answer = [](const char* command) -> const char* {
            static std::string menu; menu = std::string("main ") + (std::strrchr(command, ' ') + 1); return menu.c_str();
        };
        for (const auto& [verb, page] : std::vector<std::pair<const char*, const char*>>{{"mpSettingsControls", "fromMp_toControls"},
                                                                                         {"mpSettingsGame", "fromMp_toGameoptions"},
                                                                                         {"mpSettingsSystem", "fromMp_toSystem"}}) {
            s.guiActive = &mpMenu; s.guiRetainedReleasing = nullptr; s.UpdateRetainedMultiplayer(); CHECK(s.guiRetainedMultiplayer == card);
            s.HandleRetainedSessionRequest(card, verb);
            CHECK(gameObject.guiCommands.back() == std::string("play main_menu_selection ; mainMenu ") + page && s.guiActive == s.guiMainMenu &&
                  s.guiRetainedMultiplayer == nullptr);
        }
        s.guiActive = &mpMenu; s.guiRetainedReleasing = nullptr; s.UpdateRetainedMultiplayer(); CHECK(s.guiRetainedMultiplayer == card);
        gameObject.answer = nullptr;
        for (const char* page : {"-1", "8"}) {
            card->state["card.stock_page"] = page; s.HandleRetainedSessionRequest(card, "mpStockPage");
            CHECK(s.guiRetainedMultiplayer == card && !s.retainedMultiplayerUncovered);
        }
        // A map change retires the card at once and opens the next map's card on
        // its first page.
        card->state["card.tab"] = "5"; s.PrepareRetainedLevel("mp/q4dm2", true);
        CHECK(s.guiRetainedMultiplayer == nullptr && card->state["card.tab"] == "0" && s.guiRetainedReleasing == nullptr);
        // Chat, buy and summary GUIs are never covered; neither is a test GUI or a preview.
        s.guiActive = &chat; s.UpdateRetainedMultiplayer(); CHECK(s.guiRetainedMultiplayer == nullptr);
        s.guiActive = &mpMenu; idUserInterface probe("guis/probe.gui"); s.guiTest = &probe; s.UpdateRetainedMultiplayer(); CHECK(s.guiRetainedMultiplayer == nullptr);
        s.guiTest = nullptr; preview = true; s.UpdateRetainedMultiplayer(); CHECK(s.guiRetainedMultiplayer == nullptr);
        preview = false; s.multiplayer = false; s.UpdateRetainedMultiplayer(); CHECK(s.guiRetainedMultiplayer == nullptr);
        // The game may refuse now (the join offer, an Arena Campaign match): the
        // stock menu keeps this opening, and the next asks again.
        auto refused = Mp(true, true);
        gameObject.publish = [](idUserInterface* gui) { gui->SetStateInt("mp.protocol", 1); gui->SetStateBool("mp.cover_allowed", false); };
        refused.UpdateRetainedMultiplayer(); refused.UpdateRetainedMultiplayer();
        CHECK(refused.guiRetainedMultiplayer == nullptr && refused.retainedMultiplayerUncovered && gameObject.commands.size() == 2 && refused.retainedStock.Num() == 0);
        refused.guiActive = nullptr; refused.UpdateRetainedMultiplayer(); refused.guiActive = &mpMenu; refused.UpdateRetainedMultiplayer();
        CHECK(gameObject.commands.size() == 4);
        // A game module without the protocol keeps the stock menu for the session.
        auto old = Mp(true, true); gameObject.publish = nullptr;
        old.UpdateRetainedMultiplayer(); old.UpdateRetainedMultiplayer();
        CHECK(old.guiRetainedMultiplayer == nullptr && (Stock(old) == std::vector<std::string>{"guis/menu/mp_escape.q4ui"}) && gameObject.commands.size() == 2);
        // So does a mod's own multiplayer menu, and a card that stopped drawing.
        auto mod = Mp(true, true); cvarSystemObject.strings["fs_game"] = "mymod"; fileSystemObject.gameDirFiles["mymod"] = {"guis/mpmain.gui"};
        mod.UpdateRetainedMultiplayer();
        CHECK(mod.guiRetainedMultiplayer == nullptr && managerObject.loads.empty() && (Stock(mod) == std::vector<std::string>{"guis/menu/mp_escape.q4ui"}));
        auto failed = Mp(true, true); failed.UpdateRetainedMultiplayer(); auto* stopped = failed.guiRetainedMultiplayer; CHECK(stopped);
        failed.guiActive = nullptr; failed.UpdateRetainedMultiplayer(); stopped->failed = true; failed.guiActive = &mpMenu; failed.UpdateRetainedMultiplayer();
        CHECK(failed.guiRetainedMultiplayer == nullptr && commonObject.warnings.back().find("stopped drawing") != std::string::npos);
        auto missing = Mp(true, true); fileSystemObject.files.erase("guis/menu/mp_escape.q4ui"); missing.UpdateRetainedMultiplayer();
        CHECK(missing.guiRetainedMultiplayer == nullptr && commonObject.warnings.empty() &&
              (gameObject.commands == std::vector<std::string>{"retainedMultiplayerVariant"}));
        // Welcome: while the player has not answered the join offer the game
        // names the Welcome card, which covers the menu with its own verbs. A
        // Join page action reaches the game as "retained welcome <slot>" and
        // closes the menu when the game acts; its Settings tab hands off to the
        // join panel's settings button.
        welcomeAnswer = true;
        auto w = Mp(true, true); w.PrepareRetainedLevel("mp/q4dm1", true); w.UpdateRetainedMultiplayer();
        auto* welcome = w.guiRetainedMultiplayer;
        CHECK(welcome && welcome == w.guiRetainedWelcome && w.retainedMultiplayerWelcome && welcome->named.back() == "open");
        w.ReportRetainedScreens();
        CHECK(commonObject.output.find(" welcome=1 ") != std::string::npos && commonObject.output.find(" mp=welcome ") != std::string::npos);
        gameObject.answer = [](const char*) -> const char* { return nullptr; };
        welcome->state["card.welcome_action"] = "2"; w.HandleRetainedSessionRequest(welcome, "mpWelcomeAction");
        CHECK(gameObject.guiCommands.back() == "play main_menu_selection ; retained welcome 2" && w.guiRetainedMultiplayer == nullptr &&
              welcome->named.back() == "release");
        w.guiActive = &mpMenu; w.guiRetainedReleasing = nullptr; w.UpdateRetainedMultiplayer(); CHECK(w.guiRetainedMultiplayer == welcome);
        const size_t joined = gameObject.guiCommands.size();
        for (const char* slot : {"-1", "4"}) {
            welcome->state["card.welcome_action"] = slot; w.HandleRetainedSessionRequest(welcome, "mpWelcomeAction");
            CHECK(gameObject.guiCommands.size() == joined && w.guiRetainedMultiplayer == welcome &&
                  commonObject.warnings.back().find("join action") != std::string::npos);
        }
        gameObject.answer = nullptr;
        welcome->state["card.stock_page"] = "0"; w.HandleRetainedSessionRequest(welcome, "mpStockPage");
        CHECK(w.guiRetainedMultiplayer == welcome && !w.retainedMultiplayerUncovered);   // the Join page has no stock page
        mpMenu.state["initial_join"] = "1";   // the join offer stands: the join panel's settings
        welcome->state["card.stock_page"] = "3"; w.HandleRetainedSessionRequest(welcome, "mpStockPage");
        CHECK(legacyActions.back() == "qj_b_settings" && w.retainedMultiplayerUncovered && w.guiRetainedMultiplayer == nullptr);
        mpMenu.state["initial_join"] = "0";   // once it has closed: the menu column's settings
        w.guiActive = nullptr; w.UpdateRetainedMultiplayer(); w.guiActive = &mpMenu; w.UpdateRetainedMultiplayer();
        CHECK(w.guiRetainedMultiplayer == welcome);
        welcome->state["card.stock_page"] = "3"; w.HandleRetainedSessionRequest(welcome, "mpStockPage");
        CHECK(legacyActions.back() == "main_b_settings" && w.retainedMultiplayerUncovered);
        // Once the player answers, the game names Escape again.
        welcomeAnswer = false; w.guiActive = nullptr; w.UpdateRetainedMultiplayer(); w.guiActive = &mpMenu; w.UpdateRetainedMultiplayer();
        CHECK(w.guiRetainedMultiplayer == w.guiRetainedEscape && !w.retainedMultiplayerWelcome);
        // Each card has its own gate: with only ui_retained on, a card whose
        // pages still hand off leaves the stock menu to its openings.
        welcomeAnswer = true; auto gated = Mp(true, false); gated.UpdateRetainedMultiplayer();
        CHECK((gated.guiRetainedMultiplayer != nullptr) == (RETAINED_MP_WELCOME_MISSING_PAGES[0] == NULL));
        welcomeAnswer = false;
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


# Retained controls whose value is a list's selection rather than the draft
# setting itself; the pick operation their action names writes the setting.
RETAINED_SYSTEM_DERIVED_STATE = {'settings.display.mode.selected': 'r_mode', 'settings.display.refresh.selected': 'r_displayRefresh'}
# What each pick operation writes as its own choice: SystemDisplaySelectionPatch
# for the display lists, the preset expansion for its name. A plain edit writes
# its arguments. A control counts only for its operation's own writes.
OPERATION_WRITES = {'settings.system.display': {'r_screen'},
                    'settings.system.displayMode': {'r_mode', 'r_customWidth', 'r_customHeight'},
                    'settings.system.displayRefresh': {'r_displayRefresh'},
                    'settings.system.preset': {'com_performancePreset'}}
# The automatic values a display or size pick also returns: a size the new
# display lacks to Desktop Native, a rate the new choice lacks to Auto.
OPERATION_RESETS = {'settings.system.display': {'r_mode', 'r_displayRefresh'},
                    'settings.system.displayMode': {'r_displayRefresh'}}


def retained_system_document() -> dict:
    text = (ROOT / 'content/baseoq4/pak0/guis/menu/settings/system.q4ui').read_text(encoding='utf-8')
    return json.loads(re.sub(r'^\s*//.*$', '', text, flags=re.M))


def control_settings(value) -> set[str]:
    """The settings a control value reads: drafts, and list selections standing for one."""
    found = set()

    def expressions(item):
        if isinstance(item, dict):
            state = item.get('state')
            if isinstance(state, str) and state.startswith('settings.draft.'):
                found.add(state[len('settings.draft.'):])
            elif isinstance(state, str) and state in RETAINED_SYSTEM_DERIVED_STATE:
                found.add(RETAINED_SYSTEM_DERIVED_STATE[state])
            for child in item.values():
                expressions(child)
        elif isinstance(item, list):
            for child in item:
                expressions(child)

    expressions(value)
    return found


def retained_system_controls() -> set[str]:
    """Every setting the retained SYSTEM page has a control for: the settings the
    values of controls that act read."""
    found = set()

    def walk(node):
        control = node.get('control')
        if isinstance(control, dict) and 'value' in control and (control.get('action') or control.get('event')):
            found.update(control_settings(control['value']))
        for child in node.get('children', []):
            walk(child)

    walk(retained_system_document()['root'])
    return found


def check_retained_system_control_writes() -> None:
    """A control counts for a setting only when its action writes that setting."""
    document = retained_system_document()

    def walk(node):
        control = node.get('control')
        if isinstance(control, dict) and 'value' in control and control.get('action'):
            action = document['actions'][control['action']]
            operation = action['operation']
            writes = set(action.get('arguments', {})) if operation == 'settings.system.edit' else OPERATION_WRITES.get(operation)
            assert writes is not None, f'{node["id"]}: unknown write set for {operation}'
            missing = control_settings(control['value']) - writes
            assert not missing, f'{node["id"]} reads {sorted(missing)} but {control["action"]} ({operation}) does not write them'
        for child in node.get('children', []):
            walk(child)

    walk(document['root'])
    # The service's display picks write exactly the settings named above.
    display = (ROOT / 'src/ui/application/SystemDisplay.cpp').read_text(encoding='utf-8')
    patch = display[display.rindex('bool SystemDisplaySelectionPatch('):]
    patch = patch[:patch.index('\n}\n')]
    for key in sorted(set().union(*(OPERATION_WRITES[o] | OPERATION_RESETS.get(o, set()) for o in OPERATION_WRITES if o != 'settings.system.preset'))):
        assert f'result["{key}"]' in patch, f'SystemDisplaySelectionPatch no longer writes {key}'
    # Each branch writes what its operation is counted for: its own pick, and
    # the automatic values a display or size pick returns.
    device = patch[patch.index('if (list==SystemDisplayList::Device) {'):patch.index('} else if (list==SystemDisplayList::Mode) {')]
    mode = patch[patch.index('} else if (list==SystemDisplayList::Mode) {'):patch.rindex('} else {')]
    rate = patch[patch.rindex('} else {'):]
    assert 'result["r_screen"]=double(index);' in device, 'a display pick no longer writes r_screen'
    assert 'result["r_mode"]=-2.0;' in device and 'result["r_displayRefresh"]=0.0;' in device, 'a display pick no longer resets what the new display lacks'
    for key in ('r_mode', 'r_customWidth', 'r_customHeight'):
        assert f'result["{key}"]' in mode, f'a size pick no longer writes {key}'
    assert 'result["r_displayRefresh"]=0.0;' in mode, 'a size pick no longer resets a rate the new size lacks'
    assert 'result["r_displayRefresh"]=double(catalog.refresh[size_t(index)].rate);' in rate, 'a rate pick no longer writes its rate'


# ApplyClassOf, statement by statement: a change applies when its setting is
# Immediate or restarts the display, or is r_renderer or r_lightGridPreload;
# any other effect makes it Unsupported. retained_system_incomplete mirrors it.
APPLY_CLASS_STATEMENTS = ('if (item.effects==SystemSettingImmediate) continue;',
                          'if (item.effects==SystemSettingDisplayRestart) display=true;',
                          'else if (item.key=="r_renderer") renderer=true;',
                          'else if (item.key=="r_lightGridPreload") deferred=true;',
                          'else unsupported=true;')
# Page states that enable a control only on some renderers, with the function
# that publishes each one and the statement that makes it hold on every renderer
# the stock page's control worked on (ui_settings_display_service.py proves the
# statement's behaviour). Any other form is a reason the control is incomplete.
RENDERER_LIMITED_STATES = {'settings.msaaAvailable': ('src/ui/SettingsDisplayService.cpp',
                                                      'bool EngineSettingsDisplayHost::SupportsMultisampling() const {',
                                                      'return WindowMultisampling() || R_RendererModule_GetStatus().activeApi == RENDER_MODULE_API_VULKAN;',
                                                      'Vulkan')}
# The engine reaches a Number field's text through the native text owner;
# while no engine code constructs one, typed characters never arrive.
NATIVE_TEXT_OWNER = ('src/ui/application/ManagedNativeTextOwner.h', 'src/ui/application/ManagedNativeTextOwner.cpp')


def typed_text_reaches_numbers(adapter: str) -> bool:
    """Whether typed characters can reach a retained Number field: an event-queue
    character route in the adapter, or engine code that drives the native text owner."""
    handle = function_body(adapter, 'const char* idUserInterfaceRetained::HandleEvent(')
    if 'SE_CHAR' in handle and ('ApplyNumberInput' in handle or 'ApplyTextInput' in handle):
        return True
    owners = {ROOT / path for path in NATIVE_TEXT_OWNER}
    for folder in ('src/framework', 'src/sys', 'src/ui'):
        for path in (ROOT / folder).rglob('*'):
            if path.suffix in ('.cpp', '.h') and path not in owners and 'ManagedNativeTextOwner' in path.read_text(encoding='utf-8', errors='replace'):
                return True
    return False


def preset_targets() -> list[str]:
    """The settings a Performance Preset writes (PerformancePreset.cpp Targets)."""
    source = (ROOT / 'src/framework/PerformancePreset.cpp').read_text(encoding='utf-8')
    block = source[source.index('PerformancePresetTargetCount> Targets{{'):]
    return re.findall(r'"(\w+)"', block[:block.index('}};')])


def retained_system_catalog_effects() -> dict[str, str]:
    """Each catalog setting's effect as SystemSettingsHost::Catalog() declares it (lower-case keys)."""
    host = (ROOT / 'src/ui/application/SystemSettingsHost.cpp').read_text(encoding='utf-8')
    body = function_body(host, 'const std::vector<SystemSettingDescriptor>& SystemSettingsHost::Catalog() {')
    starts = list(re.finditer(r'\b(?:String|Boolean|Number)\("(\w+)"', body))
    assert starts, 'SystemSettingsHost::Catalog() declares no settings'
    effects = {}
    for index, start in enumerate(starts):
        span = body[start.end():starts[index + 1].start() if index + 1 < len(starts) else len(body)]
        named = re.findall(r'\bSystemSetting(\w+)\b', span)
        assert len(named) <= 1, f'{start.group(1)} declares more than one effect'
        effects[start.group(1).lower()] = named[0] if named else 'Immediate'
    return effects


def retained_system_incomplete(adapter: str) -> dict[str, str]:
    """The stock settings the retained SYSTEM page has a control for that cannot yet
    do what the stock page did, each with its reason, as the code states them."""
    document = retained_system_document()
    stock = {name.lower() for name in stock_system_settings()}
    enabled = {binding['node']: binding['value'] for binding in document['bindings'] if binding.get('property') == 'enabled'}
    roles: dict[str, set[str]] = {}
    limited: dict[str, set[str]] = {}

    def states(value) -> set[str]:
        found = set()
        if isinstance(value, dict):
            if isinstance(value.get('state'), str):
                found.add(value['state'])
            for child in value.values():
                found |= states(child)
        elif isinstance(value, list):
            for child in value:
                found |= states(child)
        return found

    def walk(node):
        control = node.get('control')
        if isinstance(control, dict) and 'value' in control:
            assert enabled.get(node['id'], True) is not False, f'{node["id"]} is never enabled'
            for key in control_settings(control['value']):
                key = key.lower()
                roles.setdefault(key, set()).add(control['role'])
                for state in states(enabled.get(node['id'])) & set(RENDERER_LIMITED_STATES):
                    limited.setdefault(key, set()).add(state)
        for child in node.get('children', []):
            walk(child)

    walk(document['root'])
    host = (ROOT / 'src/ui/application/SystemSettingsHost.cpp').read_text(encoding='utf-8')
    apply_class = function_body(host, 'SystemApplyClass SystemSettingsHost::ApplyClassOf(')
    for statement in APPLY_CLASS_STATEMENTS:
        assert statement in apply_class, f'ApplyClassOf changed ({statement}); update APPLY_CLASS_STATEMENTS and the mirror below'
    effects = retained_system_catalog_effects()
    typed = typed_text_reaches_numbers(adapter)

    def applies(key: str) -> bool:
        return effects[key] in ('Immediate', 'DisplayRestart') or key in ('r_renderer', 'r_lightgridpreload')

    def apply_class(key: str) -> str:
        return 'immediate' if effects[key] == 'Immediate' else 'display' if effects[key] == 'DisplayRestart' else key

    targets = [target.lower() for target in preset_targets()]
    reasons = {}
    for key in sorted(stock & set(roles)):
        assert key in effects, f'{key} has a retained control but no SystemSettingsHost catalog entry'
        if key == 'com_performancepreset':
            # A preset writes its targets: Apply needs every one to apply, in one class.
            assert targets and all(target in effects for target in targets), 'a preset target has no SystemSettingsHost catalog entry'
            blocked = sorted(target for target in targets if not applies(target))
            classes = {apply_class(target) for target in targets if applies(target)} - {'immediate'}
            if blocked or not applies(key) or len(classes) > 1:
                reasons[key] = (f'a preset writes {", ".join(blocked) or "settings"} whose effects have no apply path, '
                                'or mixes apply classes (ApplyClassOf: Unsupported or Mixed)')
        elif not applies(key):
            reasons[key] = f'its {effects[key]} effect has no apply path (ApplyClassOf: Unsupported)'
        elif not typed and roles[key] == {'number'}:
            reasons[key] = 'only number fields offer it, and typed characters reach no retained Number field'
        else:
            for state in sorted(limited.get(key, ())):
                path, signature, statement, renderer = RENDERER_LIMITED_STATES[state]
                if statement not in function_body((ROOT / path).read_text(encoding='utf-8'), signature):
                    reasons[key] = f'its control needs {state}, which {signature.split("::")[-1].split("(")[0]} does not publish for {renderer}'
    # The stock page's Auto-Detect is a button, not a setting row; the retained
    # page keeps its own.
    assert any(action['operation'] == 'settings.system.autodetect' for action in document['actions'].values()), 'the retained SYSTEM page lost Auto-Detect'
    return reasons


def player_setting_rules(adapter: str) -> dict:
    """The adapter's player settings (FindPlayerSetting): each setting's list
    of values, by the name its rule gives (empty for a range or a Boolean)."""
    body = function_body(adapter, 'const PlayerSetting* FindPlayerSetting(')
    lists = {name: re.findall(r'"([^"]*)"', items) for name, items in re.findall(r'static const std::vector<std::string> (\w+) = \{([^}]*)\};', body)}
    rules = {}
    for cvar, rule in re.findall(r'\{"(\w+)",\{([^{}]*(?:\{[^}]*\})?)\}\}', body):
        named = re.search(r',(\w+)$', rule.strip())
        inline = re.search(r'\{([^}]*)\}', rule)
        rules[cvar] = lists[named.group(1)] if named and named.group(1) in lists else re.findall(r'"([^"]*)"', inline.group(1)) if inline else []
    return rules


def cpp_allowlist(text: str, function: str = 'bool SessionMenuCommand(') -> set[str]:
    block = function_body(text, function)
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


HOLD = r"""
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
static int checks = 0;
#define CHECK(x) do { ++checks; if (!(x)) { std::fprintf(stderr, "check failed line %d: %s\n", __LINE__, #x); std::abort(); } } while (false)
struct idStr {
    static int Icmp(const char* a, const char* b) {
        for (;; ++a, ++b) {
            const int x = *a >= 'A' && *a <= 'Z' ? *a + 32 : *a, y = *b >= 'A' && *b <= 'Z' ? *b + 32 : *b;
            if (x != y) return x - y;
            if (!x) return 0;
        }
    }
};
struct idUserInterface {
    std::string name; bool gameDraw = false; std::vector<std::string> events;
    idUserInterface(const char* path, bool draw = false) : name(path), gameDraw(draw) {}
    struct View { bool gameDraw; bool GetBool(const char* key) const { return !std::strcmp(key, "gameDraw") && gameDraw; } };
    View State() const { return {gameDraw}; }
    const char* Name() const { return name.c_str(); }
    void HandleNamedEvent(const char* event) { events.push_back(event); }
};
struct idStrList {
    std::vector<std::string> items;
    int FindIndex(const char* text) const {
        for (size_t i = 0; i < items.size(); ++i) if (items[i] == text) return static_cast<int>(i);
        return -1;
    }
};
static const char* const RETAINED_MP_WELCOME_GUI = "guis/menu/mp_welcome.q4ui";
static bool welcomeEnabled = true, modMenu = false, retainedOpen = false;
static bool Session_RetainedMultiplayerEnabled(bool welcome) { return welcome && welcomeEnabled; }
static bool Session_ModSuppliesFile(const char* path) { return modMenu && !std::strcmp(path, "guis/mpmain.gui"); }
static bool RetainedUI_IsOpen() { return retainedOpen; }
struct Common {
    int now = 1000; std::string output;
    int GetPresentationTime() const { return now; }
    void Printf(const char* fmt, ...) { char text[512]; va_list args; va_start(args, fmt); std::vsnprintf(text, sizeof(text), fmt, args); va_end(args); output += text; }
} commonObject, *common = &commonObject;
struct CVarSystem {
    bool autoJoin = false;
    bool GetCVarBool(const char* name) const { return !std::strcmp(name, "ui_autoJoin") ? autoJoin : !std::strcmp(name, "ui_retainedTrace"); }
} cvarObject, *cvarSystem = &cvarObject;
struct MultiViewDemo { bool playing = false; bool IsPlaying() const { return playing; } };
struct idAsyncNetwork { static MultiViewDemo multiViewDemo; };
MultiViewDemo idAsyncNetwork::multiViewDemo;
class idSessionLocal {
public:
    bool multiplayer = true; void* readDemo = nullptr;
    bool IsMultiplayer() { return multiplayer; }
    bool retainedLoadingActive = true, mapSpawned = false, insideExecuteMapChange = false, retainedMultiplayerUncovered = false;
    idUserInterface *guiLoading = nullptr, *guiLoadingHold = nullptr, *guiRetainedMultiplayer = nullptr, *guiActive = nullptr;
    int retainedLoadingHoldBegan = 0, retainedLoadingHoldLive = 0, retainedLoadingHoldUntil = 0;
    bool retainedLoadingHoldFading = false;
    idStrList retainedStock;
    bool BeginRetainedLoadingHold(); void FadeRetainedLoadingHold(const char* reason);
    void UpdateRetainedLoadingHold(); void ClearRetainedLoadingHold();
};
"""

HOLD_MAIN = r"""
static idUserInterface loading{"guis/loading/loading.q4ui"}, menu{"guis/mpmain.gui", true}, card{"guis/menu/mp_welcome.q4ui"},
    chat{"guis/mpchat.gui", true};
// A session at the end of a multiplayer load that the retained screen presented.
static idSessionLocal Loaded() {
    idSessionLocal session; session.guiLoading = &loading; loading.events.clear(); common->output.clear(); common->now = 1000;
    return session;
}
// One frame: the clock, then the hold's update at the top of the frame.
static void Frame(idSessionLocal& session, int now) { common->now = now; session.UpdateRetainedLoadingHold(); }
static bool Held(const idSessionLocal& session) { return session.guiLoadingHold == &loading; }
static bool Traced(const char* line) { return common->output.find(line) != std::string::npos; }

int main() {
    // Only a Welcome join keeps the screen: the retained screen presented the
    // load, it is multiplayer and no demo, ui_autoJoin is off and the card can
    // present (its gate, no fallback, no mod menu).
    struct Refusal { const char* why; void (*set)(idSessionLocal&, bool); };
    const Refusal refusals[] = {
        {"stock screen", [](idSessionLocal& s, bool on) { s.retainedLoadingActive = !on; }},
        {"no screen", [](idSessionLocal& s, bool on) { s.guiLoading = on ? nullptr : &loading; }},
        {"single player", [](idSessionLocal& s, bool on) { s.multiplayer = !on; }},
        {"demo", [](idSessionLocal& s, bool on) { static int demo; s.readDemo = on ? &demo : nullptr; }},
        {"multiview demo", [](idSessionLocal&, bool on) { idAsyncNetwork::multiViewDemo.playing = on; }},
        {"auto join", [](idSessionLocal&, bool on) { cvarSystem->autoJoin = on; }},
        {"card off", [](idSessionLocal&, bool on) { welcomeEnabled = !on; }},
        {"card fell back", [](idSessionLocal& s, bool on) { s.retainedStock.items = on ? std::vector<std::string>{RETAINED_MP_WELCOME_GUI} : std::vector<std::string>{}; }},
        {"mod menu", [](idSessionLocal&, bool on) { modMenu = on; }},
    };
    for (const Refusal& refusal : refusals) {
        idSessionLocal session = Loaded();
        refusal.set(session, true);
        CHECK(!session.BeginRetainedLoadingHold() && session.guiLoadingHold == nullptr);
        refusal.set(session, false);
        CHECK(session.BeginRetainedLoadingHold() && Held(session));
    }
    // A listen server: the card presents in the frame the load ends, on the
    // clock the load left standing; the fade waits for the clock to move.
    {
        idSessionLocal session = Loaded();
        CHECK(session.BeginRetainedLoadingHold() && Traced("RETAINED_LOADING_HOLD begin"));
        session.mapSpawned = true;
        session.guiActive = &menu; session.guiRetainedMultiplayer = &card;
        Frame(session, 1000);
        CHECK(Held(session) && loading.events.empty() && !session.retainedLoadingHoldFading);
        session.FadeRetainedLoadingHold("card");
        CHECK(loading.events.empty());
        Frame(session, 3700);
        CHECK(loading.events == std::vector<std::string>{"handoff"} && session.retainedLoadingHoldFading);
        CHECK(Traced("RETAINED_LOADING_HOLD fade=card waited=0"));
        Frame(session, 3700 + RETAINED_LOADING_HANDOFF_MSEC - 1);
        CHECK(Held(session));
        Frame(session, 3700 + RETAINED_LOADING_HANDOFF_MSEC);
        CHECK(session.guiLoadingHold == nullptr && loading.events.size() == 1 && Traced("end faded="));
    }
    // A remote client: the card comes seconds later; its first frame draws
    // under the screen and the fade starts on the next.
    {
        idSessionLocal session = Loaded();
        CHECK(session.BeginRetainedLoadingHold());
        session.mapSpawned = true;
        Frame(session, 1000);
        for (int now = 1016; now < 3016; now += 16) {
            Frame(session, now);
            CHECK(Held(session) && loading.events.empty());
        }
        Frame(session, 3016);
        session.guiActive = &menu; session.guiRetainedMultiplayer = &card;
        CHECK(loading.events.empty());
        Frame(session, 3270);
        CHECK(loading.events == std::vector<std::string>{"handoff"} && Traced("fade=card waited=2254"));
    }
    // No card: the hold gives up after its ceiling, counted from the first
    // frame the clock moves, however far it jumped.
    {
        idSessionLocal session = Loaded();
        CHECK(session.BeginRetainedLoadingHold());
        session.mapSpawned = true;
        const int live = 1000 + RETAINED_LOADING_HOLD_MSEC + 500;
        Frame(session, live);
        CHECK(Held(session) && loading.events.empty());
        Frame(session, live + RETAINED_LOADING_HOLD_MSEC - 1);
        CHECK(loading.events.empty());
        Frame(session, live + RETAINED_LOADING_HOLD_MSEC);
        CHECK(loading.events == std::vector<std::string>{"handoff"} && Traced("fade=expired"));
        Frame(session, live + RETAINED_LOADING_HOLD_MSEC + RETAINED_LOADING_HANDOFF_MSEC);
        CHECK(session.guiLoadingHold == nullptr);
    }
    // The game's menu waiting for its card keeps the screen; anything else
    // that takes the screen ends the hold: another GUI, the stock menu
    // presenting in the card's place, a retained modal.
    {
        idSessionLocal session = Loaded();
        CHECK(session.BeginRetainedLoadingHold());
        session.mapSpawned = true;
        session.guiActive = &menu;
        Frame(session, 1100);
        CHECK(Held(session) && loading.events.empty());
        struct Screen { idUserInterface* active; bool uncovered; bool modal; };
        for (const Screen& screen : {Screen{&chat, false, false}, Screen{&menu, true, false}, Screen{nullptr, false, true}}) {
            idSessionLocal other = Loaded();
            CHECK(other.BeginRetainedLoadingHold());
            other.mapSpawned = true;
            other.guiActive = screen.active; other.retainedMultiplayerUncovered = screen.uncovered; retainedOpen = screen.modal;
            Frame(other, 1100);
            CHECK(loading.events == std::vector<std::string>{"handoff"} && Traced("fade=screen"));
            retainedOpen = false;
        }
    }
    // A new load or a stop drops the hold at once, without a fade.
    {
        idSessionLocal session = Loaded();
        CHECK(session.BeginRetainedLoadingHold());
        session.mapSpawned = true;
        session.insideExecuteMapChange = true;
        Frame(session, 1100);
        CHECK(session.guiLoadingHold == nullptr && loading.events.empty());
        idSessionLocal stopped = Loaded();
        CHECK(stopped.BeginRetainedLoadingHold());
        Frame(stopped, 1100);
        CHECK(stopped.guiLoadingHold == nullptr && loading.events.empty());
        stopped.mapSpawned = true;
        CHECK(stopped.BeginRetainedLoadingHold() && Held(stopped));
        stopped.ClearRetainedLoadingHold();
        CHECK(stopped.guiLoadingHold == nullptr && stopped.retainedLoadingHoldBegan == 0 && stopped.retainedLoadingHoldLive == 0 &&
              stopped.retainedLoadingHoldUntil == 0 && !stopped.retainedLoadingHoldFading);
    }
    std::printf("ui_retained gate: %d loading hold checks passed\n", checks);
    return 0;
}
"""


def check_loading_hold(compiler: str, directory: Path) -> None:
    """The loading screen held over a Welcome join (section 14.17): compile the
    production hold against a stand-in session and drive the listen server's
    and the remote client's joins, the ceiling, the screens that end it and
    the drops; then pin where the session calls it, and the loading
    document's hand-off."""
    menu = (ROOT / 'src/framework/Session_menu.cpp').read_text(encoding='utf-8')
    session = (ROOT / 'src/framework/Session.cpp').read_text(encoding='utf-8')
    constants = '\n'.join(re.search(rf'static const int {name} = \d+;', menu).group(0)
                          for name in ('RETAINED_LOADING_HOLD_MSEC', 'RETAINED_LOADING_HANDOFF_MSEC'))
    bodies = [constants, function_body(menu, 'static bool Session_IsGameMenu(')]
    bodies += [function_body(menu, f'{kind} idSessionLocal::{name}(') for kind, name in (
        ('bool', 'BeginRetainedLoadingHold'), ('void', 'FadeRetainedLoadingHold'), ('void', 'UpdateRetainedLoadingHold'),
        ('void', 'ClearRetainedLoadingHold'))]
    source = directory / 'hold.cpp'
    binary = directory / 'hold.exe'
    source.write_text(HOLD + '\n'.join(bodies) + HOLD_MAIN, encoding='utf-8')
    subprocess.run([compiler, '-std=c++20', '-Wall', '-Wextra', '-Wno-unused-function', str(source), '-o', str(binary)], check=True)
    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=60)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    assert result.returncode == 0, 'the loading hold checks failed'
    menu_lf, session_lf = menu.replace('\r\n', '\n'), session.replace('\r\n', '\n')
    # The load ends with the hold or, without it, the wipe; the hold must ask
    # while the retained screen still presents the load.
    change = function_body(session_lf, 'void idSessionLocal::ExecuteMapChange(')
    assert '\tif ( !BeginRetainedLoadingHold() ) {\n\t\tStartWipe( "gfx/wipes/fade_blend" );\n\t}' in change
    assert change.index('ClearRetainedLoadingHold();') < change.index('BeginRetainedLoadingHold()') < change.index('retainedLoadingActive = false;\n\n\tSys_SetPhysicalWorkMemory')
    # Drawn above the game and its menu, under the wipe and the console.
    draw = function_body(session_lf, 'void idSessionLocal::Draw(')
    held = draw.index('guiLoadingHold->Redraw( presentationTime );')
    assert draw.index('} else if ( mapSpawned ) {') < held < draw.index('RetainedUI_Draw();') < draw.index('DrawWipeModel();')
    # Updated at the top of every frame, before the card's update, and user
    # commands wait while it holds.
    frame = function_body(menu_lf, 'void idSessionLocal::GuiFrameEvents(')
    assert frame.index('UpdateRetainedLoadingHold();') < frame.index('usercmdGen->InhibitUsercmd') < frame.index('UpdateRetainedMultiplayer();')
    assert 'guiTest || RetainedUI_IsOpen() || guiLoadingHold != NULL ) {' in frame
    assert 'FadeRetainedLoadingHold' not in function_body(menu, 'void idSessionLocal::UpdateRetainedMultiplayer('), \
        'the card fades the hold from the next frame, not its own'
    assert 'ClearRetainedLoadingHold();' in function_body(session, 'void idSessionLocal::Clear(')
    assert 'ClearRetainedLoadingHold();' in function_body(session, 'void idSessionLocal::StopInternal(')
    assert 'retained->HandleNamedEvent( "present" );' in function_body(menu, 'idUserInterface *idSessionLocal::SelectRetainedLoadingGui(')
    # The loading document's hand-off: the whole screen fades over the
    # session's hand-off time, and present makes it whole again.
    text = (ROOT / 'content/baseoq4/pak0/guis/loading/loading.q4ui').read_text(encoding='utf-8')
    document = json.loads(re.sub(r'^\s*//.*$', '', text, flags=re.M))
    handoff_ms = int(re.search(r'RETAINED_LOADING_HANDOFF_MSEC = (\d+);', menu).group(1))
    timelines = {timeline['id']: timeline for timeline in document['timelines']}
    fade = timelines['handoff']
    assert fade['durationMs'] == handoff_ms and len(fade['tracks']) == 1
    track = fade['tracks'][0]
    assert track['node'] == document['root']['id'] == 'screen' and track['property'] == 'opacity'
    assert [key['value']['value'] for key in track['keys']] == [1, 0] and track['keys'][-1]['atMs'] == handoff_ms
    assert [key['value']['value'] for key in timelines['present']['tracks'][0]['keys']] == [1, 1]
    assert document['events']['handoff'] == [{'op': 'playTimeline', 'timeline': 'handoff'}]
    assert document['events']['present'] == [{'op': 'playTimeline', 'timeline': 'present'}]
    assert document['root']['properties']['opacity']['value'] == 1



def check_retained_match(menu: str) -> None:
    """The Match page's contracts that the compiled cases cannot see: the card's
    action indices, the session's tokens and the game's own Match Control
    commands agree; the game mirrors the operations the page shows, with the
    page's status lines, labels and list rows; the session's lists are the
    game's own selection commands and its roles the protocol's; the page asks
    first exactly where Match Control confirms, with the stock modal's text;
    the triggers page its sections."""
    sys.path.insert(0, str(ROOT / 'tools/ui'))
    import retained_mp_menus as cards
    tokens = tuple(re.findall(r'"([a-z_]+)"', re.search(r'RETAINED_MP_MATCH_TOKENS\[\] = \{([^}]*)\};', menu).group(1)))
    assert tokens == cards.MATCH_TOKENS, 'the session and the Match page name its actions alike'
    mp_game = (ROOT / 'src/mpgame/MultiplayerGame.cpp').read_text(encoding='utf-8')
    model = (ROOT / 'src/mpgame/mp/match/MatchControlModel.cpp').read_text(encoding='utf-8')
    handler = function_body(mp_game, 'bool idMultiplayerGame::HandleMatchControlCommand(')
    for token in tokens:
        assert f'"{token}"' in mp_game or f'"{token}"' in model, f'Match Control has no "{token}" command'
    assert '"refresh"' in handler and '"confirm"' in handler and '"cancel_confirm"' in handler
    # The game's mirrored operations, by name, prefix and label: each section's
    # actions in the page's order, the referee's between them. Where the
    # projection names an action, it names it with the page's alternatives.
    table = mp_game[mp_game.index('static const retainedMatchOperation_t RETAINED_MATCH_OPERATIONS[] = {'):]
    operations = re.findall(r'\{ "(\w+)", "(\w+)", "(#str_\d+)", (NULL|"\w+") \},', table[:table.index('};')])
    names = [name for name, _prefix, _label, _state in operations]
    assert names == [name for name, *_ in cards.MATCH_STATUS_ACTIONS] + ['referee_login', 'referee_logout'] + \
        [name for name, *_ in cards.MATCH_TEAM_ACTIONS], names
    prefixes = {name: prefix for name, prefix, _label, _state in operations}
    projection = (ROOT / 'src/mpgame/mp/match/MatchControlProjection.cpp').read_text(encoding='utf-8')
    named = {'ready': ('match_ready_action', '#str_41714'), 'team_lock': ('match_team_lock_action', '#str_41735'),
             'broadcaster': ('match_broadcaster_action', '#str_41796')}
    for name, _token, accessible, _body in cards.MATCH_ACTIONS:
        _prefix, label, state = next(entry[1:] for entry in operations if entry[0] == name)
        assert label == accessible, (name, label)
        assert state == (f'"{named[name][0]}"' if name in named else 'NULL'), (name, state)
        if name in named:
            # The projection writes the stock label or its alternative, both of
            # which the page's label column fits.
            assert f'"{named[name][1]}" : "{accessible}"' in projection, name
            assert {accessible, named[name][1]} <= set(cards.MATCH_STATUS_LABELS + cards.MATCH_TEAM_LABELS), name
            assert f'gui.SetStateString( "{named[name][0]}"' in projection, name
    header = (ROOT / 'src/mpgame/MultiplayerGame.h').read_text(encoding='utf-8')
    assert int(re.search(r'RETAINED_MATCH_STATUS_LINES = (\d+);', header).group(1)) == cards.MATCH_STATUS_LINES
    # The lists: the session's stock lists and tokens are the game's own
    # selection commands, in the card's order; a row index spans the longest
    # list; the game mirrors as many rows as the page has.
    lists = re.findall(r'\{ "(match_\w+_rows)", "(select_\w+)" \}',
                       menu[menu.index('RETAINED_MP_MATCH_LISTS[][2] = {'):menu.index('RETAINED_MP_MATCH_LIST_COUNT')])
    assert [list_name for list_name, _token in lists] == [f'match_{key}_rows' for key in cards.MATCH_LISTS], lists
    for list_name, token in lists:
        assert f'{{ "{token}", "{list_name}_sel_0",' in handler, (list_name, token)
    model_header = (ROOT / 'src/mpgame/mp/match/MatchControlModel.h').read_text(encoding='utf-8')
    longest = max(int(value) for value in re.findall(r'MP_MATCH_CONTROL_MAX_\w+_ROWS = (\d+);', model_header))
    assert int(re.search(r'RETAINED_MP_MATCH_ROWS = (\d+);', menu).group(1)) == longest == 128
    assert int(re.search(r'RETAINED_MATCH_TEAM_ROWS = (\d+);', header).group(1)) == cards.MATCH_TEAM_ROWS
    assert int(re.search(r'RETAINED_MATCH_REPLACEMENT_ROWS = (\d+);', header).group(1)) == cards.MATCH_REPLACEMENT_ROWS
    # The role choice: the protocol's roster roles, 1 to 4, by the projection's
    # own names for them; the game reads the stock choice's value.
    assert int(re.search(r'RETAINED_MP_MATCH_ROLES = (\d+);', menu).group(1)) == len(cards.MATCH_ROLES)
    protocol_header = (ROOT / 'src/mpgame/mp/match/MatchProtocol.h').read_text(encoding='utf-8')
    localization = (ROOT / 'src/mpgame/mp/match/MatchControlLocalization.cpp').read_text(encoding='utf-8')
    role_keys = function_body(localization, 'const char *MPMatchControlProtocolRosterRoleKey(')
    for key, value in cards.MATCH_ROLES:
        role = re.search(rf'MP_MATCH_PROTOCOL_ROSTER_ROLE_(\w+) = {value}', protocol_header).group(1)
        assert f'case MP_MATCH_PROTOCOL_ROSTER_ROLE_{role}: return "{key}";' in role_keys, (key, value)
    assert 'parseStateInteger( "match_role_choice",' in handler
    # Players' names reach the page only as plain text, which never translates.
    lister = function_body(mp_game, 'void idMultiplayerGame::PublishRetainedMatchList(')
    matcher = function_body(mp_game, 'void idMultiplayerGame::PublishRetainedMatch(')
    assert 'MPRetainedPlainText( cells[ column ].c_str(), 128, 1 )' in lister, 'list cells are plain text'
    assert 'MPRetainedPlainText( lines[ i ].c_str(), 1024, 1 )' in matcher and \
        'MPRetainedPlainText( state.GetString( "match_result_message" ), 1024, 4 )' in matcher, 'state lines and the result are plain text'
    publisher = function_body(mp_game, 'void idMultiplayerGame::PublishRetainedMenu(').replace('\r\n', '\n')
    assert '\tif ( !RetainedMenuWelcome() ) {\n\t\tPublishRetainedMatch( card, changed );' in publisher, 'only the Escape card has a Match page'
    # Each prefix is a protocol operation the projection decides; the page asks
    # first exactly where its descriptor carries a confirmation.
    protocol = (ROOT / 'src/mpgame/mp/match/MatchProtocol.cpp').read_text(encoding='utf-8')
    descriptors = dict(re.findall(r'\{ MP_MATCH_OP_\w+, "(\w+)",\s+MP_MATCH_LOCALIZATION_OPERATION_\w+,\s+(MP_MATCH_LOCALIZATION_\w+),', protocol))
    assert len(descriptors) == protocol.count('{ MP_MATCH_OP_'), 'every protocol descriptor reads'
    stock = (ROOT / 'content/baseoq4/pak0/guis/matchcontrol.gui').read_text(encoding='utf-8')
    for name, token, _accessible, body in cards.MATCH_ACTIONS:
        confirmed = descriptors[prefixes[name]] != 'MP_MATCH_LOCALIZATION_NONE'
        assert (body is not None) == confirmed == token.startswith('arm_'), (name, token, confirmed)
        if body is not None:
            # The stock button arms the token, then shows its modal with the body.
            after = stock[stock.index(f'"matchControl {token}"'):]
            assert re.search(r'"match_confirm_body::text" "(#str_\d+)"', after).group(1) == body, (token, body)
    for name in ('referee_login', 'referee_logout'):
        assert descriptors[prefixes[name]] == 'MP_MATCH_LOCALIZATION_NONE'
    adapter = (ROOT / 'src/ui/UserInterfaceRetained.cpp').read_text(encoding='utf-8')
    assert 'key == K_JOY16 ? "onSectionPrevious" : key == K_JOY15 ? "onSectionNext"' in adapter, 'the triggers page sections'
    assert {'mpMatch', 'mpMatchSelect'} <= cpp_allowlist(adapter)
    assert 'mpMatchRole' in cpp_allowlist(adapter, 'bool SessionMenuValueCommand(')


def prompt_bar_fits(document: dict, name: str) -> None:
    """The card's prompt bar, measured from the document itself in every
    language's shipped faces (its texts, sizes, paddings and margins), fits
    inside the card's insets: the generator fits the card to the bar, and the
    native test's host cannot see real text widths."""
    import build_retained_screens as screens
    import retained_mp_menus

    def find(node, ident):
        if node['id'] == ident:
            return node
        for child in node.get('children', []):
            found = find(child, ident)
            if found:
                return found
        return None

    def dp(node, key):
        value = node.get('properties', {}).get(key)
        return float(value['value']) if value and value.get('unit') == 'dp' else 0.0

    def width(node, language):
        props = node.get('properties', {})
        if props.get('position', {}).get('value') == 'absolute':
            return 0.0
        outer = dp(node, 'margin-left') + dp(node, 'margin-right')
        if node['type'] == 'text':
            text = retained_mp_menus.any_text(props['text']['value'])[language]
            return outer + screens.text_width(props['font-family']['value'], text, props['font-size']['value'])
        inner = dp(node, 'padding-left') + dp(node, 'padding-right')
        return outer + inner + sum(width(child, language) for child in node.get('children', []))

    card = find(document['root'], 'card')
    room = card['properties']['width']['value'] - 2 * retained_mp_menus.INSET
    bar = find(document['root'], 'prompts')
    items = [child for child in bar['children'] if child['id'] != 'prompt-spacer']
    for language in screens.LANGUAGES:
        needed = sum(width(item, language) for item in items)
        assert needed <= room, f'{name}: the {language} prompt bar needs {needed:.0f} dp, past the card\'s {room:g} dp'


def check_retained_multiplayer(menu: str, session: str) -> None:
    """The multiplayer card's contracts that the compiled cases cannot see:
    its opt-in and missing pages, the game's side of the cover protocol, the
    frame, input and draw order, and the document the generator writes."""
    assert 'idCVar ui_retainedMultiplayer( "ui_retainedMultiplayer", "0", CVAR_GUI | CVAR_BOOL' in menu
    assert ('const char *const *missing = welcome ? RETAINED_MP_WELCOME_MISSING_PAGES : RETAINED_MP_ESCAPE_MISSING_PAGES;\n'
            '\treturn ui_retainedMultiplayer.GetBool() || ( Session_RetainedScreensEnabled() && missing[0] == NULL );') in menu.replace('\r\n', '\n')
    sys.path.insert(0, str(ROOT / 'tools' / 'ui'))
    import retained_mp_menus
    text = (ROOT / 'content/baseoq4/pak0/guis/menu/mp_escape.q4ui').read_text(encoding='utf-8')
    document = json.loads(re.sub(r'^\s*//.*$', '', text, flags=re.M))
    # A page is missing while it hands off to its stock page.
    handoffs = {name[len('stock_'):] for name in document['events'] if name.startswith('stock_')}
    missing = re.search(r'RETAINED_MP_ESCAPE_MISSING_PAGES\[\] = \{([^}]*)\};', menu).group(1)
    assert missing.strip().endswith('NULL'), 'the missing-pages list must stay NULL-terminated'
    listed = set(re.findall(r'"([a-z]+)"', missing))
    assert listed == handoffs, f'RETAINED_MP_ESCAPE_MISSING_PAGES lists {sorted(listed)}; the card hands off {sorted(handoffs)}'
    pages = re.search(r'RETAINED_MP_STOCK_PAGES\[\] = \{([^}]*)\};', menu).group(1)
    assert re.findall(r'"([a-z_]+)"', pages) == [window for _ident, _key, window in retained_mp_menus.ESCAPE_TABS]
    stock_menu = (ROOT / 'content/baseoq4/pak0/guis/mpmain.gui').read_text(encoding='utf-8', errors='replace')
    for window in re.findall(r'"([a-z_]+)"', pages):
        assert f'windowDef {window}\n' in stock_menu.replace('\r\n', '\n'), f'the stock menu has no {window}'
    for index, (ident, _key, _window) in enumerate(retained_mp_menus.ESCAPE_TABS):
        event = document['events'].get(f'stock_{ident}')
        if event is not None:
            assert event == [{'op': 'setState', 'values': {'card.stock_page': index}}, {'op': 'action', 'action': 'mpStockPage'}], ident
    # The Welcome card: its missing pages are its hand-offs, and each presses
    # the join panel's button for its page.
    welcome_text = (ROOT / 'content/baseoq4/pak0/guis/menu/mp_welcome.q4ui').read_text(encoding='utf-8')
    welcome_document = json.loads(re.sub(r'^\s*//.*$', '', welcome_text, flags=re.M))
    welcome_handoffs = {name[len('stock_'):] for name in welcome_document['events'] if name.startswith('stock_')}
    welcome_missing = re.search(r'RETAINED_MP_WELCOME_MISSING_PAGES\[\] = \{([^}]*)\};', menu).group(1)
    assert welcome_missing.strip().endswith('NULL') and set(re.findall(r'"([a-z]+)"', welcome_missing)) == welcome_handoffs
    welcome_pages = re.search(r'RETAINED_MP_WELCOME_STOCK_PAGES\[\] = \{([^}]*)\};', menu).group(1)
    assert [None if item.strip() == 'NULL' else item.strip().strip('"') for item in welcome_pages.split(',')] == \
        [window for _ident, _key, window in retained_mp_menus.WELCOME_TABS]
    # Once the join panel has closed, the same pages hand off to the menu
    # column's buttons, the Escape card's.
    menu_pages = re.search(r'RETAINED_MP_WELCOME_MENU_PAGES\[\] = \{([^}]*)\};', menu).group(1)
    escape_windows = {ident: window for ident, _key, window in retained_mp_menus.ESCAPE_TABS}
    assert [None if item.strip() == 'NULL' else item.strip().strip('"') for item in menu_pages.split(',')] == \
        [None if window is None else escape_windows[ident] for ident, _key, window in retained_mp_menus.WELCOME_TABS]
    for index, (ident, _key, window) in enumerate(retained_mp_menus.WELCOME_TABS):
        if window is not None:
            assert f'windowDef {window}\n' in stock_menu.replace('\r\n', '\n'), f'the stock menu has no {window}'
            # A built page hands off only what it cannot edit yet (name and clan).
            handoff = welcome_document['events'].get(f'stock_{ident}', welcome_document['events'].get(f'classic_{ident}'))
            assert handoff == [{'op': 'setState', 'values': {'card.stock_page': index}}, {'op': 'action', 'action': 'mpStockPage'}], ident
    escape_settings = [index for index, (ident, _key, _window) in enumerate(retained_mp_menus.ESCAPE_TABS) if ident == 'settings'][0]
    assert document['events']['classic_settings'] == [{'op': 'setState', 'values': {'card.stock_page': escape_settings}},
                                                      {'op': 'action', 'action': 'mpStockPage'}]
    assert welcome_document['events']['onBack'] == [{'op': 'action', 'action': 'mpClose'}]
    prompt_bar_fits(document, 'mp_escape')
    prompt_bar_fits(welcome_document, 'mp_welcome')
    # The game answers the protocol the session expects, and its menu stops
    # drawing while covered.
    protocol = int(re.search(r'static const int RETAINED_MP_PROTOCOL = (\d+);', menu).group(1))
    mp_game = (ROOT / 'src/mpgame/MultiplayerGame.cpp').read_text(encoding='utf-8', errors='replace')
    assert f'static const int RETAINED_MENU_PROTOCOL = {protocol};' in mp_game
    cover = function_body(mp_game, 'void idMultiplayerGame::SetRetainedMenuCover(')
    assert 'card->SetStateInt( "mp.protocol", RETAINED_MENU_PROTOCOL );' in cover
    # The join offer is the Welcome card's; the card's softening replaces the join panel's blur.
    assert 'const bool allowed = currentMenu == 1 && mainGui != NULL && !IsArenaCampaignMatch();' in cover
    assert cover.index('retainedMenuCovered = true;') < cover.index('SetJoinScreenSoftFocus( false );')
    assert ('return joinScreenPending || ( player != NULL && player->spectating && !cvarSystem->GetCVarBool( "ui_joined" ) &&\n'
            '\t\t!cvarSystem->GetCVarBool( "ui_autoJoin" ) );' in function_body(mp_game, 'bool idMultiplayerGame::RetainedMenuWelcome(').replace('\r\n', '\n'))
    draw = function_body(mp_game, 'bool idMultiplayerGame::Draw(')
    assert 'if ( !retainedMenuCovered ) {\n\t\t\t\tmainGui->Redraw( gameLocal.time );' in draw.replace('\r\n', '\n')
    assert 'retainedMenuCovered = false;' in function_body(mp_game, 'void idMultiplayerGame::DisableMenu(')
    mp_local = (ROOT / 'src/mpgame/Game_local.cpp').read_text(encoding='utf-8', errors='replace')
    for verb, call in (('retainedMultiplayerVariant', 'gui->SetStateBool( "mp.welcome", mpGame.RetainedMenuWelcome() );'),
                       ('retainedMultiplayerCover', 'mpGame.SetRetainedMenuCover( true, gui );'),
                       ('retainedMultiplayerUncover', 'mpGame.SetRetainedMenuCover( false, gui );'),
                       ('retainedMultiplayerState', 'mpGame.PublishRetainedMenu( gui );')):
        answer = mp_local[mp_local.index(f'!idStr::Icmp( menuCommand, "{verb}" )'):]
        assert call in answer[:answer.index('} else if')], verb
    # The frame pump updates the card before its no-GUI return, input reaches
    # the card after the home screen's, and the card draws in the menu's place.
    frame = function_body(menu, 'void idSessionLocal::GuiFrameEvents(')
    assert frame.index('UpdateRetainedSubpage();') < frame.index('UpdateRetainedMultiplayer();') < frame.index('RetainedMultiplayerFrameEvent();') < \
        frame.index('ClearMenuControllerRepeatState();\n\t\treturn;\n\t}\n\n\tif ( guiActive ) {')
    menu_event = function_body(menu, 'void idSessionLocal::MenuEvent(')
    assert menu_event.index('if ( guiRetainedHome != NULL && guiActive == guiMainMenu ) {') < menu_event.index('if ( RetainedMultiplayerCovers() ) {') < \
        menu_event.index('menuCommand = guiActive->HandleEvent(')
    dispatch = function_body(menu, 'void idSessionLocal::DispatchCommand(')
    assert 'else if ( gui == guiRetainedMultiplayer ) HandleRetainedMultiplayerRequest( gui, "mpClose" );' in dispatch
    assert 'HandleGameMenuReturn( game->HandleGuiCommands( menuCommand ) );' in dispatch
    drawing = function_body(session, 'void idSessionLocal::Draw(')
    assert ('} else if ( RetainedMultiplayerCovers() ) {' in drawing and
            drawing.index('UI_RunTimeEvents( guiActive, presentationTime );') < drawing.index('guiRetainedMultiplayer->Redraw( presentationTime );'))
    assert 'guiRetainedEscape = guiRetainedWelcome = guiRetainedMultiplayer = NULL;' in function_body(session, 'void idSessionLocal::Clear(')
    # Each card loads inside the level load, and the game names the card
    # before the session loads or covers with it.
    prepare = function_body(menu, 'void idSessionLocal::PrepareRetainedLevel(')
    assert 'guiRetainedEscape = FindRetainedGui( RETAINED_MP_ESCAPE_GUI, false, false );' in prepare
    assert 'guiRetainedWelcome = FindRetainedGui( RETAINED_MP_WELCOME_GUI, false, false );' in prepare
    update = function_body(menu, 'void idSessionLocal::UpdateRetainedMultiplayer(')
    assert update.index('game->HandleMainMenuCommands( "retainedMultiplayerVariant", guiActive );') < \
        update.index('if ( !Session_RetainedMultiplayerEnabled( welcome ) || retainedStock.FindIndex( path ) >= 0 ) {') < update.index('document = FindRetainedGui( path, false, false );') < \
        update.index('game->HandleMainMenuCommands( "retainedMultiplayerCover", card );')
    release_ms = int(re.search(r'static const int RETAINED_RELEASE_MSEC = (\d+);', menu).group(1))
    timelines = {item['id']: item for item in document['timelines']}
    assert timelines['release']['durationMs'] == release_ms
    reset = document['events']['onActivate'][0]
    assert reset['op'] == 'if' and reset['condition'] == {'state': 'card.released'}
    assert document['events']['onBack'] == [{'op': 'action', 'action': 'mpClose'}]
    # The Team page's slots: the session bounds the slot, the game derives its
    # action again from the player's state, and the document offers as many.
    slots = int(re.search(r'static const int RETAINED_MP_TEAM_SLOTS = (\d+);', menu).group(1))
    header = (ROOT / 'src/mpgame/MultiplayerGame.h').read_text(encoding='utf-8', errors='replace')
    assert f'static const int RETAINED_TEAM_SLOTS = {slots};' in header
    assert slots == retained_mp_menus.TEAM_SLOTS and all(f'team_slot_{slot}' in document['events'] for slot in range(slots))
    command = function_body(mp_game, 'bool idMultiplayerGame::HandleRetainedMenuCommand(')
    assert command.index('RetainedTeamSlots( slots );') < command.index('if ( slot.action == RTA_NONE || !slot.available ) {') < \
        command.index('return RunRetainedAction( slot.action );')
    welcome_branch = command[command.index('if ( !sub.Icmp( "welcome" )'):]
    assert welcome_branch.index('RetainedWelcomeSlots( slots );') < welcome_branch.index('if ( slot.action == RTA_NONE || !slot.available ) {') < \
        welcome_branch.index('return RunRetainedAction( slot.action );')
    runner = function_body(mp_game, 'bool idMultiplayerGame::RunRetainedAction(')
    assert runner.index('default: return false;') < runner.index('DisableMenu();') < runner.index('return true;')
    # The Welcome card's Join page slots: the session bounds them, and the
    # session, the game and the document agree on four.
    welcome_slots = int(re.search(r'static const int RETAINED_MP_WELCOME_SLOTS = (\d+);', menu).group(1))
    assert f'static const int RETAINED_WELCOME_SLOTS = {welcome_slots};' in header
    assert welcome_slots == retained_mp_menus.WELCOME_SLOTS and all(f'join_slot_{slot}' in welcome_document['events'] for slot in range(welcome_slots))
    assert 'if ( slot < 0 || slot >= RETAINED_MP_WELCOME_SLOTS ) {' in function_body(menu, 'void idSessionLocal::HandleRetainedMultiplayerRequest(')
    # The Vote page is built, so it no longer hands off. The adapter's value
    # verbs are the session's field table, in the game's field order, which the
    # document's rows and the game's publisher follow; each row requests its
    # verb with its control's value.
    assert 'vote' not in handoffs
    adapter = (ROOT / 'src/ui/UserInterfaceRetained.cpp').read_text(encoding='utf-8', errors='replace')
    value_verbs = cpp_allowlist(adapter, 'bool SessionMenuValueCommand(')
    fields = re.findall(r'"(mpVote[A-Za-z]+)"', re.search(r'RETAINED_MP_VOTE_FIELDS\[\] = \{([^}]*)\};', menu).group(1))
    appearance = re.findall(r'"(mp[A-Za-z]+)"', re.search(r'RETAINED_MP_APPEARANCE_VALUES\[\] = \{([^}]*)\};', menu).group(1))
    choices = re.findall(r'"(mp[A-Za-z]+)"', re.search(r'RETAINED_MP_MATCH_CHOICES\[\] = \{([^}]*)\};', menu).group(1))
    assert set(fields) | set(appearance) | set(choices) == value_verbs and \
        len(fields) + len(appearance) + len(choices) == len(value_verbs), (fields, appearance, choices, value_verbs)
    assert appearance == [*retained_mp_menus.MODEL_VERBS, 'mpCrosshair'] and choices == ['mpMatchRole']
    enum = [name.strip() for name in re.search(r'enum retainedVoteField_t \{([^}]*)\};', header).group(1).split(',') if name.strip()]
    assert enum[-1] == 'RVF_COUNT'
    keys = [name[len('RVF_'):].lower() for name in enum[:-1]]
    assert keys == [verb[len('mpVote'):].lower() for verb in fields]
    assert [(key, verb) for key, verb, _label, _control in retained_mp_menus.VOTE_ROWS] == list(zip(keys, fields))
    publisher = function_body(mp_game, 'void idMultiplayerGame::PublishRetainedVote(')
    assert re.findall(r'"([a-z]+)"', re.search(r'static const char \*const fields\[ RVF_COUNT \] = \{([^}]*)\};', publisher).group(1)) == keys
    for key, verb, _label, control in retained_mp_menus.VOTE_ROWS:
        assert document['actions'][verb] == {'operation': 'session.menuValue', 'input': 'boolean' if control[0] == 'toggle' else 'number',
                                             'arguments': {'command': verb, 'value': {'input': 'value'}}}, verb
    assert f'static const int RETAINED_VOTE_LINES = {retained_mp_menus.VOTE_LINES};' in header
    request = function_body(menu, 'void idSessionLocal::HandleRetainedMultiplayerRequest(')
    assert request.index('} else if ( Session_RetainedValueRequest( request, RETAINED_MP_VOTE_FIELDS,') < \
        request.index('gameCommand = va( "retained voteSet %d %d", voteField, voteValue );') < \
        request.index('} else if ( Session_RetainedValueRequest( request, RETAINED_MP_APPEARANCE_VALUES,') < \
        request.index('gameCommand = voteField < 3 ? va( "retained appearance %d %d", voteField, voteValue ) : va( "retained crosshair %d", voteValue );')
    # The Settings pages: the game, the session and the document agree on the
    # model lists and the swatches; the adapter allows the document's
    # settings with the lists' own values; the appearance commands keep the
    # menu open.
    assert f'static const int RETAINED_MODEL_SLOTS = {retained_mp_menus.MODEL_SLOTS};' in header
    assert f'static const int RETAINED_MODEL_ROWS = {retained_mp_menus.MODEL_ROWS};' in header
    rails = len(retained_mp_menus.RAIL_SWATCHES)
    assert f'static const int RETAINED_RAIL_COLORS = {rails};' in header and f'static const int RETAINED_MP_RAIL_COLORS = {rails};' in menu
    assert len(re.findall(r'"\d+ [\d.]+ 1"', function_body(mp_game, 'const char *idMultiplayerGame::RetainedRailColor('))) == rails
    adapter_rules = player_setting_rules(adapter)
    for _label, enemy, team, _key, values in retained_mp_menus.APPEARANCE_ROWS:
        assert adapter_rules[enemy] == list(values) and adapter_rules[team] == list(values), enemy
        assert document['actions'][f'set.{enemy}']['operation'] == 'settings.player.set'
    assert adapter_rules['cl_player_outline_width'] == list(retained_mp_menus.OUTLINE_WIDTHS)
    for verb in ('appearance', 'rail', 'crosshair'):
        branch = command[command.index(f'if ( !sub.Icmp( "{verb}" )'):]
        branch = branch[:branch.index('return false;')]
        assert 'retainedMenuCovered' in branch and 'DisableMenu' not in branch, verb
    # The game: a ballot only while the player can cast one, a drafted field
    # checked against its rules without closing the menu, and a call only of
    # the fields that differ from the server's, closing the menu.
    vote_branch = command[command.index('if ( !sub.Icmp( "vote" )'):command.index('if ( !sub.Icmp( "voteSet" )')]
    assert vote_branch.index('vote == VOTE_NONE || RetainedBallotRefusal() != NULL') < \
        vote_branch.index('CastVote( gameLocal.localClientNum, yes );') < vote_branch.index('DisableMenu();')
    set_branch = command[command.index('if ( !sub.Icmp( "voteSet" )'):command.index('if ( !sub.Icmp( "callVote" )')]
    assert 'retainedMenuCovered' in set_branch and 'SetRetainedVoteField( atoi( fieldText.c_str() ), atoi( valueText.c_str() ) );' in set_branch
    assert 'DisableMenu' not in set_branch and 'return true' not in set_branch
    call_branch = command[command.index('if ( !sub.Icmp( "callVote" )'):command.index('if ( ( !sub.Icmp( "select" )')]
    assert call_branch.index('RetainedVoteRefusal() != NULL || RetainedVoteChanges( data ) == 0') < \
        call_branch.index('ClientCallPackedVote( data );') < call_branch.index('DisableMenu();')
    changes = function_body(mp_game, 'int idMultiplayerGame::RetainedVoteChanges(')
    assert 'retainedVoteDraft[ limit.field ] != si.GetInt( limit.key )' in changes and 'retainedVoteMap.Icmp( current ) != 0' in changes
    assert cover.index('retainedMenuCovered = true;') < cover.index('ResetRetainedVoteDraft();') < cover.index('PublishRetainedMenu( card );')
    # HandleGuiCommands' _XENON branches defeat a brace count; pin the statement.
    assert mp_game.replace('\r\n', '\n').count('if ( HandleRetainedMenuCommand( args, icmd ) ) {\n\t\t\t\treturn NULL;') == 1
    # The Players page: the session bounds the client to the server's slots,
    # and the game acts only on a client with a row now, never mutes or
    # befriends the player's own row, and keeps the menu open.
    assert 'static const int RETAINED_MP_CLIENTS = MAX_ASYNC_CLIENTS;' in menu
    assert 'if ( client < 0 || client >= RETAINED_MP_CLIENTS ) {' in function_body(menu, 'void idSessionLocal::HandleRetainedMultiplayerRequest(')
    listed = command.index('if ( client < 0 || client >= MAX_CLIENTS || !RetainedListed( client ) ) {')
    assert listed < command.index('retainedStatClient = client;')
    own = command.index('} else if ( local != NULL && client != local->entityNumber ) {')
    assert listed < own < command.index('ClientVoiceMute( client, !local->IsPlayerMuted( client ) );') < command.index('ToggleFriend( client );')
    players = command[listed:]
    assert 'DisableMenu' not in players and 'return true' not in players, 'the Players page commands keep the menu open'
    # The game and the document agree on the lists, the weapons and the awards.
    assert f'static const int RETAINED_PLAYER_LISTS = {len(retained_mp_menus.PLAYER_LISTS)};' in header
    assert f'static const int RETAINED_PLAYER_ROWS = {retained_mp_menus.PLAYER_ROWS};' in header
    weapons = re.search(r'RETAINED_ACCURACY_WEAPONS\[\] = \{([^}]*)\};', mp_game).group(1)
    assert re.findall(r'"([a-z_]+)"', weapons) == [weapon for weapon, _icon, _tint in retained_mp_menus.WEAPONS]
    awards = re.search(r'RETAINED_AWARDS\[\] = \{([^}]*)\};', mp_game).group(1)
    assert re.findall(r'IGA_[A-Z_]+', awards) == ['IGA_' + award.upper() for award in retained_mp_menus.AWARDS]
    for kind, _tints in retained_mp_menus.PLAYER_LISTS:
        assert all(f'players_{kind}{row}' in document['events'] for row in range(retained_mp_menus.PLAYER_ROWS)), kind
    publish = function_body(mp_game, 'void idMultiplayerGame::PublishRetainedMenu(')
    assert publish.index('PublishRetainedPlayers( card, changed );') < publish.index('if ( changed ) {')
    # The deathmatch header's rank text drops the HUD's colour codes.
    assert 'score = MPRetainedPlainText( GetPlayerRankText( player ), 96, 1 );' in publish
    # The stock Friend button keeps the same mark the page shows.
    assert mp_game.count('ToggleFriend( client );') == 2


def main() -> int:
    menu = (ROOT / 'src/framework/Session_menu.cpp').read_text(encoding='utf-8')
    session = (ROOT / 'src/framework/Session.cpp').read_text(encoding='utf-8')
    adapter = (ROOT / 'src/ui/UserInterfaceRetained.cpp').read_text(encoding='utf-8')

    # The gate itself: on by default and archived, so a player's choice of the
    # stock screens persists.
    assert 'idCVar ui_retained( "ui_retained", "1", CVAR_GUI | CVAR_BOOL | CVAR_ARCHIVE, ' in menu, 'ui_retained must default to 1 and be archived'
    assert 'ui_retainedSystem( "ui_retainedSystem", "0", CVAR_GUI | CVAR_BOOL' in menu
    assert ('return ui_retainedSystem.GetBool() || ( Session_RetainedScreensEnabled() &&\n'
            '\t\tRETAINED_SYSTEM_MISSING_SETTINGS[0] == NULL && RETAINED_SYSTEM_INCOMPLETE_SETTINGS[0] == NULL );') in menu
    # The SYSTEM page joins the gate once it has a control for every setting of
    # the stock page and each one works there; the two lists must say exactly that.
    missing = re.search(r'RETAINED_SYSTEM_MISSING_SETTINGS\[\] = \{([^}]*)\};', menu).group(1)
    listed = {name.lower() for name in re.findall(r'"([A-Za-z_0-9]+)"', missing)}
    assert missing.strip().endswith('NULL'), 'the missing-settings list must stay NULL-terminated'
    # CVar names are case-insensitive (the stock page binds r_multisamples).
    actual = {name.lower() for name in stock_system_settings()} - {name.lower() for name in retained_system_controls()}
    assert listed == actual, f'RETAINED_SYSTEM_MISSING_SETTINGS lists {sorted(listed)}; the retained SYSTEM page lacks {sorted(actual)}'
    check_retained_system_control_writes()
    incomplete = re.search(r'RETAINED_SYSTEM_INCOMPLETE_SETTINGS\[\] = \{([^}]*)\};', menu).group(1)
    assert incomplete.strip().endswith('NULL'), 'the incomplete-settings list must stay NULL-terminated'
    listed_incomplete = {name.lower() for name in re.findall(r'"([A-Za-z_0-9]+)"', incomplete)}
    reasons = retained_system_incomplete(adapter)
    assert listed_incomplete == set(reasons), (
        f'RETAINED_SYSTEM_INCOMPLETE_SETTINGS lists {sorted(listed_incomplete)}; the code gives these settings a reason: '
        + '; '.join(f'{key}: {reason}' for key, reason in sorted(reasons.items())))
    assert 'if ( !Session_RetainedSystemEnabled() || systemGuiTransition' in function_body(menu, 'bool idSessionLocal::OpenSystemSettings(')
    assert 'guiMainMenu->SetStateBool( "retainedSystem", RetainedSystemAvailable() );' in menu
    # Every retained document path in the session is behind the gate.
    for source, name in ((menu, 'Session_menu.cpp'), (session, 'Session.cpp')):
        for match in re.finditer(r'"([^"]+\.q4ui)"', source):
            path = match.group(1)
            allowed = {'guis/menu/settings/system.q4ui', 'guis/menu/title.q4ui', 'guis/menu/pause.q4ui', 'guis/menu/pause_strogg.q4ui',
                       'guis/loading/loading.q4ui', 'guis/menu/singleplayer.q4ui', 'guis/menu/campaigns.q4ui',
                       'guis/menu/mp_escape.q4ui', 'guis/menu/mp_welcome.q4ui'}
            assert path in allowed, f'{name} names an ungated retained document {path}'
    # Every retained document loads through FindRetainedGui, which falls back to
    # the stock screen; the SYSTEM page and the campaign selectors fall back too.
    assert not re.search(r'uiManager->FindGui\(\s*(?:RETAINED_|"[^"]+\.q4ui")', menu + session), 'retained documents load only through FindRetainedGui'
    find_retained = function_body(menu, 'idUserInterface *idSessionLocal::FindRetainedGui(')
    assert 'uiManager->FindGui( path, true, !shared, shared )' in find_retained and 'retainedStock.Append( path );' in find_retained
    system_open = function_body(menu, 'bool idSessionLocal::OpenSystemSettings(')
    assert 'FindRetainedGui( RETAINED_SYSTEM_GUI, false, false )' in system_open and 'retainedStock.Append( RETAINED_SYSTEM_GUI );' in system_open
    main_menu = function_body(menu, 'void idSessionLocal::HandleMainMenuCommands(')
    for command, multiplayer in (('openRetainedSystem', 'false'), ('openRetainedSystemFromMp', 'true')):
        assert f'if ( !idStr::Icmp( cmd, "{command}" ) ) {{\n\t\t\tOpenSystemSettingsRoute( {multiplayer} );\n\t\t\treturn;' in main_menu
    system_route = function_body(menu, 'void idSessionLocal::OpenSystemSettingsRoute(')
    assert 'UI_RunLegacyWindowAction( guiMainMenu, "set_b_system", false, command )' in system_route, 'a failed SYSTEM page must open the stock one'
    assert 'guiMainMenu->HandleNamedEvent( "fromMp_toSystemStock" );' in system_route, 'a failed multiplayer SYSTEM route must open the stock page'
    home_document = function_body(menu, 'idUserInterface *idSessionLocal::RetainedHomeDocument(')
    assert 'UI_RetainedViewFailed( home )' in home_document and 'retainedStock.AddUnique( path );' in home_document
    assert 'retainedStock.Clear();' in function_body(session, 'void idSessionLocal::Clear(')
    campaign_selector = function_body(menu, 'void idSessionLocal::OpenCampaignSelector(')
    assert 'Session_RetainedScreensEnabled() ?' in campaign_selector and 'arenaCampaign.OpenSelector();' in campaign_selector
    assert 'FindGui( "guis/campaign_menu.gui"' in campaign_selector
    assert menu.count('RETAINED_TITLE_GUI') == 3 and menu.count('RETAINED_PAUSE_GUI') == 4 and menu.count('RETAINED_LOADING_GUI') == 2
    assert menu.count('RETAINED_PAUSE_STROGG_GUI') == 3
    check_retained_multiplayer(menu, session)
    check_retained_match(menu)
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
    value_allowlist = cpp_allowlist(adapter, 'bool SessionMenuValueCommand(')
    player_settings = player_setting_rules(adapter)
    handled = set(re.findall(r'\{ "([A-Za-z][A-Za-z0-9]*)",\s+"main_b_', menu)) | set(re.findall(r'!idStr::Icmp\( request, "([A-Za-z][A-Za-z0-9]*)" \)', menu))
    assert allowlist == handled, f'allowlist {sorted(allowlist)} differs from session handlers {sorted(handled)}'
    for relative in ('content/baseoq4/pak0/guis/menu/title.q4ui', 'content/baseoq4/pak0/guis/menu/pause.q4ui',
                     'content/baseoq4/pak0/guis/menu/pause_strogg.q4ui', 'content/baseoq4/pak0/guis/loading/loading.q4ui',
                     'content/baseoq4/pak0/guis/menu/singleplayer.q4ui', 'content/baseoq4/pak0/guis/menu/campaigns.q4ui',
                     'content/baseoq4/pak0/guis/menu/mp_escape.q4ui'):
        text = (ROOT / relative).read_text(encoding='utf-8')
        document = json.loads(re.sub(r'^\s*//.*$', '', text, flags=re.M))
        assert document.get('canvas') == {'height': 720}, relative
        if 'pause' in relative or 'mp_escape' in relative:
            assert [child['id'] for child in document['root']['children']] == ['scene-softfocus', 'scrim', 'chrome'], relative
        if 'pause' in relative:
            layers = [child['id'] for child in document['root']['children'][2]['children']]
            assert layers.index('objectives-bar') < layers.index('band-top') < layers.index('objectives'), relative
        for action in document.get('actions', {}).values():
            if action['operation'] == 'settings.player.set':
                assert action['arguments']['cvar'] in player_settings and action['arguments']['value'] == {'input': 'value'}, relative
            elif action['operation'] == 'session.menuValue':
                assert action['arguments']['command'] in value_allowlist and action['arguments']['value'] == {'input': 'value'}, relative
            else:
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
        'static bool Session_IsGameMenu(', 'bool idSessionLocal::RetainedMultiplayerCovers(', 'void idSessionLocal::UpdateRetainedMultiplayer(',
        'void idSessionLocal::RetireRetainedMultiplayer(', 'void idSessionLocal::RetainedMultiplayerFrameEvent(',
        'void idSessionLocal::HandleGameMenuReturn(', 'void idSessionLocal::HandleRetainedMultiplayerRequest(',
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
            check_loading_hold(compiler, Path(directory))
        return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
