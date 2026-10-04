// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
// Retained screens: image nodes, path blends and view-height canvases in the
// canonical schema and runtime, then the production title, pause and loading
// documents (content/baseoq4/pak0/guis) loaded, laid out and driven by state.
#include "src/ui/retained/Runtime.h"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <map>
#include <set>
#include <string>
#include <vector>

using namespace openq4::ui;
static int checks = 0;
static void Check(bool condition, const char* message) {
	++checks;
	if (!condition) { std::fprintf(stderr,"FAIL: %s\n",message); std::exit(1); }
}
static bool Near(float a, float b, float tolerance = .75f) { return std::abs(a-b) <= tolerance; }

struct ScreenHost final : Host {
	struct Submission { std::vector<Vertex> vertices; std::uintptr_t material = 0; };
	std::vector<Submission> draws;
	std::vector<std::string> materials;
	std::uintptr_t multiply = 7;
	bool reducedMotion = false;
	int errors = 0;
	std::uint32_t activeLayer = 0;
	std::uint64_t frame = 1;
	bool ReadFile(const std::string&, std::string&) override { return false; }
	std::string Translate(const std::string& text) override { return text.starts_with("#str_") ? "Label" : text; }
	// The engine reports soft focus through ui_retainedSoftFocus and draws it
	// through SoftenBackdrop; without it the runtime leaves the backdrop.
	bool softFocus = false;
	struct Softened { float sigma = 0, saturation = 1; Bounds region; };
	std::vector<Softened> softened;
	std::string language = "english";
	// The player settings the multiplayer card's Settings and Voice pages read back.
	std::map<std::string,StateValue> cvars = {{"ui_handicap",100.0},{"s_voiceVolume",1.0},{"s_micInputLevel",5.0},
		{"s_voiceChatSend",true},{"s_voiceChatReceive",true},{"s_voiceChatEcho",false},{"cl_player_outline_width",std::string("2.0")},
		{"cl_player_outline_enemy",std::string("0")},{"cl_player_outline_team",std::string("0")},{"cl_player_rimlight_enemy",std::string("0")},
		{"cl_player_rimlight_team",std::string("0")},{"cl_player_brightskin_enemy",std::string("0")},{"cl_player_brightskin_team",std::string("0")},
		{"cl_player_visibility_enemy_color",std::string("1 0.12 0.05")},{"cl_player_visibility_team_color",std::string("1 0.12 0.05")},
		{"cl_player_brightskin_enemy_color",std::string("1 0.05 0.02")},{"cl_player_brightskin_team_color",std::string("1 0.05 0.02")}};
	bool ReadCVar(const std::string& name, size_t type, StateValue& value) override {
		if (type == 2 && name == "sys_lang") { value = language; return true; }
		if (const auto found = cvars.find(name); found != cvars.end()) {
			if (found->second.index() != type) return false;
			value = found->second; return true;
		}
		if (type != 1) return false;
		if (name == "ui_retainedReducedMotion") { value = reducedMotion; return true; }
		if (name == "ui_retainedSoftFocus") { value = softFocus; return true; }
		return false;
	}
	bool SoftenBackdrop(std::uint32_t destination, float sigma, float saturation, const Bounds& region) override {
		Check(destination != 0,"the soft focus is drawn into a pushed layer");
		softened.push_back({sigma,saturation,region}); return softFocus;
	}
	void Log(bool error, const std::string& message) override {
		if (error) { ++errors; std::fprintf(stderr,"retained: %s\n",message.c_str()); }
	}
	std::uintptr_t LoadMaterial(const std::string& name, int& width, int& height) override {
		materials.push_back(name);
		// Fonts and pictures: a 4:3 picture, so cover and contain differ at 16:9.
		width = 640; height = 480;
		return 100+materials.size();
	}
	std::uintptr_t MultiplyMaterial() override { return multiply; }
	void Draw(const std::vector<Vertex>& vertices, const std::vector<int>& indices, std::uintptr_t material) override {
		Check(indices.size()%3 == 0,"triangle topology");
		for (int index : indices) Check(index >= 0 && static_cast<size_t>(index) < vertices.size(),"valid indices");
		draws.push_back({vertices,material});
	}
	std::uint64_t RenderFrame() const override { return frame; }
	std::vector<float> compositeOpacities;
	bool BeginLayer(std::uint32_t id, int, int) override { activeLayer = id; return true; }
	void CompositeLayer(std::uint32_t, std::uint32_t destination, float opacity, const Bounds&) override {
		compositeOpacities.push_back(opacity); activeLayer = destination;
	}
	void MaskLayer(std::uint32_t, std::uint32_t destination, const Bounds&) override { activeLayer = destination; }
	void EndLayer(std::uint32_t restore) override { activeLayer = restore; }
	FontMetrics GetFontMetrics(const std::string&, int size) override { return {size*.8f,size*.2f,size*1.2f,size*.5f}; }
	std::set<std::uint32_t> glyphs;   // every code point the runtime asked to draw or measure
	Glyph GetGlyph(const std::string&, int size, std::uint32_t codepoint) override {
		glyphs.insert(codepoint);
		return {size*.6f,0,-size*.8f,size*.6f,static_cast<float>(size),0,0,1,1,"test-font"};
	}
};

static std::string Read(const char* path) {
	std::ifstream file(path, std::ios::binary);
	Check(file.good(),"read a production retained document");
	return std::string(std::istreambuf_iterator<char>(file),std::istreambuf_iterator<char>());
}

static bool Loads(const std::string& source) {
	Document document; std::vector<Diagnostic> diagnostics;
	return document.Load(source,diagnostics);
}

static std::string Wrap(const std::string& root, const std::string& extra = "") {
	return R"({"format":"openq4-ui","version":1,"id":"screens-schema")"+extra+R"(,"root":)"+root+"}";
}

static void CheckSchema() {
	const std::string picture = R"({"id":"root","type":"group","children":[{"id":"shot","type":"image","properties":{"image":{"type":"image","value":"gfx/guis/loadscreens/generic"},"image-fit":{"type":"keyword","value":"cover"},"image-blend":{"type":"keyword","value":"additive"},"image-color":{"type":"color","value":[1,1,1,0.5]},"width":{"type":"length","value":100,"unit":"%"}}}]})";
	Document document; std::vector<Diagnostic> diagnostics;
	Check(document.Load(Wrap(picture,R"(,"canvas":{"height":720})"),diagnostics),"image node, fit, blend and tint compile");
	Check(document.Model().canvasHeight == 720,"view-height canvas recorded");
	const auto markup = document.BuildMarkup();
	Check(markup.find("decorator:image(material:q4-add/gfx/guis/loadscreens/generic none cover center center)") != std::string::npos,
		"additive image decorator resolves from the VFS root with its fit and alignment");
	Check(markup.find("image-fit") == std::string::npos && markup.find("image-blend") == std::string::npos,"fit and blend fold into the decorator");
	Check(markup.find("image-color:rgba(255,255,255,128)") != std::string::npos,"image tint reaches the layout");
	for (const char* source : {"../gfx/x","/gfx/x","gfx//x","gfx/x/","gfx/x y","C:gfx","gfx\\\\x",".hidden"}) {
		std::string bad = picture; const auto at = bad.find("gfx/guis/loadscreens/generic");
		bad.replace(at,28,source);
		Check(!Loads(Wrap(bad)),"image sources stay relative VFS names");
	}
	Check(ValidImageSource("") && ValidImageSource("guis/assets/generated/loadscreens/airdefense1_1920x1080.tga"),"empty and generated levelshot sources are valid");
	Check(!Loads(Wrap(R"({"id":"root","type":"group","properties":{"image":{"type":"image","value":"gfx/x"}}})")),"image properties require an image node");
	Check(!Loads(Wrap(R"({"id":"root","type":"image","properties":{"width":{"type":"length","value":10,"unit":"dp"}}})")),"an image node requires its source property");
	Check(!Loads(Wrap(R"({"id":"root","type":"image","properties":{"image":{"type":"image","value":"x"},"image-fit":{"type":"keyword","value":"stretch"}}})")),"unknown fit rejected");
	Check(!Loads(Wrap(picture,R"(,"canvas":{"height":100})")) && !Loads(Wrap(picture,R"(,"canvas":{"height":720,"width":1280})")),"canvas height bounded, no other fields");
	const auto vector = [](const std::string& blend, bool mask) {
		const std::string shape = R"({"id":"p","commands":[{"id":"a","op":"move","points":[[0,0]]},{"id":"b","op":"line","points":[[10,0]]},{"id":"c","op":"line","points":[[10,10]]}],"fill":{"type":"solid","color":{"type":"color","value":[1,1,1,1]}},"blend":")"+blend+R"("})";
		return Wrap(mask ? R"({"id":"root","type":"group","mask":{"paths":[)"+shape+R"(]}})" : R"({"id":"root","type":"vector","paths":[)"+shape+R"(]})");
	};
	Check(Loads(vector("additive",false)) && Loads(vector("multiply",false)) && Loads(vector("normal",false)),"path blends compile");
	Check(!Loads(vector("screen",false)),"unknown blend rejected");
	Check(!Loads(vector("additive",true)) && Loads(vector("normal",true)),"mask coverage cannot blend");
	const std::string bound = R"({"id":"root","type":"group","children":[{"id":"shot","type":"image","properties":{"image":{"type":"image","value":""}}}]})";
	const std::string state = R"(,"state":{"shot":{"type":"string","initial":""}})";
	Check(Loads(Wrap(bound,state+R"(,"bindings":[{"id":"b","node":"shot","property":"image","value":{"state":"shot"}}])")),"image source binds application strings");
	Check(!Loads(Wrap(bound,state+R"(,"bindings":[{"id":"b","node":"shot","property":"image","value":"../escape"}])")),"literal image bindings are checked");
	Check(!Loads(Wrap(bound,R"(,"timelines":[{"id":"t","durationMs":10,"tracks":[{"node":"shot","property":"image","keys":[{"atMs":0,"value":{"type":"image","value":"a"}},{"atMs":10,"value":{"type":"image","value":"b"}}]}]}])")),
		"image sources are discrete, never animated");
	Viewport viewport; viewport.width = 1920; viewport.height = 1080; viewport.displayScale = 2; viewport.userScale = 1.5f;
	viewport.canvasHeight = 720;
	Check(Near(viewport.DpRatio(),1.5f,.001f),"a view-height canvas replaces density and user scale");
	viewport.canvasHeight = 0;
	Check(Near(viewport.DpRatio(),3,.001f),"display density applies without a canvas");
}

static const std::set<std::string> SessionCommands = {"continue","singlePlayer","loadGame","saveGame","multiplayer","settings",
	"mods","demos","updates","credits","quit","resume","restartLevel","quitToMenu",
	"mpClose","mpMainMenu","mpDisconnect","mpStockPage","mpTeamAction","mpSelectPlayer","mpMute","mpFriend","mpWelcomeAction",
	"mpVoteYes","mpVoteNo","mpCallVote","mpRail","mpSettingsControls","mpSettingsGame","mpSettingsSystem"};
// The value controls' verbs, which carry the control's new value.
static const std::set<std::string> SessionValueCommands = {"mpVoteMap","mpVoteGameType","mpVoteTimeLimit","mpVoteFragLimit",
	"mpVoteCaptureLimit","mpVoteTourneyLimit","mpVoteControlTime","mpVoteBalance","mpVoteShuffle","mpVoteRestart","mpVoteBuying","mpVoteKick",
	"mpModelSelf","mpModelEnemy","mpModelTeam","mpCrosshair"};
// The player settings the multiplayer card's Settings and Voice pages change.
static const std::set<std::string> PlayerSettings = {"ui_handicap","cl_player_outline_enemy","cl_player_outline_team",
	"cl_player_rimlight_enemy","cl_player_rimlight_team","cl_player_visibility_enemy_color","cl_player_visibility_team_color",
	"cl_player_brightskin_enemy","cl_player_brightskin_team","cl_player_brightskin_enemy_color","cl_player_brightskin_team_color",
	"cl_player_outline_width","s_voiceChatSend","s_voiceChatReceive","s_voiceChatEcho","s_voiceVolume","s_micInputLevel"};

static void CheckSessionActions(const Document& document) {
	for (const auto& [id,action] : document.Model().actions) {
		if (action.operation == "settings.player.set") {
			const auto cvar = action.arguments.find("cvar");
			Check(cvar != action.arguments.end() && action.arguments.size() == 2 && PlayerSettings.contains(std::get<std::string>(cvar->second.literal)) &&
				action.arguments.at("value").inputValue && action.inputType,"a setting control sets an allowlisted player setting");
			continue;
		}
		const bool value = action.operation == "session.menuValue";
		Check(action.operation == "session.menu" || value,"production screens request only session operations");
		const auto command = action.arguments.find("command");
		Check(command != action.arguments.end() && action.arguments.size() == (value ? 2u : 1u),"one command argument, and a value");
		Check((value ? SessionValueCommands : SessionCommands).contains(std::get<std::string>(command->second.literal)),
			"every command is in the session allowlist");
		Check(!value || (action.arguments.at("value").inputValue && action.inputType),"a value verb carries its control's value");
	}
}

// Overflow under a transform: RmlUi clips with the clipping box's geometry
// instead of a scissor. The renderer applies it as an exact rectangle for
// translation and scale, and clips a rotated box to its bounds (counted).
static void CheckTransformedClip(ScreenHost& host) {
	const auto document = [](const char* transform) {
		return Wrap(std::string(R"({"id":"root","type":"group","properties":{"transform":{"type":"transform","unit":"dp","value":)")+transform+R"(}},"children":[)"
			R"({"id":"clip","type":"group","properties":{"position":{"type":"keyword","value":"absolute"},"left":{"type":"length","value":10,"unit":"dp"},"top":{"type":"length","value":0,"unit":"dp"},"width":{"type":"length","value":50,"unit":"dp"},"height":{"type":"length","value":10,"unit":"dp"},"overflow":{"type":"keyword","value":"hidden"}},"children":[)"
			R"({"id":"wide","type":"vector","properties":{"position":{"type":"keyword","value":"absolute"},"left":{"type":"length","value":0,"unit":"dp"},"top":{"type":"length","value":0,"unit":"dp"},"width":{"type":"length","value":200,"unit":"dp"},"height":{"type":"length","value":10,"unit":"dp"}},"paths":[)"
			R"({"id":"bar","commands":[{"id":"a","op":"move","points":[[0,0]]},{"id":"b","op":"line","points":[[{"fraction":1},0]]},{"id":"c","op":"line","points":[[{"fraction":1},{"fraction":1}]]},{"id":"d","op":"line","points":[[0,{"fraction":1}]]},{"id":"e","op":"close"}],"fill":{"type":"solid","color":{"type":"color","value":[1,1,1,1]}}}]}]}]})");
	};
	for (const bool rotated : {false,true}) {
		Runtime runtime(host);
		std::vector<Diagnostic> diagnostics;
		Check(runtime.Initialize() && runtime.LoadDocument(document(rotated ? "[10,20,1,1,10]" : "[10,20,1,1,0]"),"clip.q4ui",diagnostics),
			"transformed clip document loads");
		host.draws.clear();
		runtime.Frame(Viewport(),1);
		Bounds clip;
		Check(runtime.GetBounds("clip",clip),"clip box laid out");
		float minX = 1e9f, maxX = -1e9f;
		size_t vertices = 0;
		for (const auto& draw : host.draws) for (const auto& vertex : draw.vertices) {
			minX = std::min(minX,vertex.x); maxX = std::max(maxX,vertex.x); ++vertices;
		}
		const auto statistics = runtime.Statistics();
		if (!rotated) {
			Check(vertices > 0 && Near(minX,clip.x+10,.01f) && Near(maxX-minX,clip.width,.01f),"a translated overflow clip cuts its content exactly");
			Check(statistics.clipMasks > 0 && statistics.clipMaskFallbacks == 0,"a translated clip mask is an exact rectangle");
		} else {
			Check(vertices > 0 && maxX-minX < clip.width+2,"a rotated overflow clip still bounds its content");
			Check(statistics.clipMaskFallbacks > 0,"a rotated clip mask is counted as approximate");
		}
	}
}

static bool Additive(const ScreenHost& host) {
	for (const auto& draw : host.draws) if (!draw.material)
		for (const auto& vertex : draw.vertices) if (vertex.a == 0 && vertex.g > .01f) return true;
	return false;
}

// The multiplayer Escape card (section 14.18): centered at every view, motion
// and release, the tab programs, the leaving page, hand-offs and the header.
static void CheckEscape(ScreenHost& host, const char* path) {
	const auto source = Read(path);
	Document document; std::vector<Diagnostic> diagnostics;
	const bool valid = document.Load(source,diagnostics);
	for (const auto& diagnostic : diagnostics) std::fprintf(stderr,"mp_escape %s: %s\n",diagnostic.pointer.c_str(),diagnostic.message.c_str());
	Check(valid && document.Model().id == "openq4.mp_escape" && document.Model().canvasHeight == 720,"the Escape card validates");
	CheckSessionActions(document);
	// The softened view stands outside the card's composition: a node inside
	// a composited group gets no soft focus.
	const auto& root = document.Model().root;
	Check(root.children.size() == 3 && root.children[0].id == "scene-softfocus" && root.children[1].id == "scrim" &&
		root.children[2].id == "chrome","the softened view, its scrim stand-in, then the card and its modal");
	Runtime runtime(host);
	Check(runtime.Initialize() && runtime.LoadDocument(source,"guis/menu/mp_escape.q4ui",diagnostics),"the card loads into a runtime");
	Viewport viewport; viewport.canvasHeight = 720;
	std::string error;
	Runtime::EventEffects effects;
	const char* const tabs[] = {"team","players","vote","match","settings","voice","server","admin"};
	const auto bounds = [&](const std::string& id) { Bounds b; Check(runtime.GetBounds(id,b),"a card node is laid out"); return b; };
	const auto number = [&](const char* node, const char* property) {
		const auto value = runtime.PresentedValue(node,property); Check(value.has_value(),"a presented value"); return static_cast<float>(value->data[0]);
	};
	const auto text = [&](const char* node, const char* property) {
		const auto value = runtime.PresentedValue(node,property); Check(value.has_value(),"a presented keyword"); return value->text;
	};
	// Centered on the projection center at 16:9, 1080 p and 4:3, never closer
	// than 16 dp to the sides, the same size on every tab.
	float cardWidth = 0;
	for (const auto& [width,height] : std::vector<std::pair<int,int>>{{1280,720},{1920,1080},{1024,768}}) {
		viewport.width = width; viewport.height = height;
		runtime.Frame(viewport,1);
		const auto card = bounds("card");
		const float scale = height/720.f;
		if (!cardWidth) cardWidth = card.width/scale;
		Check(Near(card.x+card.width/2,width/2.f) && Near(card.y+card.height/2,height/2.f),"the card is centered");
		Check(Near(card.width,cardWidth*scale,1) && Near(card.height,477*scale,1),"the card keeps its size at every view");
		Check(card.x >= 16*scale-.5f,"the card clears the view's sides by 16 dp");
	}
	Check(cardWidth >= 648-.5f && cardWidth <= 928+.5f,"the card is at least the specified 648 dp and fits a 4:3 view");
	viewport.width = 1280; viewport.height = 720;
	// The game publishes the Team page before the card opens: on a team, a
	// switch it allows with the sizes it would leave, a spectate it refuses
	// with its reason, and no third action.
	Check(runtime.SetState({{"mp.team.band",std::string("MARINES")},{"mp.team.band_color",0.0},{"mp.team.band_score",std::string("12")},
		{"mp.team.band_detail",std::string("4 - 3")},
		{"mp.action0.shown",true},{"mp.action0.available",true},{"mp.action0.label",std::string("SWITCH TEAM")},
		{"mp.action0.detail",std::string("MARINES 3 - 4 STROGG")},
		{"mp.action1.shown",true},{"mp.action1.available",false},{"mp.action1.label",std::string("SPECTATE")},
		{"mp.action1.reason",std::string("Spectating is disabled on this server.")},
		{"mp.action2.shown",false},{"mp.chat0",std::string("Anderson: gg")}},error,1.5),"publish the Team page");
	// Opening: the softening ramps over 250 ms while the card rises 12 dp and
	// fades in over 150 ms; the current page's primary action takes focus.
	host.softFocus = true;
	Check(runtime.RunEvent("open",2,effects,error),"the card opens");
	// 30 ms in: the ease-out has covered most of the way but not all of it.
	runtime.Frame(viewport,2.03);
	Check(number("card","opacity") > .05f && number("card","opacity") < .99f,"part way through its fade");
	const auto rising = runtime.PresentedValue("card","transform");
	Check(rising && rising->data[1] > .05f && rising->data[1] < 12,"and rising from 12 dp");
	runtime.Frame(viewport,2.2);
	Check(Near(number("card","opacity"),1,.001f) && Near(static_cast<float>(runtime.PresentedValue("card","transform")->data[1]),0,.01f),
		"risen and shown at 150 ms");
	Check(number("scene-softfocus","backdrop-blur") < 7.4f,"the softening is still ramping");
	runtime.Frame(viewport,2.3);
	Check(Near(number("scene-softfocus","backdrop-blur"),7.5f,.01f) && Near(number("scene-softfocus","backdrop-saturate"),.8f,.001f),
		"softened at 250 ms with modal.softfocus's values");
	Check(text("scene-softfocus","display") == "block" && text("scrim","display") == "none","soft focus replaces the scrim");
	Check(runtime.FocusedControl() == "team-slot-0","the Team page's first action has focus");
	// The Team page: the band in the team's color, an available action with
	// its detail, an unavailable one dimmed with its lock and reason, and a
	// slot the game leaves empty hidden.
	Check(text("team-band-0","display") == "block" && text("team-band-1","display") == "none","the band takes the team's color");
	Check(text("team-slot-0-detail","display") == "block" && text("team-slot-0-reason","display") == "none" &&
		text("team-slot-0-lock","display") == "none" && Near(number("team-slot-0","opacity"),1,.001f),"an available action shows its detail");
	Check(text("team-slot-1-reason","display") == "block" && text("team-slot-1-lock","display") == "block" &&
		Near(number("team-slot-1","opacity"),.6f,.001f),"an unavailable one dims with its lock and reason");
	Check(text("team-slot-2-slot","display") == "none","an empty slot is hidden");
	const auto slot0 = bounds("team-slot-0-slot"), slot1 = bounds("team-slot-1-slot");
	Check(slot1.y >= slot0.y+slot0.height,"the actions stack without overlap");
	Check(runtime.RunEvent("team_slot_0",2.31,effects,error) && effects.actions.size() == 1 &&
		std::get<std::string>(effects.actions[0].arguments.at("command")) == "mpTeamAction" &&
		std::get<double>(runtime.GetState().at("card.team_action")) == 0,"an available action asks the game");
	Check(runtime.RunEvent("team_slot_1",2.32,effects,error) && effects.actions.empty(),"an unavailable one does not");
	runtime.Frame(viewport,2.37);
	const auto shaking = runtime.PresentedValue("team-slot-1-slot","transform");
	Check(shaking && std::abs(shaking->data[0]) > .5f,"it shakes instead");
	runtime.Frame(viewport,2.7);
	const auto settled = runtime.PresentedValue("team-slot-1-slot","transform");
	Check(settled && Near(static_cast<float>(settled->data[0]),0,.01f),"and settles after 300 ms");
	// Each tab: the strip lays its tabs in order without overlap inside the
	// card, and only the current tab rises.
	const auto card = bounds("card");
	float previousRight = card.x;
	for (const char* tab : tabs) {
		const auto box = bounds(std::string("tab-")+tab);
		Check(box.x >= previousRight-.5f && box.x+box.width <= card.x+card.width,"tabs keep their order inside the card");
		previousRight = box.x+box.width;
		const auto label = bounds(std::string("tab-")+tab+"-label");
		Check(label.x >= box.x && label.x+label.width <= box.x+box.width+.5f,"a label stays inside its tab");
	}
	Check(text("tab-team-active","display") == "block" && text("tab-players-active","display") == "none","only the current tab rises");
	// The game publishes the Players page: three Marines with the player's own
	// row second, two Strogg and a spectator; the player's statistics show.
	StateValues lists = {{"mp.players.a.shown",true},{"mp.players.a.title",std::string("MARINES")},{"mp.players.a.color",0.0},
		{"mp.players.a.score",std::string("12")},{"mp.players.a.count",3.0},{"mp.players.b.shown",true},
		{"mp.players.b.title",std::string("STROGG")},{"mp.players.b.color",1.0},{"mp.players.b.count",2.0},
		{"mp.players.s.shown",true},{"mp.players.s.title",std::string("SPECTATORS")},{"mp.players.s.color",2.0},{"mp.players.s.count",1.0},
		{"mp.stat.client",1.0},{"mp.stat.name",std::string("Kane")},{"mp.stat.color",0.0},{"mp.stat.kills",std::string("7")},
		{"mp.stat.acc0",std::string("57%")},{"mp.stat.acc1",std::string("-")},{"mp.stat.award0",std::string("2")},
		{"mp.stat.award1",std::string("0")},
		{"mp.mute.shown",true},{"mp.mute.available",false},{"mp.mute.label",std::string("MUTE PLAYER")},
		{"mp.mute.reason",std::string("You can't mute yourself.")},{"mp.friend.shown",true},{"mp.friend.available",false},
		{"mp.friend.label",std::string("ADD FRIEND")},{"mp.friend.reason",std::string("You can't add yourself as a friend.")}};
	const char* const names[] = {"Anderson","Kane","Rhodes","Makron","Gladiator","Voss"};
	for (int client = 0; client < 6; ++client) {
		const std::string row = client < 3 ? "mp.players.a"+std::to_string(client) : client < 5 ? "mp.players.b"+std::to_string(client-3) :
			"mp.players.s0";
		lists[row+".client"] = static_cast<double>(client); lists[row+".name"] = std::string(names[client]);
		lists[row+".score"] = std::to_string(10-client); lists[row+".ping"] = std::to_string(20+client);
		lists[row+".local"] = client == 1; lists[row+".friend"] = client == 0; lists[row+".muted"] = client == 2;
	}
	Check(runtime.SetState(lists,error,2.9),"publish the Players page");
	// Q, E and the strip's keycaps: the next tab at once, its page cross-fading
	// over 150 ms, the leaving page shown but out of reach meanwhile.
	Check(runtime.RunEvent("onTabNext",3,effects,error),"E moves to the next tab");
	Check(std::get<double>(runtime.GetState().at("card.tab")) == 1 && std::get<double>(runtime.GetState().at("card.leaving")) == 0,
		"the players tab is current and the team page is leaving");
	runtime.Frame(viewport,3.075);
	Check(text("page-team","display") == "block" && text("page-players","display") == "block","both pages show while they cross-fade");
	Check(number("page-players","opacity") > .1f && number("page-players","opacity") < .9f && number("page-team","opacity") < .9f,
		"one fades in as the other fades out");
	Check(!runtime.CanActivateControl("team-slot-0",3.075) && runtime.CanActivateControl("players-a-1",3.075),
		"the leaving page takes no input");
	Check(runtime.FocusedControl() == "players-a-1","the arriving page focuses the player whose statistics show");
	runtime.Frame(viewport,3.2);
	Check(text("page-team","display") == "none" && Near(number("page-players","opacity"),1,.001f) &&
		std::get<double>(runtime.GetState().at("card.leaving")) == -1,"the cross-fade ends with one page");
	Check(text("tab-players-active","display") == "block" && text("tab-team-active","display") == "none","the new tab rises");
	// The Players page: each list's rows in its band's color, the player's own
	// row brighter with the marker, the selected player lit, the symbols.
	Check(text("players-a-2","display") == "block" && text("players-a-3","display") == "none" && text("players-b-1","display") == "block" &&
		text("players-b-2","display") == "none" && text("players-s-0","display") == "block" && text("players-s-1","display") == "none",
		"each list shows its players' rows");
	Check(text("players-a-band-0","display") == "block" && text("players-a-band-1","display") == "none" &&
		text("players-b-band-1","display") == "block" && text("players-s-band","display") == "block","the bands take their teams' colors");
	Check(text("players-a-1-marker","display") == "block" && text("players-a-0-marker","display") == "none" &&
		Near(number("players-a-1-band","opacity"),.29f,.001f) && Near(number("players-a-0-band","opacity"),.08f,.001f),
		"the player's own row is brighter and marked");
	Check(text("players-a-1-chosen","display") == "block" && text("players-a-0-chosen","display") == "none","the selected player is lit");
	Check(text("players-a-2-speaker-slash","display") == "block" && text("players-a-0-speaker-slash","display") == "none" &&
		Near(number("players-a-0-friend","opacity"),1,.001f) && Near(number("players-a-2-friend","opacity"),.125f,.001f),
		"muted players' speakers are crossed and friends lit");
	const auto lists0 = bounds("players-lists"), stats0 = bounds("players-stats");
	Check(lists0.x+lists0.width <= stats0.x,"the statistics stand beside the lists");
	Check(Near(bounds("players-a-0").height,24,.01f) && bounds("players-a-1").y >= bounds("players-a-0").y+23.9f,"few players take the widest pitch");
	// The statistics: a weapon that has not fired dims, flag awards only in flag modes.
	Check(Near(number("stat-acc-0-icon","opacity"),1,.001f) && Near(number("stat-acc-1-icon","opacity"),.35f,.001f),
		"a weapon that has not fired dims");
	Check(Near(number("stat-award-0-icon","opacity"),1,.001f) && Near(number("stat-award-1-icon","opacity"),.35f,.001f),
		"an award not earned dims");
	Check(text("stat-award-4-cell","display") == "block" && text("stat-award-5-cell","display") == "none","flag awards only in flag modes");
	Check(text("stat-band-0","display") == "block" && text("stat-band-2","display") == "none","the statistics take the player's team color");
	// The player's own row offers neither Mute nor Friend, and says why.
	Check(text("players-mute-reason","display") == "block" && text("players-mute-lock","display") == "block","Mute says why it is unavailable");
	Check(runtime.RunEvent("players_mute",3.3,effects,error) && effects.actions.empty(),"an unavailable Mute asks nothing");
	// Choosing a row asks the game for that player; the game answers with
	// their statistics and makes Mute and Friend available.
	Check(runtime.RunEvent("players_b1",3.4,effects,error) && effects.actions.size() == 1 &&
		std::get<std::string>(effects.actions[0].arguments.at("command")) == "mpSelectPlayer" &&
		std::get<double>(runtime.GetState().at("card.client")) == 4,"choosing a row asks for its player");
	Check(runtime.SetState({{"mp.stat.client",4.0},{"mp.stat.color",1.0},{"mp.stat.flag_mode",true},{"mp.mute.available",true},
		{"mp.friend.available",true}},error,3.45),"the game selects the player");
	runtime.Frame(viewport,3.5);
	Check(text("players-b-1-chosen","display") == "block" && text("players-a-1-chosen","display") == "none","the chosen player is lit");
	Check(text("stat-band-1","display") == "block" && text("stat-award-5-cell","display") == "block","their team's color, and flag awards in flag modes");
	Check(runtime.RunEvent("players_friend",3.6,effects,error) && effects.actions.size() == 1 &&
		std::get<std::string>(effects.actions[0].arguments.at("command")) == "mpFriend" &&
		std::get<double>(runtime.GetState().at("card.client")) == 4,"Friend asks for the selected player");
	Check(runtime.RunEvent("players_mute",3.7,effects,error) && effects.actions.size() == 1 &&
		std::get<std::string>(effects.actions[0].arguments.at("command")) == "mpMute","and so does Mute");
	// Sixteen entries take the narrowest pitch and still fit the page.
	StateValues full;
	for (const auto& [list,count] : std::vector<std::pair<std::string,int>>{{"a",8},{"b",7},{"s",1}}) {
		full["mp.players."+list+".count"] = static_cast<double>(count);
		for (int row = 0; row < count; ++row) full["mp.players."+list+std::to_string(row)+".client"] = static_cast<double>(row+10);
	}
	Check(runtime.SetState(full,error,3.75),"sixteen players");
	runtime.Frame(viewport,3.8);
	const auto last = bounds("players-s-0"), page = bounds("page-players");
	// 325 dp less the headings and three bands leaves 231 dp for sixteen rows.
	Check(Near(bounds("players-a-0").height,231/16.f,.02f) && last.y+last.height <= page.y+page.height+.5f,
		"sixteen players share what the bands leave and fit");
	// Past sixteen clients the rows keep 14 dp and the last ones are clipped.
	StateValues over = full;
	over["mp.players.a.count"] = 16.0;
	for (int row = 8; row < 16; ++row) over["mp.players.a"+std::to_string(row)+".client"] = static_cast<double>(row+30);
	Check(runtime.SetState(over,error,3.8),"twenty-four clients");
	runtime.Frame(viewport,3.82);
	Check(Near(bounds("players-a-0").height,14,.02f),"rows never shrink below 14 dp");
	Check(runtime.SetState(lists,error,3.85),"back to six players");
	// The strip wraps both ways; choosing the current tab changes nothing.
	Check(runtime.RunEvent("tab_admin",4,effects,error) && runtime.RunEvent("onTabNext",4.01,effects,error),"E past the last tab");
	Check(std::get<double>(runtime.GetState().at("card.tab")) == 0,"wraps to the first");
	Check(runtime.RunEvent("onTabPrevious",4.02,effects,error) && std::get<double>(runtime.GetState().at("card.tab")) == 7,"Q wraps back");
	runtime.Frame(viewport,4.3);
	Check(runtime.RunEvent("tab_admin",4.4,effects,error) && std::get<double>(runtime.GetState().at("card.leaving")) == -1 &&
		effects.actions.empty(),"the current tab does nothing");
	// A page in development hands off to its stock page through the session.
	Check(runtime.RunEvent("stock_admin",5,effects,error) && effects.actions.size() == 1 &&
		std::get<std::string>(effects.actions[0].arguments.at("command")) == "mpStockPage" &&
		std::get<double>(runtime.GetState().at("card.stock_page")) == 7,"Admin hands off to the stock Admin page");
	Check(runtime.RunEvent("onBack",5.1,effects,error) && effects.actions.size() == 1 &&
		std::get<std::string>(effects.actions[0].arguments.at("command")) == "mpClose","Back resumes the match");
	// The prompt bar sits inside the card's bottom inset, Disconnect last.
	const auto prompts = bounds("prompts"), disconnect = bounds("prompt-disconnect"), menu = bounds("prompt-mainmenu");
	Check(prompts.y+prompts.height <= card.y+card.height-15 && prompts.y > card.y+card.height-60,"the prompt bar closes the card");
	Check(menu.x < disconnect.x && disconnect.x+disconnect.width <= card.x+card.width-23,"Main Menu, then Disconnect, at the trailing end");
	Check(runtime.RunEvent("disconnectModalShow",6,effects,error),"Disconnect asks first");
	runtime.Frame(viewport,6.3);
	Check(runtime.FocusedControl() == "disconnectModal_no","the confirmation's NO has focus");
	Check(runtime.RunEvent("disconnectModalHide",6.4,effects,error),"NO closes it");
	runtime.Frame(viewport,6.8);
	// The Server page: its rules and rotation, the current map in orange and
	// the slots past the rotation hidden; its tab keeps the focus.
	Check(runtime.SetState({{"mp.server.name",std::string("openQ4 test")},{"mp.server.message",std::string("Welcome\nRules: be fair")},
		{"mp.rule0",std::string("Team Deathmatch")},{"mp.rotation0",std::string("The Fragging Yard")},{"mp.rotation1",std::string("Lost Fleet")},
		{"mp.rotation2",std::string("Bloodwork")},{"mp.rotation_count",3.0},{"mp.rotation_current",1.0}},error,6.85),"publish the Server page");
	Check(runtime.RunEvent("tab_server",6.9,effects,error),"to the Server tab");
	runtime.Frame(viewport,7.06);
	Check(runtime.FocusedControl() == "tab-server","the Server page's tab keeps the focus");
	const auto current = runtime.PresentedValue("server-rotation-1","color"), other = runtime.PresentedValue("server-rotation-0","color");
	Check(current && Near(static_cast<float>(current->data[0]),.89f,.01f) && other && Near(static_cast<float>(other->data[3]),.7f,.01f),
		"the current map is orange");
	Check(text("server-rotation-2","display") == "block" && text("server-rotation-3","display") == "none","only the rotation's maps show");
	const auto message = bounds("server-message"), rules = bounds("server-rule-0");
	Check(message.y+message.height <= rules.y+.5f,"the message stays above the rules");
	// A long map name clips before the header's trailing texts.
	Check(runtime.SetState({{"mp.title",std::string(60,'W')},{"mp.mode",std::string("Team Deathmatch")},{"mp.clock",std::string("9:48")},
		{"mp.score",std::string("MARINES 0 - 0 STROGG")}},error,7),"publish the header");
	runtime.Frame(viewport,7.1);
	const auto title = bounds("header-title"), mode = bounds("header-mode"), score = bounds("header-score");
	Check(title.x+title.width <= mode.x+.5f && mode.x+mode.width <= bounds("header-clock").x,"the title yields to the mode, clock and score");
	Check(score.x+score.width <= card.x+card.width-24+.5f,"the score keeps the card's inset");
	// Every way out hides the card at once and releases the softening over
	// 250 ms; the next activation brings it back.
	Check(runtime.RunEvent("release",8,effects,error),"the card closes");
	runtime.Frame(viewport,8.125);
	Check(text("chrome","display") == "none" && Near(number("scene-softfocus","backdrop-blur"),3.75f,.05f),"closed at once, releasing");
	runtime.Frame(viewport,8.3);
	Check(Near(number("scene-softfocus","backdrop-blur"),0,.01f),"released after 250 ms");
	Check(runtime.RunEvent("onActivate",9,effects,error) && runtime.RunEvent("open",9,effects,error),"the card opens again");
	runtime.Frame(viewport,9.3);
	Check(text("chrome","display") == "block" && Near(number("card","opacity"),1,.001f),"shown again");
	// Reduced motion: no rise, the softening and fade in 80 ms.
	host.reducedMotion = true;
	runtime.SetReducedMotion(true,10);
	Check(runtime.RunEvent("release",10,effects,error) && runtime.RunEvent("onActivate",10.5,effects,error) &&
		runtime.RunEvent("open",10.5,effects,error),"reopened under reduced motion");
	runtime.Frame(viewport,10.54);
	const auto still = runtime.PresentedValue("card","transform");
	Check(still && Near(static_cast<float>(still->data[1]),0,.01f),"no rise");
	Check(number("scene-softfocus","backdrop-blur") > 1 && number("scene-softfocus","backdrop-blur") < 7,"the softening ramps over 80 ms");
	runtime.Frame(viewport,10.59);
	Check(Near(number("card","opacity"),1,.001f) && Near(number("scene-softfocus","backdrop-blur"),7.5f,.01f),"in within 80 ms");
	host.reducedMotion = false;
	runtime.SetReducedMotion(false,11);
	host.softFocus = false;
}

// The Escape card's Vote page (section 14.18): the running vote first, then
// the rows of the call the drafted game type uses, a locked one dimmed, each
// row's control requesting its verb with its new value, and Call Vote.
static void CheckVote(ScreenHost& host, const char* path) {
	const auto source = Read(path);
	Runtime runtime(host);
	std::vector<Diagnostic> diagnostics;
	Check(runtime.Initialize() && runtime.LoadDocument(source,"guis/menu/mp_escape.q4ui",diagnostics),"the Escape card loads for its Vote page");
	Viewport viewport; viewport.canvasHeight = 720; viewport.width = 1280; viewport.height = 720;
	std::string error;
	Runtime::EventEffects effects;
	const auto bounds = [&](const std::string& id) { Bounds b; Check(runtime.GetBounds(id,b),"a vote node is laid out"); return b; };
	const auto text = [&](const std::string& node, const char* property) {
		const auto value = runtime.PresentedValue(node,property); Check(value.has_value(),"a presented keyword"); return value->text;
	};
	const auto number = [&](const std::string& node, const char* property) {
		const auto value = runtime.PresentedValue(node,property); Check(value.has_value(),"a presented value"); return static_cast<float>(value->data[0]);
	};
	// The value a control's request carries, resolved through its action.
	const auto request = [&](const char* verb) {
		const auto actions = runtime.TakeActions();
		Check(actions.size() == 1 && actions[0].action == verb && actions[0].proposal.has_value(),"a row requests its verb");
		ActionInvocation invocation;
		Check(runtime.ResolveAction(actions[0].action,invocation,error,&*actions[0].proposal) &&
			invocation.operation == "session.menuValue" && std::get<std::string>(invocation.arguments.at("command")) == verb,
			"with the value verb");
		runtime.AcknowledgeControlProposal(actions[0].node,actions[0].proposalToken,true);
		return invocation.arguments.at("value");
	};
	const auto press = [&](MenuInput input, double at) { runtime.MenuAction(input,true,at); runtime.MenuAction(input,false,at+.01); };
	// An open list lays out the rows it shows; a row past its count takes no room.
	const auto Listed = [&](const char* option) { Bounds b; return runtime.GetBounds(option,b) && b.height > 0; };
	// No vote runs. The game publishes Team DM's rows (no capture, tournament
	// or control time limit), buying locked by the server, and Call Vote
	// unavailable until something changes.
	StateValues page = {{"mp.vote.running",false},{"mp.vote.call.shown",true},{"mp.vote.call.available",false},
		{"mp.vote.call.label",std::string("CALL VOTE")},{"mp.vote.call.reason",std::string("Change a setting to call a vote.")},
		{"mp.vote.map_count",3.0},{"mp.vote.map0",std::string("The Fragging Yard")},{"mp.vote.map1",std::string("Lost Fleet")},
		{"mp.vote.map2",std::string("Bloodwork")},{"mp.vote.map",1.0},{"mp.vote.gametype_count",12.0},
		{"mp.vote.gametype2",std::string("Team DM")},{"mp.vote.gametype",2.0},{"mp.vote.timelimit",10.0},{"mp.vote.fraglimit",20.0},
		{"mp.vote.balance",true},{"mp.vote.shuffle",false},{"mp.vote.restart",false},{"mp.vote.buying",false},
		{"mp.vote.kick_count",3.0},{"mp.vote.kick0",std::string("Anderson")},{"mp.vote.kick1",std::string("Rhodes")},{"mp.vote.kick",-1.0},
		{"mp.vote.locked",true}};
	const char* const keys[] = {"map","gametype","timelimit","fraglimit","capturelimit","tourneylimit","controltime","balance","shuffle",
		"restart","buying","kick"};
	for (const char* key : keys) {
		const std::string field = key;
		page["mp.vote."+field+".row_shown"] = field != "capturelimit" && field != "tourneylimit" && field != "controltime";
		page["mp.vote."+field+".row_allowed"] = field != "buying";
	}
	Check(runtime.SetState(page,error,1),"publish the Vote page");
	Check(runtime.RunEvent("open",1,effects,error) && runtime.RunEvent("tab_vote",1.01,effects,error),"open on the Vote tab");
	runtime.Frame(viewport,1.4);
	Check(text("vote-none","display") == "block" && text("vote-caller","display") == "none" && text("vote-yes-slot","display") == "none" &&
		text("vote-no-slot","display") == "none","with no vote running, the page says so and offers no ballot");
	Check(runtime.FocusedControl() == "vote-row-map","and opens on its first row");
	// The rows the drafted game type uses stack in order without gaps above
	// Call Vote; the locked one dims with its lock, and the heading says why.
	float previous = 0;
	int shown = 0;
	for (const char* key : keys) {
		const std::string row = std::string("vote-row-")+key;
		if (!std::get<bool>(page.at("mp.vote."+std::string(key)+".row_shown"))) {
			Check(text(row,"display") == "none","a row the drafted game type does not use is hidden");
			continue;
		}
		const auto box = bounds(row);
		Check(text(row,"display") == "block" && Near(box.height,26,.01f) && (!shown || Near(box.y,previous,.01f)),"shown rows stack");
		previous = box.y+box.height; ++shown;
	}
	Check(shown == 9 && previous <= bounds("vote-call-slot").y+.5f,"nine rows fit above Call Vote");
	Check(Near(number("vote-row-buying","opacity"),.38f,.001f) && text("vote-row-buying-lock","display") == "block" &&
		Near(number("vote-row-map","opacity"),1,.001f) && text("vote-row-map-lock","display") == "none","a locked row dims with its lock");
	Check(text("vote-locked","display") == "block" && !runtime.FocusControl("vote-row-buying",1.41),"it says why and takes no focus");
	const auto left = bounds("vote-heading-running"), right = bounds("vote-heading-call");
	Check(left.x+left.width <= right.x && bounds("vote-row-map").x >= right.x-.5f,"the running vote stands beside the call");
	// Call Vote has nothing to call yet: it shakes and asks nothing.
	Check(text("vote-call-reason","display") == "block" && text("vote-call-lock","display") == "block","Call Vote says why it waits");
	Check(runtime.RunEvent("vote_call",1.5,effects,error) && effects.actions.empty(),"and asks nothing");
	// Each row's control requests its verb with its new value: Right steps a
	// limit, accept checks a box, and a list unfolds its game's rows.
	Check(runtime.FocusControl("vote-row-timelimit",1.6),"focus the time limit");
	press(MenuInput::Right,1.61);
	Check(std::get<double>(request("mpVoteTimeLimit")) == 11,"Right asks for one more minute");
	Check(runtime.FocusControl("vote-row-shuffle",1.7),"focus shuffle");
	press(MenuInput::Accept,1.71);
	Check(std::get<bool>(request("mpVoteShuffle")),"accept asks to shuffle");
	Check(runtime.FocusControl("vote-row-map",1.8) && runtime.OpenChoicePopup("vote-row-map",1.8),"the map list unfolds");
	runtime.Frame(viewport,1.85);
	Check(Listed("vote-row-map-option-2") && !Listed("vote-row-map-option-3"),"it lists the game's maps");
	const auto popup = bounds("vote-row-map-popup"), card = bounds("card");
	Check(popup.y >= bounds("vote-row-map").y && popup.y+popup.height <= card.y+card.height,"under its row, inside the card");
	press(MenuInput::Down,1.9);
	press(MenuInput::Accept,1.95);
	Check(std::get<double>(request("mpVoteMap")) == 2,"choosing a map asks for its row");
	Check(runtime.FocusControl("vote-row-kick",2) && runtime.OpenChoicePopup("vote-row-kick",2),"the kick list unfolds");
	runtime.Frame(viewport,2.05);
	Check(Listed("vote-row-kick-option-0") && Listed("vote-row-kick-option-2") && !Listed("vote-row-kick-option-3"),
		"no one, then the other players");
	press(MenuInput::Down,2.1);
	press(MenuInput::Accept,2.15);
	Check(std::get<double>(request("mpVoteKick")) == 0,"choosing a player asks for their row");
	// A vote runs: who called it, its lines, the time left and the tally, and
	// Yes and No with the keys bound to them; the page opens on Yes.
	Check(runtime.SetState({{"mp.vote.running",true},{"mp.vote.caller",std::string("CALLED BY Anderson")},
		{"mp.vote.line0",std::string("MAP Lost Fleet")},{"mp.vote.line1",std::string("TIME LIMIT 15")},{"mp.vote.line_count",2.0},
		{"mp.vote.time",std::string("TIME LEFT 0:27")},{"mp.vote.tally",std::string("1 YES VOTES, 0 NO VOTES")},
		{"mp.vote.yes.shown",true},{"mp.vote.yes.available",true},{"mp.vote.yes.label",std::string("VOTE YES")},
		{"mp.keys.vote_yes",std::string("F1")},{"mp.keys.vote_yes_bound",true},{"mp.vote.no.shown",true},{"mp.vote.no.available",true},
		{"mp.vote.no.label",std::string("VOTE NO")},{"mp.keys.vote_no",std::string("F2")},{"mp.keys.vote_no_bound",true},
		{"mp.vote.call.reason",std::string("There is already a vote in progress")}},error,3),"a vote runs");
	Check(runtime.RunEvent("tab_team",3.01,effects,error) && runtime.RunEvent("tab_vote",3.02,effects,error),"back to the Vote tab");
	runtime.Frame(viewport,3.3);
	Check(text("vote-none","display") == "none" && text("vote-caller","display") == "block" && text("vote-line-1","display") == "block" &&
		text("vote-line-2","display") == "none" && text("vote-time","display") == "block" && text("vote-tally","display") == "block",
		"the caller, the vote's lines, the time left and the tally");
	Check(runtime.FocusedControl() == "vote-yes" && text("vote-yes-keycap","display") == "block" && text("vote-no-keycap","display") == "block",
		"the page opens on Yes, and each ballot shows its key");
	const auto yes = bounds("vote-yes-label"), keycap = bounds("vote-yes-keycap"), plate = bounds("vote-yes");
	Check(keycap.x >= yes.x+yes.width && keycap.x+keycap.width <= plate.x+plate.width,"the key follows the label on the plate");
	const auto lines = bounds("vote-tally"), ballots = bounds("vote-yes-slot");
	Check(lines.y+lines.height <= ballots.y && bounds("vote-no-slot").y >= ballots.y+45,"the ballots follow the tally");
	Check(runtime.RunEvent("vote_yes",3.4,effects,error) && effects.actions.size() == 1 &&
		std::get<std::string>(effects.actions[0].arguments.at("command")) == "mpVoteYes","Yes asks the game");
	// Once the player has voted the ballots lock and say why; the keys go.
	Check(runtime.SetState({{"mp.vote.yes.available",false},{"mp.vote.no.available",false},
		{"mp.vote.yes.reason",std::string("You have voted.")},{"mp.vote.no.reason",std::string("You have voted.")}},error,3.5),"voted");
	runtime.Frame(viewport,3.6);
	Check(text("vote-yes-keycap","display") == "none" && text("vote-yes-lock","display") == "block" && text("vote-no-reason","display") == "block",
		"a ballot the player cannot cast locks and says why");
	Check(runtime.RunEvent("vote_no",3.7,effects,error) && effects.actions.empty(),"and asks nothing");
	// Another tab takes the page's input away.
	Check(runtime.RunEvent("tab_team",3.8,effects,error),"to the Team tab");
	runtime.Frame(viewport,4.1);
	Check(!runtime.CanActivateControl("vote-row-map",4.1) && !runtime.CanActivateControl("vote-call",4.1),"the Vote page takes no input");
}

// The multiplayer cards' Settings pages and the Escape card's Voice page
// (section 14.18): the player's rows, the rail color swatches, the
// appearance table with the teammates' column only in team modes, the hand-
// offs, and each control requesting its verb or player setting.
static void CheckSettings(ScreenHost& host, const char* escapePath, const char* welcomePath) {
	std::string error;
	Runtime::EventEffects effects;
	Viewport viewport; viewport.canvasHeight = 720; viewport.width = 1280; viewport.height = 720;
	const auto press = [](Runtime& runtime, MenuInput input, double at) { runtime.MenuAction(input,true,at); runtime.MenuAction(input,false,at+.01); };
	// The one action a control queued, resolved through its descriptor.
	const auto taken = [&](Runtime& runtime, const char* action) {
		const auto actions = runtime.TakeActions();
		Check(actions.size() == 1 && actions[0].action == action,"a control requests its action");
		ActionInvocation invocation;
		const StateValue* input = actions[0].proposal ? &*actions[0].proposal : nullptr;
		Check(runtime.ResolveAction(actions[0].action,invocation,error,input),"the action resolves");
		if (actions[0].proposalToken) runtime.AcknowledgeControlProposal(actions[0].node,actions[0].proposalToken,true);
		return invocation;
	};
	{
		Runtime runtime(host);
		std::vector<Diagnostic> diagnostics;
		Check(runtime.Initialize() && runtime.LoadDocument(Read(escapePath),"guis/menu/mp_escape.q4ui",diagnostics),"the Escape card loads for its Settings page");
		const auto bounds = [&](const std::string& id) { Bounds b; Check(runtime.GetBounds(id,b),"a settings node is laid out"); return b; };
		const auto text = [&](const std::string& node, const char* property) {
			const auto value = runtime.PresentedValue(node,property); Check(value.has_value(),"a presented keyword"); return value->text;
		};
		StateValues page = {{"mp.settings.name",std::string("Anderson")},{"mp.settings.clan",std::string("Q4")},{"mp.settings.rail",3.0},
			{"mp.model0_count",3.0},{"mp.model0.0",std::string("Marine")},{"mp.model0.1",std::string("Kane")},{"mp.model0.2",std::string("Rhodes")},
			{"mp.model0",1.0},{"mp.model0.row_shown",true},{"mp.model1_count",2.0},{"mp.model1.0",std::string("Off")},
			{"mp.model1.1",std::string("Kane")},{"mp.model1",0.0},{"mp.model1.row_shown",true},{"mp.model2_count",2.0},
			{"mp.model2.0",std::string("Off")},{"mp.model2.1",std::string("Kane")},{"mp.model2",0.0},{"mp.model2.row_shown",true}};
		Check(runtime.SetState(page,error,1),"publish the Settings page");
		Check(runtime.RunEvent("open",1,effects,error) && runtime.RunEvent("tab_settings",1.01,effects,error),"open on the Settings tab");
		runtime.Frame(viewport,1.4);
		Check(runtime.FocusedControl() == "settings-name","the page opens on the player's name");
		// The player's rows stack, the hand-off plates below them inside the page.
		float previous = bounds("settings-name").y;
		for (const char* row : {"settings-clan","settings-model","settings-rail","settings-handicap"}) {
			const auto box = bounds(row);
			Check(Near(box.y,previous+26,.01f) && Near(box.height,26,.01f),"the player's rows stack");
			previous = box.y;
		}
		const auto system = bounds("settings-mpSettingsSystem"), pageBox = bounds("page-settings");
		Check(bounds("settings-mpSettingsControls").y >= previous+26 && system.y+system.height <= pageBox.y+pageBox.height+.5f,
			"Controls, Game Options and System follow inside the page");
		// Name and clan hand off to the classic Settings page, which edits them.
		Check(runtime.RunEvent("classic_settings",1.5,effects,error) && effects.actions.size() == 1 &&
			std::get<std::string>(effects.actions[0].arguments.at("command")) == "mpStockPage" &&
			std::get<double>(runtime.GetState().at("card.stock_page")) == 4,"name and clan hand off to the classic Settings page");
		// The swatch the player's tint matches stands taller; each asks the game for its color.
		const auto chosen = runtime.PresentedValue("settings-rail-3-chip","transform"), other = runtime.PresentedValue("settings-rail-0-chip","transform");
		Check(chosen && other && chosen->data[1] < -1 && Near(static_cast<float>(other->data[1]),0,.01f),"the player's rail color stands taller");
		Check(runtime.RunEvent("rail_5",1.6,effects,error) && effects.actions.size() == 1 &&
			std::get<std::string>(effects.actions[0].arguments.at("command")) == "mpRail" &&
			std::get<double>(runtime.GetState().at("card.rail")) == 5,"a swatch asks for its color");
		// The handicap slider and the appearance lists set their player settings.
		Check(runtime.FocusControl("settings-handicap",1.7),"focus the handicap");
		press(runtime,MenuInput::Left,1.71);
		auto invocation = taken(runtime,"set.ui_handicap");
		Check(invocation.operation == "settings.player.set" && std::get<std::string>(invocation.arguments.at("cvar")) == "ui_handicap" &&
			std::get<double>(invocation.arguments.at("value")) == 99,"Left lowers the handicap");
		Check(runtime.FocusControl("settings-row-1-opponents",1.8) && runtime.OpenChoicePopup("settings-row-1-opponents",1.8),"the opponents' outline unfolds");
		runtime.Frame(viewport,1.85);
		press(runtime,MenuInput::Down,1.9);
		press(runtime,MenuInput::Accept,1.95);
		invocation = taken(runtime,"set.cl_player_outline_enemy");
		Check(std::get<std::string>(invocation.arguments.at("value")) == "0.35","a level takes its stock value");
		Check(runtime.FocusControl("settings-row-0-teammates",2) && runtime.OpenChoicePopup("settings-row-0-teammates",2),"the teammates' model unfolds");
		runtime.Frame(viewport,2.05);
		press(runtime,MenuInput::Down,2.1);
		press(runtime,MenuInput::Accept,2.15);
		Check(std::get<double>(taken(runtime,"mpModelTeam").arguments.at("value")) == 1,"a model asks the game for its row");
		const auto opponents = bounds("settings-row-1-opponents"), teammates = bounds("settings-row-1-teammates");
		Check(opponents.x+opponents.width <= teammates.x && Near(opponents.y,teammates.y,.01f),"the teammates' cell stands beside the opponents'");
		Check(text("settings-team-note","display") == "none","no team-mode note in a team mode");
		// Outside team modes the teammates' column goes and the note says why.
		Check(runtime.SetState({{"mp.model2.row_shown",false}},error,2.2),"a deathmatch");
		runtime.Frame(viewport,2.3);
		Check(text("settings-row-1-teammates","display") == "none" && text("settings-heading-teammates","display") == "none" &&
			text("settings-team-note","display") == "block" && !runtime.FocusControl("settings-row-0-teammates",2.31),
			"outside team modes only the opponents' column shows");
		// System leaves for the main menu's page.
		Check(runtime.FocusControl("settings-mpSettingsSystem",2.4),"focus System");
		press(runtime,MenuInput::Accept,2.41);
		Check(taken(runtime,"mpSettingsSystem").operation == "session.menu","System leaves for the main menu's page");
		// The Voice page: its toggles and sliders set their settings; the
		// push-to-talk key shows when bound; the test waits for voice chat.
		Check(runtime.RunEvent("tab_voice",3,effects,error),"to the Voice tab");
		runtime.Frame(viewport,3.3);
		Check(runtime.FocusedControl() == "voice-send","the Voice page opens on sending voice");
		press(runtime,MenuInput::Accept,3.31);
		invocation = taken(runtime,"set.s_voiceChatSend");
		Check(std::get<std::string>(invocation.arguments.at("cvar")) == "s_voiceChatSend" && !std::get<bool>(invocation.arguments.at("value")),
			"accept stops sending voice");
		Check(runtime.FocusControl("voice-volume",3.4),"focus the receive volume");
		press(runtime,MenuInput::Left,3.41);
		Check(std::abs(std::get<double>(taken(runtime,"set.s_voiceVolume").arguments.at("value"))-.95) < 1e-6,"Left lowers the volume a step");
		Check(text("voice-unbound","display") == "block" && text("voice-key","display") == "none","an unbound key says so");
		Check(runtime.SetState({{"mp.keys.voice_chat",std::string("V")},{"mp.keys.voice_chat_bound",true}},error,3.5),"bind push to talk");
		runtime.Frame(viewport,3.6);
		Check(text("voice-unbound","display") == "none" && text("voice-key","display") == "block","the bound key shows");
		Check(text("voice-test-lock","display") == "block" && text("voice-test-reason","display") == "block","the test is unavailable and says why");
		Check(runtime.RunEvent("voice_test",3.7,effects,error) && effects.actions.empty(),"and asks nothing");
	}
	{
		Runtime runtime(host);
		std::vector<Diagnostic> diagnostics;
		Check(runtime.Initialize() && runtime.LoadDocument(Read(welcomePath),"guis/menu/mp_welcome.q4ui",diagnostics),"the Welcome card loads for its Settings page");
		const auto text = [&](const std::string& node, const char* property) {
			const auto value = runtime.PresentedValue(node,property); Check(value.has_value(),"a presented keyword"); return value->text;
		};
		Check(runtime.SetState({{"mp.crosshair",0.0},{"mp.model0_count",1.0},{"mp.model0.0",std::string("Marine")},{"mp.model0",0.0}},error,1),
			"publish Welcome's Settings page");
		Check(runtime.RunEvent("open",1,effects,error) && runtime.RunEvent("tab_settings",1.01,effects,error),"open on Welcome's Settings tab");
		runtime.Frame(viewport,1.4);
		Check(runtime.FocusedControl() == "settings-name","Welcome's Settings opens on the player's name");
		Check(text("settings-crosshair-weapon","display") == "block" && text("settings-crosshair-image","display") == "none",
			"each weapon's own crosshair, said in words");
		Check(runtime.SetState({{"mp.crosshair",3.0},{"mp.crosshair_image",std::string("gfx/guis/crosshairs/crosshair_lightninggun")}},error,1.5),
			"a custom crosshair");
		runtime.Frame(viewport,1.6);
		Check(text("settings-crosshair-weapon","display") == "none" && text("settings-crosshair-image","display") == "block","the custom one shows");
		Check(runtime.FocusControl("settings-crosshair",1.7),"focus the crosshair");
		press(runtime,MenuInput::Right,1.71);
		const auto invocation = taken(runtime,"mpCrosshair");
		Check(invocation.operation == "session.menuValue" && std::get<double>(invocation.arguments.at("value")) == 4,"Right asks for the next crosshair");
	}
}

// The multiplayer Welcome card (section 14.18): centered, each mode's join
// choices, a refused team card, the Players page without choices, the hand-off
// to the join panel's settings, Spectate on Back and Leave Server asking first.
static void CheckWelcome(ScreenHost& host, const char* path) {
	const auto source = Read(path);
	Document document; std::vector<Diagnostic> diagnostics;
	const bool valid = document.Load(source,diagnostics);
	for (const auto& diagnostic : diagnostics) std::fprintf(stderr,"mp_welcome %s: %s\n",diagnostic.pointer.c_str(),diagnostic.message.c_str());
	Check(valid && document.Model().id == "openq4.mp_welcome" && document.Model().canvasHeight == 720,"the Welcome card validates");
	CheckSessionActions(document);
	Runtime runtime(host);
	Check(runtime.Initialize() && runtime.LoadDocument(source,"guis/menu/mp_welcome.q4ui",diagnostics),"the Welcome card loads into a runtime");
	Viewport viewport; viewport.canvasHeight = 720; viewport.width = 1280; viewport.height = 720;
	std::string error;
	Runtime::EventEffects effects;
	const auto bounds = [&](const std::string& id) { Bounds b; Check(runtime.GetBounds(id,b),"a Welcome node is laid out"); return b; };
	const auto number = [&](const char* node, const char* property) {
		const auto value = runtime.PresentedValue(node,property); Check(value.has_value(),"a presented value"); return static_cast<float>(value->data[0]);
	};
	const auto text = [&](const char* node, const char* property) {
		const auto value = runtime.PresentedValue(node,property); Check(value.has_value(),"a presented keyword"); return value->text;
	};
	const auto asked = [&](const char* command) {
		return effects.actions.size() == 1 && std::get<std::string>(effects.actions[0].arguments.at("command")) == command;
	};
	// A team mode: the balance rule refuses the Marines, the Strogg are open,
	// and Auto join names the team it picks.
	Check(runtime.SetState({{"mp.welcome.title",std::string("WELCOME TO OPENQ4")},{"mp.welcome.players",std::string("6/12 PLAYERS")},
		{"mp.welcome.match",std::string("Team Deathmatch - The Fragging Yard")},{"mp.welcome.state",std::string("MATCH IN PROGRESS")},
		{"mp.clock",std::string("9:12")},{"mp.welcome.limit",std::string("Frag limit 50")},{"mp.welcome.team_mode",true},
		{"mp.welcome.team0.score",std::string("12")},{"mp.welcome.team0.count",std::string("4")},{"mp.welcome.team0.flag",std::string("FLAG AT BASE")},
		{"mp.welcome.team1.score",std::string("9")},{"mp.welcome.team1.count",std::string("2")},
		{"mp.join0.shown",true},{"mp.join0.available",false},{"mp.join0.label",std::string("MARINES")},
		{"mp.join0.reason",std::string("Too many players on the Marine team.")},
		{"mp.join1.shown",true},{"mp.join1.available",true},{"mp.join1.label",std::string("STROGG")},
		{"mp.join2.shown",true},{"mp.join2.available",true},{"mp.join2.label",std::string("AUTO JOIN")},{"mp.join2.detail",std::string("Joins STROGG.")},
		{"mp.join3.shown",true},{"mp.join3.available",true},{"mp.join3.label",std::string("SPECTATE")}},error,1),"publish the Join page");
	host.softFocus = true;
	Check(runtime.RunEvent("open",2,effects,error),"the Welcome card opens");
	runtime.Frame(viewport,2.3);
	const auto card = bounds("card");
	Check(Near(card.x+card.width/2,640) && Near(card.y+card.height/2,360),"the Welcome card is centered");
	Check(card.width >= 648-.5f && card.width <= 928+.5f && Near(card.height,477,1),"the Welcome card takes the specified Escape height and fits a 4:3 view");
	Check(runtime.FocusedControl() == "join-slot-2","Auto join has focus");
	Check(text("join-teams","display") == "block" && text("join-solo","display") == "none","team modes show the team cards");
	const auto marines = bounds("join-slot-0"), strogg = bounds("join-slot-1"), automatic = bounds("join-slot-2");
	Check(marines.x+marines.width <= strogg.x && Near(marines.y,strogg.y) && automatic.y >= marines.y+marines.height,
		"the team cards stand side by side above Auto join");
	Check(Near(number("join-slot-0","opacity"),.6f,.001f) && text("join-slot-0-lock","display") == "block" &&
		text("join-slot-0-reason","display") == "block","a refused team dims with its lock and reason");
	Check(Near(number("join-slot-1","opacity"),1,.001f) && text("join-slot-1-lock","display") == "none" &&
		text("join-slot-1-reason","display") == "none","an open team has neither");
	Check(text("join-slot-2-detail","display") == "block","Auto join names the team it picks");
	const auto spectate = bounds("prompt-back-0"), leave = bounds("prompt-leave");
	Check(spectate.x >= card.x+23 && leave.x+leave.width <= card.x+card.width-23,"the prompt bar keeps the card's insets");
	Check(runtime.RunEvent("join_slot_1",2.4,effects,error) && asked("mpWelcomeAction") &&
		std::get<double>(runtime.GetState().at("card.welcome_action")) == 1,"an open team card joins its team");
	Check(runtime.RunEvent("join_slot_0",2.5,effects,error) && effects.actions.empty(),"a refused one asks nothing");
	runtime.Frame(viewport,2.56);
	const auto shaking = runtime.PresentedValue("join-slot-0-slot","transform");
	Check(shaking && std::abs(shaking->data[0]) > .5f,"it shakes instead");
	Check(runtime.RunEvent("join_slot_2",2.9,effects,error) && asked("mpWelcomeAction") &&
		std::get<double>(runtime.GetState().at("card.welcome_action")) == 2,"Auto join asks the game");
	// Deathmatch: the three leaders, then Join game focused and Spectate.
	Check(runtime.SetState({{"mp.welcome.team_mode",false},{"mp.welcome.leader0.name",std::string("Anderson")},
		{"mp.welcome.leader0.score",std::string("7")},{"mp.welcome.leader1.name",std::string("Kane")},{"mp.welcome.leader1.score",std::string("5")},
		{"mp.join0.available",true},{"mp.join0.label",std::string("JOIN GAME")},{"mp.join0.reason",std::string("")},
		{"mp.join1.label",std::string("SPECTATE")},{"mp.join2.shown",false},{"mp.join3.shown",false}},error,3),"publish deathmatch");
	Check(runtime.RunEvent("tab_server",3.1,effects,error) && runtime.RunEvent("tab_join",3.3,effects,error),"back to the Join tab");
	runtime.Frame(viewport,3.5);
	Check(text("join-solo","display") == "block" && text("join-teams","display") == "none" && text("join-leaders","display") == "block" &&
		text("join-arenas","display") == "none","deathmatch shows its leaders");
	Check(runtime.FocusedControl() == "join-solo-0","Join game has focus");
	const auto first = runtime.PresentedValue("join-leader-0-rank","text"), third = runtime.PresentedValue("join-leader-2-rank","text");
	Check(first && first->text == "1" && third && third->text.empty(),"leaders are ranked, an empty place unnumbered");
	Check(runtime.RunEvent("join_solo_0",3.6,effects,error) && asked("mpWelcomeAction") &&
		std::get<double>(runtime.GetState().at("card.welcome_action")) == 0,"Join game asks the game");
	// Tourney: the arenas in play instead of the leaders.
	Check(runtime.SetState({{"mp.welcome.arena_count",2.0},{"mp.welcome.arena0",std::string("Arena 1   Anderson 2 - 1 Kane")},
		{"mp.welcome.arena1",std::string("Arena 2   Voss 0 - 0 Rhodes")}},error,3.7),"publish Tourney's arenas");
	runtime.Frame(viewport,3.8);
	Check(text("join-arenas","display") == "block" && text("join-leaders","display") == "none","Tourney shows its arenas");
	// The Players page lists without choices; its tab keeps the focus.
	Check(runtime.SetState({{"mp.players.a.shown",true},{"mp.players.a.title",std::string("MARINES")},{"mp.players.a.count",2.0},
		{"mp.players.a0.name",std::string("Anderson")},{"mp.players.a1.name",std::string("Kane")},{"mp.players.a1.local",true}},error,3.9),
		"publish the Players page");
	Check(runtime.RunEvent("tab_players",4,effects,error),"to the Players tab");
	runtime.Frame(viewport,4.2);
	Check(runtime.FocusedControl() == "tab-players" && !runtime.CanActivateControl("players-a-0",4.2),"rows are not choices on Welcome");
	Check(text("players-a-1","display") == "block" && text("players-a-2","display") == "none" &&
		text("players-a-1-marker","display") == "block","the lists show their players and the player's own row");
	// Settings' name and clan hand off to the classic Settings page, which edits them.
	Check(runtime.RunEvent("classic_settings",4.3,effects,error) && asked("mpStockPage") &&
		std::get<double>(runtime.GetState().at("card.stock_page")) == 3,"name and clan hand off to the classic Settings page");
	// Back spectates for now; Leave Server asks first.
	Check(runtime.RunEvent("onBack",4.4,effects,error) && asked("mpClose"),"Back closes the card and the player spectates");
	Check(runtime.RunEvent("leaveModalShow",4.5,effects,error),"Leave Server asks first");
	runtime.Frame(viewport,4.8);
	Check(runtime.FocusedControl() == "leaveModal_no","the confirmation's NO has focus");
	Check(runtime.RunEvent("leaveModalHide",4.9,effects,error),"NO closes it");
	host.softFocus = false;
}

int main(int argc, char** argv) {
	Check(argc == 9,"usage: title.q4ui pause.q4ui loading.q4ui pause_strogg.q4ui singleplayer.q4ui campaigns.q4ui mp_escape.q4ui mp_welcome.q4ui");
	CheckSchema();
	ScreenHost host;
	CheckTransformedClip(host);
	// Title: canvas scaling, the lit field, the multiplied emblem and CONTINUE.
	{
		const auto source = Read(argv[1]);
		Document document; std::vector<Diagnostic> diagnostics;
		if (!document.Load(source,diagnostics)) for (const auto& d : diagnostics) std::fprintf(stderr,"%u:%u %s %s\n",unsigned(d.line),unsigned(d.column),d.pointer.c_str(),d.message.c_str());
		Check(diagnostics.empty() && document.Model().id == "openq4.title" && document.Model().canvasHeight == 720,"title document validates");
		CheckSessionActions(document);
		Runtime runtime(host);
		Check(runtime.Initialize(),"retained runtime");
		Check(runtime.LoadDocument(source,"guis/menu/title.q4ui",diagnostics),"title loads into a runtime");
		Viewport viewport; viewport.canvasHeight = 720;
		runtime.Frame(viewport,1);
		Bounds label, focus;
		Check(runtime.GetBounds("nav_singleplayer-label",label),"navigation label laid out");
		// 1280x720: the 4:3 canvas starts at 160 px; labels at 44 u (66 dp).
		Check(Near(label.x,160+66),"labels sit at 44 u on the canvas at 16:9");
		Check(Additive(host),"the light band and focus light submit additive light");
		Check(std::any_of(host.draws.begin(),host.draws.end(),[&](const auto& draw) { return draw.material == host.multiply; }),
			"the emblem multiplies the lit field through the host material");
		Check(std::find(host.materials.begin(),host.materials.end(),"gfx/guis/mainmenu/level_mcc.dds") != host.materials.end(),"the backdrop montage loads its levelshots");
		Check(std::find(host.materials.begin(),host.materials.end(),"q4-add/gfx/guis/mainmenu/q4text") != host.materials.end(),"the wordmark is additive light");
		// Without a save CONTINUE collapses: SINGLE PLAYER takes the first row.
		const float firstRow = label.y;
		std::string error;
		Check(runtime.SetState({{"menu_continue",true},{"menu_continue_title",std::string("Air Defense Bunker")},
			{"menu_continue_shot",std::string("savegames/quick.tga")}},error,2),"publish the newest save");
		runtime.Frame(viewport,2.5);
		Check(runtime.GetBounds("nav_singleplayer-label",label) && Near(label.y-firstRow,45),"CONTINUE leads when a save exists");
		viewport.width = 1920; viewport.height = 1080;
		runtime.Frame(viewport,3);
		Check(runtime.GetBounds("nav_singleplayer-label",label) && Near(label.x,240+99) && Near(label.y,(firstRow+45)*1.5f,1.5f),
			"canvas follows the 1080 p view height");
		ActionInvocation invocation;
		Check(runtime.ResolveAction("continue",invocation,error) && std::get<std::string>(invocation.arguments.at("command")) == "continue",
			"CONTINUE requests the session's continue operation");
		Check(!runtime.SetState({{"menu_continue_shot",std::string("../escape.tga")}},error,4),"an unsafe picture source rejects the whole batch");
		Check(runtime.FocusControl("nav_settings",5),"keyboard focus reaches a navigation plate");
		runtime.Frame(viewport,5.5);
		Check(runtime.GetBounds("nav_settings-focus",focus),"focus rail laid out");
		Check(runtime.HasEvent("exitModalShow") && runtime.HasEvent("onBack"),"Back asks before leaving the game");
		// The emblem's glint turns once every 9 s under its wedge mask while
		// the rim inside turns back; reduced motion keeps only the rim.
		Runtime::EventEffects init;
		Check(runtime.RunEvent("onInit",6,init,error),"the title starts its ambient loops");
		runtime.Frame(viewport,6+4.5);
		const auto glint = runtime.PresentedValue("emblem-glint","transform");
		const auto rim = runtime.PresentedValue("emblem-glint-rim","transform");
		Check(glint && rim && Near(static_cast<float>(glint->data[4]),180,1) && Near(static_cast<float>(rim->data[4]),-180,1),
			"half way round at 4.5 s, the rim held in place");
		// Statistics are per frame, and the glint is the title's only mask.
		Check(runtime.Statistics().maskApplications == 1,"the wedge masks the glint");
		// A settled title draws its artwork from cache: only the turning wedge
		// tessellates again (its counter-turned rim stays put within float
		// jitter), and the zero-opacity rails, markers and lines take no layers.
		runtime.Frame(viewport,6+4.6);
		Check(runtime.Statistics().vectorPathsCompiled == 1,"a settled title tessellates only the turning wedge");
		Check(runtime.Statistics().layerElisions > 0,"zero-opacity controls take no composition layers");
		const auto shown = runtime.PresentedValue("emblem-glint","display");
		host.reducedMotion = true;
		runtime.Frame(viewport,11);
		const auto hidden = runtime.PresentedValue("emblem-glint","display");
		Check(shown && shown->text == "block" && hidden && hidden->text == "none" && runtime.Statistics().maskApplications == 0,
			"reduced motion hides the glint");
		host.reducedMotion = false;
		// Depth (section 13.8): the backdrop leans 6 dp away from the pointer and
		// the frame a third of that; reduced motion holds both still.
		Check(runtime.SetState({{"pointer_x",1.0},{"pointer_y",-0.5}},error,11.5),"publish the pointer");
		runtime.Frame(viewport,11.6);
		const auto backdrop = runtime.PresentedValue("depth-backdrop","transform");
		const auto frameLean = runtime.PresentedValue("depth-frame","transform");
		Check(backdrop && Near(static_cast<float>(backdrop->data[0]),-6,.01f) && Near(static_cast<float>(backdrop->data[1]),3,.01f) &&
			frameLean && Near(static_cast<float>(frameLean->data[0]),-1.98f,.01f),"the layers lean away from the pointer, deeper further");
		host.reducedMotion = true;
		runtime.Frame(viewport,11.7);
		const auto still = runtime.PresentedValue("depth-backdrop","transform");
		Check(still && Near(static_cast<float>(still->data[0]),0,.001f) && Near(static_cast<float>(still->data[1]),0,.001f),
			"reduced motion holds the layers still");
		host.reducedMotion = false;
		// Title carry (section 13.8): SETTINGS travels from its row into the
		// page's title slot at 39,19 u and settles at the 18 dp title size.
		// With a save shown its row is the fifth: 212.2 + 4 * 30 u.
		Runtime::EventEffects carry;
		Check(runtime.RunEvent("carry_settings",12,carry,error),"a page hand-off carries its label");
		runtime.Frame(viewport,12.002);
		const auto begin = runtime.PresentedValue("title-carry","transform");
		const auto carried = runtime.PresentedValue("title-carry","text");
		Check(begin && Near(static_cast<float>(begin->data[0]),7.5f,.1f) && Near(static_cast<float>(begin->data[1]),(212.2f+120+2.8f-19)*1.5f,.2f),
			"the carry starts on the chosen row");
		Check(carried && carried->text == "#str_200009","the carried title is the chosen item's label");
		runtime.Frame(viewport,12.6);
		const auto landed = runtime.PresentedValue("title-carry","transform");
		const auto visible = runtime.PresentedValue("title-carry","opacity");
		Check(landed && Near(static_cast<float>(landed->data[1]),-(1-.75f)*24.4f*1.5f/2,.1f) && Near(static_cast<float>(landed->data[2]),.75f,.001f) &&
			visible && Near(static_cast<float>(visible->data[0]),1,.001f),"it lands in the title slot at the title size");
		Runtime::EventEffects home;
		Check(runtime.RunEvent("returnHome",13,home,error) || runtime.PlayTimeline("returnHome",13),"back home");
		runtime.Frame(viewport,13.7);
		const auto gone = runtime.PresentedValue("title-carry","opacity");
		Check(gone && Near(static_cast<float>(gone->data[0]),0,.001f),"home starts without a carried title");
		// The exit confirmation (section 6) at 1080p, 1.5 px a dp: the stock
		// art's silhouette sits 6.5625 dp inside the glow column, the title
		// starts at the slot's foot, and its outline is eight copies extruded
		// 1 dp and composited once at 0.85, behind the fill. modal.enter brings
		// the scrim, glow and frame in over 200 ms and shows the contents at its
		// end; modal.leave hides them at once and closes the modal 300 ms later.
		// This host cannot soften the screen, so the scrim form stands in.
		{
			Runtime::EventEffects shown;
			Check(runtime.RunEvent("exitModalShow",14,shown,error),"the exit confirmation opens");
			runtime.Frame(viewport,14.1);
			const auto scrim = runtime.PresentedValue("exitModal-scrim","background-color");
			const auto frameIn = runtime.PresentedValue("exitModal-frame","opacity");
			const auto waiting = runtime.PresentedValue("exitModal-contents","display");
			Check(scrim && Near(static_cast<float>(scrim->data[3]),.47f,.02f) && frameIn && Near(static_cast<float>(frameIn->data[0]),.5f,.02f) &&
				waiting && waiting->text == "none","half way in, the scrim and frame rise while the contents wait");
			const auto fallbackFocus = runtime.PresentedValue("exitModal-softfocus","display");
			const auto column = runtime.PresentedValue("exitModal-glow","display");
			const auto cut = runtime.PresentedValue("exitModal-glow-soft","display");
			Check(fallbackFocus && fallbackFocus->text == "none" && column && column->text == "block" && cut && cut->text == "none" &&
				host.softened.empty() && runtime.Statistics().backdropFallbacks == 0,
				"without soft focus the scrim and the stock glow column stand in, and no backdrop pass runs");
			Check(runtime.FocusedControl().empty(),"focus waits for the contents");
			host.draws.clear(); host.compositeOpacities.clear();
			runtime.Frame(viewport,14.25);
			const auto appeared = runtime.PresentedValue("exitModal-contents","display");
			Check(appeared && appeared->text == "block" && runtime.FocusedControl() == "exitModal_no",
				"the contents appear together at 200 ms and NO takes focus");
			const auto dimmed = runtime.PresentedValue("wordmark","image-color");
			Check(dimmed && Near(static_cast<float>(dimmed->data[0]),.4f,.01f) && Near(static_cast<float>(dimmed->data[3]),1,.001f),
				"the Exit modal dims the wordmark to 40% gray");
			Bounds dialog, title, outline, left, below, body;
			Check(runtime.GetBounds("exitModal-dialog",dialog) && runtime.GetBounds("exitModal-title",title) &&
				runtime.GetBounds("exitModal-title-outline",outline) && runtime.GetBounds("exitModal-title-outline-1",left) &&
				runtime.GetBounds("exitModal-title-outline-4",below) && runtime.GetBounds("exitModal-body",body),"the confirmation is laid out");
			Check(Near(dialog.x,240+240*1.5f) && Near(dialog.width,480*1.5f),"the dialog is the stock 320 u rect");
			Check(Near(title.x-dialog.x,30.125f*1.5f) && Near(title.y-dialog.y,-4*1.5f),"the title hangs from the slot's foot");
			Check(Near(left.x-title.x,-1.5f,.01f) && Near(left.y-title.y,0,.01f) && Near(below.y-title.y,1.5f,.01f),
				"the outline copies extrude 1 dp");
			Check(outline.x <= left.x && outline.y <= title.y-1.5f && outline.x+outline.width >= title.x+title.width+1.5f,
				"the outline group encloses its copies, since its composite is clipped to it");
			Check(Near(body.y-dialog.y,71*1.5f) && Near(body.x-dialog.x,33*1.5f),"the body sits where the stock body does");
			Check(std::any_of(host.compositeOpacities.begin(),host.compositeOpacities.end(),[](float value) { return Near(value,.85f,.001f); }),
				"the outline composites once at 0.85");
			// Vector fills arrive as pixel coverage spans: the first fully covered
			// column and row start at the next pixel boundary past each edge.
			float silhouetteLeft = 1e9f, silhouetteTop = 1e9f;
			for (const auto& draw : host.draws) for (const auto& vertex : draw.vertices)
				if (!draw.material && vertex.r == 0 && vertex.g == 0 && vertex.b == 0 && Near(vertex.a,.7f,.005f) &&
					vertex.x >= dialog.x-1 && vertex.x <= dialog.x+dialog.width+1 && vertex.y >= dialog.y-1 && vertex.y <= dialog.y+dialog.height+1) {
					silhouetteLeft = std::min(silhouetteLeft,vertex.x); silhouetteTop = std::min(silhouetteTop,vertex.y);
				}
			Check(Near(silhouetteLeft,std::ceil(dialog.x+480*7/512.f*1.5f),.01f) && Near(silhouetteTop,std::ceil(dialog.y+3.5625f*1.5f),.01f),
				"the silhouette leaves the 6 dp lit margin and its raised top line");
			Runtime::EventEffects hidden;
			Check(runtime.RunEvent("exitModalHide",14.3,hidden,error),"the exit confirmation closes");
			runtime.Frame(viewport,14.32);
			const auto held = runtime.PresentedValue("exitModal-scrim","background-color");
			const auto gone = runtime.PresentedValue("exitModal-contents","display");
			const auto open = runtime.PresentedValue("exitModal","display");
			Check(gone && gone->text == "none" && open && open->text == "block" && held && Near(static_cast<float>(held->data[3]),.94f,.01f),
				"leaving hides the contents at once and holds the scrim for 50 ms");
			runtime.Frame(viewport,14.56);
			const auto frameOut = runtime.PresentedValue("exitModal-frame","opacity");
			const auto stillOpen = runtime.PresentedValue("exitModal","display");
			Check(frameOut && Near(static_cast<float>(frameOut->data[0]),0,.001f) && stillOpen && stillOpen->text == "block",
				"Exit releases its frame over 200 ms while the scrim is still going");
			const auto restoredMark = runtime.PresentedValue("wordmark","image-color");
			Check(restoredMark && Near(static_cast<float>(restoredMark->data[0]),1,.001f),"the wordmark is restored from 50 ms over 150 ms");
			runtime.Frame(viewport,14.61);
			const auto closed = runtime.PresentedValue("exitModal","display");
			Check(closed && closed->text == "none" && runtime.FocusedControl() != "exitModal_no","the modal closes when the scrim is gone");
			// A Hide just after enter ended (with no frame between) runs enter's
			// completion first, so the contents stay hidden. A Show while leaving
			// then takes over the leave, which never completes.
			Check(runtime.RunEvent("exitModalShow",15,shown,error) && runtime.RunEvent("exitModalHide",15.25,hidden,error),"hide after enter ended");
			runtime.Frame(viewport,15.27);
			const auto ordered = runtime.PresentedValue("exitModal-contents","display");
			Check(ordered && ordered->text == "none" && hidden.stateChanges.contains("exitModal.contents") &&
				!std::get<bool>(hidden.stateChanges.at("exitModal.contents")),"a completion due before an event runs before its program");
			Check(runtime.RunEvent("exitModalShow",15.4,shown,error),"reopen while leaving");
			runtime.Frame(viewport,15.7);
			const auto reopened = runtime.PresentedValue("exitModal","display");
			const auto restored = runtime.PresentedValue("exitModal-contents","display");
			Check(reopened && reopened->text == "block" && restored && restored->text == "block","a reopened modal stays open");
			Check(runtime.RunEvent("exitModalHide",16,hidden,error),"close again");
			runtime.Frame(viewport,16.4);
		}
		// Soft focus (REN-016): where the renderer softens the screen, the modal
		// blurs it 5 u (7.5 dp, 11.25 px at 1080p) at 0.80 saturation without
		// dimming it, ramping with modal.enter and released after leave's 50 ms
		// hold; the scrim and the stock column give way to the glow cut to the
		// dialog, whose side fade is the screen's second mask.
		{
			host.softFocus = true;
			Runtime::EventEffects shown, hidden;
			Check(runtime.RunEvent("exitModalShow",16.42,shown,error),"the exit confirmation opens over soft focus");
			host.softened.clear();
			runtime.Frame(viewport,16.52);
			const auto blur = runtime.PresentedValue("exitModal-softfocus","backdrop-blur");
			const auto saturate = runtime.PresentedValue("exitModal-softfocus","backdrop-saturate");
			Check(blur && Near(static_cast<float>(blur->data[0]),3.75f,.05f) && saturate && Near(static_cast<float>(saturate->data[0]),.9f,.005f),
				"half way in, the soft focus is at half strength");
			const auto focus = runtime.PresentedValue("exitModal-softfocus","display");
			const auto scrim = runtime.PresentedValue("exitModal-scrim","display");
			const auto column = runtime.PresentedValue("exitModal-glow","display");
			const auto cut = runtime.PresentedValue("exitModal-glow-soft","display");
			Check(focus && focus->text == "block" && scrim && scrim->text == "none" && column && column->text == "none" && cut && cut->text == "block",
				"soft focus replaces the scrim and the stock glow column");
			Check(host.softened.size() == 1 && Near(host.softened[0].sigma,3.75f*1.5f,.05f) && Near(host.softened[0].saturation,.9f,.005f),
				"the host softens the screen once a frame, the sigma in view pixels");
			const auto& region = host.softened[0].region;
			Check(region.x <= 0 && region.y <= 0 && region.x+region.width >= 1920 && region.y+region.height >= 1080,
				"the whole view beneath the modal is softened");
			Check(runtime.Statistics().backdropComposites == 1 && runtime.Statistics().backdropFallbacks == 0,"the backdrop pass is counted");
			runtime.Frame(viewport,16.64);
			Check(host.softened.size() == 2 && Near(host.softened[1].sigma,11.25f,.01f) && Near(host.softened[1].saturation,.8f,.001f),
				"modal.enter ends at a 7.5 dp blur and 0.80 saturation");
			Check(runtime.Statistics().maskApplications == 2,"the glow's side fade masks it, beside the emblem glint");
			Check(runtime.RunEvent("exitModalHide",16.65,hidden,error),"the exit confirmation closes");
			runtime.Frame(viewport,16.67);
			Check(host.softened.size() == 3 && Near(host.softened[2].sigma,11.25f,.01f),"leave holds the soft focus for 50 ms");
			runtime.Frame(viewport,16.825);
			Check(host.softened.size() == 4 && Near(host.softened[3].sigma,11.25f/2,.05f) && Near(host.softened[3].saturation,.9f,.005f),
				"and releases it over 250 ms");
			runtime.Frame(viewport,16.96);
			const auto closed = runtime.PresentedValue("exitModal","display");
			Check(closed && closed->text == "none" && host.softened.size() == 4 && runtime.Statistics().backdropComposites == 0,
				"a closed modal softens nothing");
			host.softFocus = false;
		}
		// content.out (section 8): departing home plates fade over 250 ms, but
		// the plinth and its secondary links take 50 ms; content.in brings
		// them back together over 150 ms after the bands return.
		{
			Check(runtime.PlayTimeline("depart",17),"depart toward a page");
			runtime.Frame(viewport,17.05);
			const auto plinth = runtime.PresentedValue("plinth","opacity");
			const auto homeOut = runtime.PresentedValue("home","opacity");
			Check(plinth && Near(static_cast<float>(plinth->data[0]),0,.001f) && homeOut && Near(static_cast<float>(homeOut->data[0]),.8f,.01f),
				"the plinth is gone at 50 ms while the home plates are still fading");
			Check(runtime.PlayTimeline("returnHome",18),"return home");
			runtime.Frame(viewport,18.7);
			const auto plinthBack = runtime.PresentedValue("plinth","opacity");
			const auto homeBack = runtime.PresentedValue("home","opacity");
			Check(plinthBack && Near(static_cast<float>(plinthBack->data[0]),1,.001f) && homeBack && Near(static_cast<float>(homeBack->data[0]),1,.001f),
				"the plinth returns with the home content");
		}
	}
	// Pause: the level block binds the mission, difficulty, objectives and shot.
	{
		const auto source = Read(argv[2]);
		Document document; std::vector<Diagnostic> diagnostics;
		const bool valid = document.Load(source,diagnostics);
		for (const auto& diagnostic : diagnostics) std::fprintf(stderr,"pause %s: %s\n",diagnostic.pointer.c_str(),diagnostic.message.c_str());
		Check(valid && document.Model().id == "openq4.pause","pause document validates");
		CheckSessionActions(document);
		Runtime runtime(host);
		Check(runtime.Initialize() && runtime.LoadDocument(source,"guis/menu/pause.q4ui",diagnostics),"pause loads into a runtime");
		std::string error;
		Check(runtime.SetState({{"pause_level",std::string("Air Defense Trenches")},{"pause_shot",std::string("gfx/guis/loadscreens/airdefense2")}},error,1),
			"publish the level block");
		Viewport viewport; viewport.canvasHeight = 720;
		host.materials.clear();
		runtime.Frame(viewport,1.2);
		Check(std::find(host.materials.begin(),host.materials.end(),"gfx/guis/loadscreens/airdefense2") != host.materials.end(),"the level block shows the levelshot");
		const auto hidden = runtime.PresentedValue("level-objectives-head","display");
		Check(hidden && hidden->text == "none","a map without objectives shows no objectives heading");
		Check(runtime.SetState({{"pause_objectives",std::string("Reach the anti-aircraft battery.")}},error,1.3),"publish objectives");
		runtime.Frame(viewport,1.4);
		const auto shown = runtime.PresentedValue("level-objectives-head","display");
		Check(shown && shown->text == "block","objectives bring their heading");
		// The objectives the game publishes take the summary's place, a row
		// each, with the time in the mission under them (section 13.7).
		const auto stillHidden = runtime.PresentedValue("level-stats-rule","display");
		Check(stillHidden && stillHidden->text == "none","no time line before the game publishes one");
		Check(runtime.SetState({{"pause_objective_count",2.0},{"pause_objective_0",std::string("Destroy the anti-aircraft battery")},
			{"pause_objective_1",std::string("Reach the bunker")},{"pause_stats",std::string("0:42:10 in mission")}},error,1.5),
			"publish the open objectives and the time in the mission");
		runtime.Frame(viewport,1.6);
		const auto first = runtime.PresentedValue("level-objective-0","display");
		const auto second = runtime.PresentedValue("level-objective-1","display");
		const auto third = runtime.PresentedValue("level-objective-2","display");
		const auto summary = runtime.PresentedValue("level-objectives","display");
		const auto firstText = runtime.PresentedValue("level-objective-0-text","text");
		Check(first && first->text == "block" && second && second->text == "block" && third && third->text == "none",
			"one row for each open objective");
		Check(summary && summary->text == "none" && firstText && firstText->text == "Destroy the anti-aircraft battery",
			"the open objectives replace the map's summary, newest first");
		const auto stats = runtime.PresentedValue("level-stats","text");
		const auto rule = runtime.PresentedValue("level-stats-rule","display");
		Check(stats && stats->text == "0:42:10 in mission" && rule && rule->text == "block","the time in the mission shows under a rule");
		ActionInvocation invocation;
		Check(runtime.ResolveAction("resume",invocation,error) && std::get<std::string>(invocation.arguments.at("command")) == "resume","RESUME returns to the game");
		// SAVE GAME's label carries from its row at 212.2 u into the title slot.
		Runtime::EventEffects carry;
		Check(runtime.RunEvent("carry_saveGame",2,carry,error),"a pause page hand-off carries its label");
		runtime.Frame(viewport,2.002);
		const auto begin = runtime.PresentedValue("title-carry","transform");
		const auto carried = runtime.PresentedValue("title-carry","text");
		Check(begin && Near(static_cast<float>(begin->data[1]),(212.2f+2.8f-19)*1.5f,.2f) && carried && carried->text == "#str_200003",
			"SAVE GAME starts on its row");
		// The paused view (sections 9 and 13.7) at 1280x720, a pixel a dp:
		// without soft focus the darkening scrim stands in; with it the view
		// is softened by modal.softfocus, never dimmed, ramping in with
		// menu.fade, and the quit modal softens the pause screen above it.
		{
			runtime.Frame(viewport,2.5);
			const auto dimmed = runtime.PresentedValue("scrim","display");
			const auto plain = runtime.PresentedValue("scene-softfocus","display");
			Check(dimmed && dimmed->text == "block" && plain && plain->text == "none" && runtime.Statistics().backdropComposites == 0,
				"without soft focus the darkening scrim stands in for the softened view");
			host.softFocus = true;
			Check(runtime.PlayTimeline("open",3),"the pause fades in");
			host.softened.clear();
			runtime.Frame(viewport,3.125);
			const auto blur = runtime.PresentedValue("scene-softfocus","backdrop-blur");
			const auto scrim = runtime.PresentedValue("scrim","display");
			Check(blur && Near(static_cast<float>(blur->data[0]),3.75f,.05f) && scrim && scrim->text == "none",
				"the softening ramps in with menu.fade and replaces the darkening scrim");
			Check(host.softened.size() == 1 && Near(host.softened[0].sigma,3.75f,.05f) && Near(host.softened[0].saturation,.9f,.005f) &&
				host.softened[0].region.x <= 0 && host.softened[0].region.x+host.softened[0].region.width >= 1280,
				"the whole paused view is softened");
			runtime.Frame(viewport,3.4);
			Check(host.softened.size() == 2 && Near(host.softened[1].sigma,7.5f,.01f) && Near(host.softened[1].saturation,.8f,.001f),
				"at rest the paused view stays in modal.softfocus");
			Runtime::EventEffects quit;
			Check(runtime.RunEvent("quitModalShow",3.5,quit,error),"the quit confirmation opens");
			runtime.Frame(viewport,3.8);
			Check(host.softened.size() == 4 && Near(host.softened[2].sigma,7.5f,.01f) && Near(host.softened[3].sigma,7.5f,.01f) &&
				runtime.Statistics().backdropComposites == 2,"the quit modal softens the pause screen above the softened view");
			Check(runtime.RunEvent("quitModalHide",3.9,quit,error),"the quit confirmation closes");
			runtime.Frame(viewport,4.3);
			// The pause document outlives each pause: a page's return keeps the
			// view softened, and the next pause ramps in from nothing again.
			Check(runtime.PlayTimeline("returnHome",4.4),"a page returns home");
			runtime.Frame(viewport,4.5);
			const auto kept = runtime.PresentedValue("scene-softfocus","backdrop-blur");
			Check(kept && Near(static_cast<float>(kept->data[0]),7.5f,.01f),"returning from a page keeps the softened view");
			Check(runtime.PlayTimeline("open",5),"the game pauses again");
			runtime.Frame(viewport,5.125);
			const auto again = runtime.PresentedValue("scene-softfocus","backdrop-blur");
			Check(again && Near(static_cast<float>(again->data[0]),3.75f,.05f),"each pause ramps the softening in from nothing");
			// Returning to the game hides the screen at once (section 8) and
			// releases the softened view over 250 ms, as the modal backdrop
			// does (section 4).
			runtime.Frame(viewport,5.5);
			Runtime::EventEffects release;
			Check(runtime.RunEvent("release",5.6,release,error),"the game resumes");
			host.softened.clear();
			runtime.Frame(viewport,5.6);
			const auto closed = runtime.PresentedValue("chrome","display");
			Check(closed && closed->text == "none" && host.softened.size() == 1 && Near(host.softened[0].sigma,7.5f,.01f) &&
				runtime.Statistics().backdropComposites == 1,"the screen closes at once over the still-softened view");
			runtime.Frame(viewport,5.725);
			const auto releasing = runtime.PresentedValue("scene-softfocus","backdrop-blur");
			const auto resaturating = runtime.PresentedValue("scene-softfocus","backdrop-saturate");
			Check(releasing && Near(static_cast<float>(releasing->data[0]),3.75f,.05f) && resaturating &&
				Near(static_cast<float>(resaturating->data[0]),.9f,.005f),"the softened view releases over 250 ms");
			runtime.Frame(viewport,5.9);
			const auto clear = runtime.PresentedValue("scene-softfocus","backdrop-blur");
			const auto saturated = runtime.PresentedValue("scene-softfocus","backdrop-saturate");
			Check(clear && Near(static_cast<float>(clear->data[0]),0,.001f) && saturated && Near(static_cast<float>(saturated->data[0]),1,.001f),
				"and is clear by 250 ms");
			// Without soft focus the scrim standing in for it fades out instead,
			// and each pause opens with its screen and scrim again.
			host.softFocus = false;
			Check(runtime.RunEvent("open",6,release,error),"the game pauses again");
			runtime.Frame(viewport,6.01);
			const auto reopened = runtime.PresentedValue("chrome","display");
			const auto scrimBack = runtime.PresentedValue("scrim","opacity");
			Check(reopened && reopened->text == "block" && scrimBack && Near(static_cast<float>(scrimBack->data[0]),1,.001f),
				"every pause opens with its screen");
			Check(runtime.RunEvent("release",6.5,release,error),"the game resumes without soft focus");
			runtime.Frame(viewport,6.625);
			const auto fading = runtime.PresentedValue("scrim","opacity");
			Check(fading && Near(static_cast<float>(fading->data[0]),.5f,.01f),"the scrim fades out over 250 ms");
			runtime.Frame(viewport,6.8);
			const auto gone = runtime.PresentedValue("scrim","opacity");
			Check(gone && Near(static_cast<float>(gone->data[0]),0,.001f),"and is gone by 250 ms");
			Check(runtime.RunEvent("open",7,release,error),"the game pauses once more");
			runtime.Frame(viewport,7.3);
			const auto restored = runtime.PresentedValue("scrim","opacity");
			const auto screen = runtime.PresentedValue("chrome","display");
			Check(restored && Near(static_cast<float>(restored->data[0]),1,.001f) && screen && screen->text == "block",
				"the scrim and screen return with the pause");
			// The pause also comes back through returnHome (a page left with Back
			// before the legacy menu reached home): activation shows the screen
			// and ramps the softened view back in.
			host.softFocus = true;
			Check(runtime.RunEvent("release",7.5,release,error),"the game resumes from a page's return");
			runtime.Frame(viewport,7.8);
			Check(runtime.RunEvent("onActivate",8,release,error) && runtime.PlayTimeline("returnHome",8),"the pause returns through returnHome");
			runtime.Frame(viewport,8.01);
			const auto back = runtime.PresentedValue("chrome","display");
			const auto backScrim = runtime.PresentedValue("scrim","opacity");
			Check(back && back->text == "block" && backScrim && Near(static_cast<float>(backScrim->data[0]),1,.001f),
				"a pause activated after a release shows its screen");
			runtime.Frame(viewport,8.3);
			const auto resoftened = runtime.PresentedValue("scene-softfocus","backdrop-blur");
			Check(resoftened && Near(static_cast<float>(resoftened->data[0]),7.5f,.01f),"and softens the view again");
			// An activation that follows no release changes nothing.
			Check(runtime.RunEvent("onActivate",8.4,release,error),"the pause activates again");
			runtime.Frame(viewport,8.5);
			const auto steady = runtime.PresentedValue("scene-softfocus","backdrop-blur");
			Check(steady && Near(static_cast<float>(steady->data[0]),7.5f,.01f),"without a release the softened view stays");
			host.softFocus = false;
		}
		// OBJECTIVES (sections 13.7 and 14.11) is a page of the pause: it docks
		// the bands and carries its label, then the stock entry motion shows
		// every open objective, newest first, with its description and
		// screenshot, and the completed ones under COMPLETED. Back fades the
		// page and closes it when the bands are home.
		{
			const auto objectivesRow = runtime.PresentedValue("nav_objectives-label","text");
			Check(objectivesRow && objectivesRow->text == "#str_200380","OBJECTIVES is the fifth action");
			Bounds restartRow, objectivesBox;
			Check(runtime.GetBounds("nav_restart-label",restartRow) && runtime.GetBounds("nav_objectives-label",objectivesBox) &&
				Near(objectivesBox.y-restartRow.y,45),"OBJECTIVES follows RESTART LEVEL on the 30 u pitch");
			std::string longText; for (int word = 0; word < 120; ++word) longText += "squad ";
			Check(runtime.SetState({{"pause_objective_count",3.0},{"pause_objective_0",std::string("Destroy the battery")},
				{"pause_objective_text_0",std::string("Strogg forces hold the hangar.")},
				{"pause_objective_shot_0",std::string("gfx/objectives/airdefense_obj_1")},
				{"pause_objective_1",std::string("Reach the bunker")},{"pause_objective_text_1",longText},
				{"pause_objective_2",std::string("Regroup with Rhino squad")},
				{"pause_completed_count",1.0},{"pause_completed_0",std::string("Retrieve the medic")}},error,10),
				"publish the objectives page");
			Runtime::EventEffects page;
			host.materials.clear();
			Check(runtime.RunEvent("objectivesShow",10.1,page,error),"OBJECTIVES opens its page");
			runtime.Frame(viewport,10.2);
			const auto open = runtime.PresentedValue("objectives","display");
			const auto waiting = runtime.PresentedValue("objectives-content","opacity");
			const auto carried = runtime.PresentedValue("title-carry","text");
			const auto docking = runtime.PresentedValue("band-top","transform");
			Check(open && open->text == "block" && waiting && Near(static_cast<float>(waiting->data[0]),0,.001f) &&
				carried && carried->text == "#str_200380" && docking && docking->data[0] > 1,
				"the bands dock and OBJECTIVES carries before the page appears");
			runtime.Frame(viewport,11.0);
			const auto shown = runtime.PresentedValue("objectives-content","opacity");
			const auto barIn = runtime.PresentedValue("objectives-bar","transform");
			const auto prompts = runtime.PresentedValue("prompts","opacity");
			Check(shown && Near(static_cast<float>(shown->data[0]),1,.001f) && barIn && Near(static_cast<float>(barIn->data[0]),0,.01f) &&
				prompts && Near(static_cast<float>(prompts->data[0]),0,.001f),"by 900 ms the page is in with its back bar, and the prompts give way");
			const auto first = runtime.PresentedValue("objectives-entry-0","display");
			const auto third = runtime.PresentedValue("objectives-entry-2","display");
			const auto fourth = runtime.PresentedValue("objectives-entry-3","display");
			const auto empty = runtime.PresentedValue("objectives-empty","display");
			const auto done = runtime.PresentedValue("objectives-done-0","display");
			const auto notDone = runtime.PresentedValue("objectives-done-1","display");
			const auto count = runtime.PresentedValue("objectives-completed-count","text");
			Check(first && first->text == "block" && third && third->text == "block" && fourth && fourth->text == "none" &&
				empty && empty->text == "none" && done && done->text == "block" && notDone && notDone->text == "none" && count && count->text == "1",
				"a plate for each open objective and a row for each completed one");
			const auto title = runtime.PresentedValue("objectives-entry-0-title","text");
			const auto text = runtime.PresentedValue("objectives-entry-0-text","text");
			Check(title && title->text == "Destroy the battery" && text && text->text == "Strogg forces hold the hangar.","the plates carry each objective's title and description");
			Bounds titleBox;
			Check(runtime.GetBounds("objectives-entry-0-title",titleBox) && Near(titleBox.width,308*1.5f,1),"a title wraps at the stock 308 u");
			Check(std::find(host.materials.begin(),host.materials.end(),"gfx/objectives/airdefense_obj_1") != host.materials.end(),
				"the plates show each objective's screenshot");
			// Descriptions wrap without a limit, so a long one grows its plate.
			Bounds shortPlate, longPlate, frame;
			Check(runtime.GetBounds("objectives-entry-0",shortPlate) && runtime.GetBounds("objectives-entry-1",longPlate) &&
				runtime.GetBounds("objectives-entry-1-frame",frame) && Near(shortPlate.height,132*1.5f,1) &&
				longPlate.height > shortPlate.height+30 && Near(frame.height,longPlate.height,1),"a long description grows its plate and frame");
			// The list scrolls: the bar holds focus, and the down input moves it.
			Check(runtime.FocusedControl() == "objectives_scroll","the page opens with its list's scrollbar in focus");
			const auto before = runtime.GetWidgetState("objectives_scroll");
			Check(before && before->scroll && before->scroll->geometry.usable && before->scroll->geometry.range > 0,"the list overflows and can scroll");
			runtime.MenuAction(MenuInput::Down,true,11.1); runtime.MenuAction(MenuInput::Down,false,11.12);
			runtime.Frame(viewport,11.2);
			const auto after = runtime.GetWidgetState("objectives_scroll");
			Check(after && after->scroll && after->scroll->geometry.offset > before->scroll->geometry.offset,"the down input scrolls the list");
			// A snapshot restored with the page open keeps its scroll: the restored
			// page is open already, not newly opened.
			{
				std::string saved; std::vector<Diagnostic> restoredDiagnostics;
				Check(runtime.SaveSnapshot(saved,error,11.2),"save the open Objectives page");
				Runtime restored(host);
				Check(restored.Initialize() && restored.LoadDocument(source,"guis/menu/pause.q4ui",restoredDiagnostics) &&
					restored.RestoreSnapshot(saved,error,11.2),"restore it into a fresh runtime");
				restored.Frame(viewport,11.21); restored.Frame(viewport,11.22);
				const auto kept = restored.GetWidgetState("objectives_scroll");
				Check(kept && kept->scroll && Near(static_cast<float>(kept->scroll->geometry.offset),static_cast<float>(after->scroll->geometry.offset),.5f),
					"a restored page keeps its scroll");
			}
			// Back: the page fades, the bands come home, and the page closes.
			Check(runtime.RunEvent("objectivesHide",12,page,error),"Back leaves the page");
			runtime.Frame(viewport,12.2);
			const auto fading = runtime.PresentedValue("objectives-content","opacity");
			const auto still = runtime.PresentedValue("objectives","display");
			Check(fading && Near(static_cast<float>(fading->data[0]),0,.001f) && still && still->text == "block","the page fades while the bands return");
			Check(runtime.RunEvent("objectivesHide",12.3,page,error),"a second Back during the leave");
			runtime.Frame(viewport,12.8);
			const auto closed = runtime.PresentedValue("objectives","display");
			const auto back = runtime.PresentedValue("prompts","opacity");
			Check(closed && closed->text == "none" && back && Near(static_cast<float>(back->data[0]),1,.001f) &&
				runtime.FocusedControl() != "objectives_scroll","the page closes with the bands home and the prompts back, the second Back ignored");
			// Reopened, the list starts at its first entry again.
			Check(runtime.RunEvent("objectivesShow",12.9,page,error),"OBJECTIVES opens again");
			runtime.Frame(viewport,13.8);
			const auto reopened = runtime.GetWidgetState("objectives_scroll");
			Check(reopened && reopened->scroll && Near(static_cast<float>(reopened->scroll->geometry.offset),0,.01f),"a reopened page starts at the top of its list");
			// A pause that closed without Back (a console load) opens at home
			// without the page, its prompts showing.
			Check(runtime.RunEvent("open",14,page,error),"the game pauses again");
			runtime.Frame(viewport,14.3);
			const auto reset = runtime.PresentedValue("objectives","display");
			const auto resetBar = runtime.PresentedValue("objectives-bar","display");
			const auto resetPrompts = runtime.PresentedValue("prompts","opacity");
			Check(reset && reset->text == "none" && resetBar && resetBar->text == "none" && resetPrompts &&
				Near(static_cast<float>(resetPrompts->data[0]),1,.001f) && runtime.FocusedControl() != "objectives_scroll",
				"every pause opens without the Objectives page");
			// No open objective: the stock static screenshot and line in one plate.
			Check(runtime.SetState({{"pause_objective_count",0.0},{"pause_completed_count",0.0}},error,14.5),"no objectives");
			host.materials.clear();
			Check(runtime.RunEvent("objectivesShow",14.6,page,error),"OBJECTIVES opens on an empty list");
			runtime.Frame(viewport,15.5);
			const auto none = runtime.PresentedValue("objectives-empty","display");
			const auto noneDone = runtime.PresentedValue("objectives-completed","display");
			Bounds noneText;
			Check(none && none->text == "block" && noneDone && noneDone->text == "none" &&
				std::find(host.materials.begin(),host.materials.end(),"gfx/objectives/none") != host.materials.end() &&
				runtime.GetBounds("objectives-empty-text",noneText) && Near(noneText.width,164*1.5f,1),
				"without objectives the page shows the stock static and line");
			// The level block lists the objectives with their state: the open ones,
			// then the completed ones behind a check at 0.5.
			Check(runtime.SetState({{"pause_objective_count",1.0},{"pause_objective_0",std::string("Escort Anderson")},
				{"pause_completed_count",2.0},{"pause_completed_0",std::string("Retrieve the medic")},
				{"pause_completed_1",std::string("Regroup")}},error,16),"one open and two completed objectives");
			runtime.Frame(viewport,16.1);
			const auto openRow = runtime.PresentedValue("level-objective-0-text","text");
			const auto openMark = runtime.PresentedValue("level-objective-0-mark","display");
			const auto doneRow = runtime.PresentedValue("level-objective-1-text","text");
			const auto doneCheck = runtime.PresentedValue("level-objective-1-check","display");
			const auto doneMark = runtime.PresentedValue("level-objective-1-mark","display");
			const auto doneColour = runtime.PresentedValue("level-objective-1-text","color");
			const auto lastRow = runtime.PresentedValue("level-objective-2-text","text");
			Check(openRow && openRow->text == "Escort Anderson" && openMark && openMark->text == "block" &&
				doneRow && doneRow->text == "Retrieve the medic" && doneCheck && doneCheck->text == "block" && doneMark && doneMark->text == "none" &&
				doneColour && Near(static_cast<float>(doneColour->data[3]),.5f,.001f) && lastRow && lastRow->text == "Regroup",
				"the level block lists the open objective, then the completed ones behind a check");
		}
	}
	// Strogg pause (section 13.7): the Marine pause's level block and verbs in
	// the Strogg family, every label arriving in runes and translating.
	{
		const auto source = Read(argv[4]);
		Document document; std::vector<Diagnostic> diagnostics;
		const bool valid = document.Load(source,diagnostics);
		for (const auto& diagnostic : diagnostics) std::fprintf(stderr,"strogg pause %s: %s\n",diagnostic.pointer.c_str(),diagnostic.message.c_str());
		Check(valid && document.Model().id == "openq4.pause_strogg","the Strogg pause validates");
		CheckSessionActions(document);
		Runtime runtime(host);
		Check(runtime.Initialize() && runtime.LoadDocument(source,"guis/menu/pause_strogg.q4ui",diagnostics),"the Strogg pause loads into a runtime");
		std::string error;
		Check(runtime.SetState({{"pause_level",std::string("Strogg Medical Facilities")},{"pause_shot",std::string("gfx/guis/loadscreens/medlabs")},
			{"pause_objective_count",1.0},{"pause_objective_0",std::string("Escape the medical facility")},
			{"pause_stats",std::string("0:18:40 in mission")}},error,1),"publish the level block");
		Viewport viewport; viewport.canvasHeight = 720;
		host.materials.clear();
		runtime.Frame(viewport,1.1);
		const auto face = runtime.PresentedValue("nav_resume-label","font-family");
		const auto runeFace = runtime.PresentedValue("nav_resume-rune","font-family");
		Check(face && face->text == "r_strogg" && runeFace && runeFace->text == "strogg","labels are R_Strogg over a rune copy");
		const auto rowRunes = runtime.PresentedValue("level-objective-0-text-rune","text");
		const auto nameRunes = runtime.PresentedValue("level-name-rune","text");
		Check(rowRunes && rowRunes->text == "Escape the medical facility" && nameRunes && nameRunes->text == "Strogg Medical Facilities",
			"the rune copies follow the published lines");
		Check(std::find(host.materials.begin(),host.materials.end(),"gfx/guis/loadscreens/medlabs") != host.materials.end(),
			"the level block shows the levelshot");
		Check(std::find(host.materials.begin(),host.materials.end(),"q4-add/gfx/guis/hud/s_static") != host.materials.end(),
			"the level block adds the Strogg HUD's grain");
		// The label's wrapper fits the label, so the scan bar's head rests
		// 12 u past it whatever the language: the test face advances 0.6 of
		// the 24 dp size per glyph, and labels read "Label".
		Bounds fit, labelBox, bar;
		Check(runtime.GetBounds("nav_resume-fit",fit) && runtime.GetBounds("nav_resume-label",labelBox) &&
			runtime.GetBounds("nav_resume-scan",bar),"the Strogg plate is laid out");
		Check(Near(labelBox.width,5*.6f*24) && Near(fit.width,labelBox.width+26*1.5f) && Near(bar.x,fit.x) && Near(bar.width,fit.width),
			"the wrapper fits the label and the scan bar spans it");
		Check(Near(labelBox.x,160+66),"Strogg labels sit at 44 u like the Marine ones");
		// Opening: the actions translate 120 + 45 ms per row apart over 200 ms,
		// EXIT after them (390 ms), GAME PAUSED from 60 ms over 500 ms under
		// the scan bar, arriving white, and the level block's lines last (435 ms).
		Check(runtime.HasEvent("open") && runtime.HasEvent("returnHome"),"opening and returning play the translation");
		Runtime::EventEffects open;
		Check(runtime.RunEvent("open",2,open,error),"the Strogg pause opens");
		runtime.Frame(viewport,2.05);
		const auto resumeIn = runtime.PresentedValue("nav_resume-latin","opacity");
		const auto resumeRunes = runtime.PresentedValue("nav_resume-rune","color");
		Check(resumeIn && Near(static_cast<float>(resumeIn->data[0]),0,.001f) && resumeRunes && Near(static_cast<float>(resumeRunes->data[3]),.8f,.001f),
			"RESUME arrives in runes");
		runtime.Frame(viewport,2.33);
		const auto resumeDone = runtime.PresentedValue("nav_resume-latin","opacity");
		const auto resumeGone = runtime.PresentedValue("nav_resume-rune","color");
		const auto quitWaits = runtime.PresentedValue("nav_quit-latin","opacity");
		const auto heading = runtime.PresentedValue("level-heading","color");
		Check(resumeDone && Near(static_cast<float>(resumeDone->data[0]),1,.001f) && resumeGone && Near(static_cast<float>(resumeGone->data[3]),0,.001f),
			"RESUME has translated by 320 ms");
		const auto exitWaits = runtime.PresentedValue("link_exit-latin","opacity");
		Check(quitWaits && Near(static_cast<float>(quitWaits->data[0]),0,.001f) && heading && Near(static_cast<float>(heading->data[3]),0,.001f) &&
			exitWaits && Near(static_cast<float>(exitWaits->data[0]),0,.001f),"QUIT TO MENU, EXIT and the level block wait their turn");
		const auto titleMid = runtime.PresentedValue("paused-title","color");
		const auto scanMid = runtime.PresentedValue("paused-title-scan","opacity");
		Check(titleMid && Near(static_cast<float>(titleMid->data[0]),1,.001f) && Near(static_cast<float>(titleMid->data[3]),.54f,.02f) &&
			scanMid && Near(static_cast<float>(scanMid->data[0]),.46f,.02f),"GAME PAUSED fades in white while the scan bar dims");
		runtime.Frame(viewport,3.2);
		const auto titleRest = runtime.PresentedValue("paused-title","color");
		const auto headingRest = runtime.PresentedValue("level-heading","color");
		const auto rowRest = runtime.PresentedValue("level-objective-0-text","color");
		const auto quitDone = runtime.PresentedValue("nav_quit-latin","opacity");
		Check(titleRest && Near(static_cast<float>(titleRest->data[1]),1,.001f) && Near(static_cast<float>(titleRest->data[2]),200/255.f,.002f) &&
			Near(static_cast<float>(titleRest->data[3]),1,.002f),"GAME PAUSED settles to #FCFFC8");
		const auto exitDone = runtime.PresentedValue("link_exit-latin","opacity");
		const auto exitRunes = runtime.PresentedValue("link_exit-rune","color");
		Check(exitDone && Near(static_cast<float>(exitDone->data[0]),1,.001f) && exitRunes && Near(static_cast<float>(exitRunes->data[3]),0,.001f),
			"EXIT has translated");
		Check(headingRest && Near(static_cast<float>(headingRest->data[3]),1,.001f) && rowRest && Near(static_cast<float>(rowRest->data[3]),1,.001f) &&
			quitDone && Near(static_cast<float>(quitDone->data[0]),1,.001f),"every line has translated by 1.2 s");
		// Focus runs the credits scan bar under the label: its head sweeps in
		// from the wrapper's leading edge over 300 ms, by its right inset, so
		// it crosses any label whole, and the bar dims over a second.
		Check(runtime.FocusControl("nav_savegame",4),"focus reaches a Strogg plate");
		runtime.Frame(viewport,4.002);
		Bounds parked, half, rest;
		Check(runtime.GetBounds("nav_savegame-fit",fit) && runtime.GetBounds("nav_savegame-scan",parked) &&
			parked.x+parked.width <= fit.x+2,"the bar's head starts at the label wrapper's leading edge");
		runtime.Frame(viewport,4.15);
		const auto sliding = runtime.PresentedValue("nav_savegame-scan","right");
		const auto lit = runtime.PresentedValue("nav_savegame-scan","opacity");
		Check(sliding && sliding->unit == "%" && sliding->data[0] > 1 && sliding->data[0] < 99 && lit && lit->data[0] > .8 &&
			runtime.GetBounds("nav_savegame-scan",half) && half.x+half.width > fit.x+2 && half.x+half.width < fit.x+fit.width-2,
			"the scan bar sweeps across the focused label");
		runtime.Frame(viewport,5.2);
		const auto rested = runtime.PresentedValue("nav_savegame-scan","right");
		const auto dimmed = runtime.PresentedValue("nav_savegame-scan","opacity");
		Check(rested && Near(static_cast<float>(rested->data[0]),0,.01f) && dimmed && Near(static_cast<float>(dimmed->data[0]),0,.001f) &&
			runtime.GetBounds("nav_savegame-scan",rest) && Near(rest.x+rest.width,fit.x+fit.width),
			"the bar rests 12 u past the label and dims away");
		const auto focusColour = runtime.PresentedValue("nav_savegame-label","color");
		Check(focusColour && Near(static_cast<float>(focusColour->data[0]),1,.001f) && Near(static_cast<float>(focusColour->data[1]),.8f,.002f) &&
			Near(static_cast<float>(focusColour->data[2]),0,.001f),"a focused label turns #FFCC00");
		// Reduced motion shows the translated labels at once.
		runtime.SetReducedMotion(true,6);
		Check(runtime.RunEvent("open",6,open,error),"the Strogg pause opens again with reduced motion");
		runtime.Frame(viewport,6.09);
		const auto quitAtOnce = runtime.PresentedValue("nav_quit-latin","opacity");
		const auto runesGone = runtime.PresentedValue("nav_quit-rune","color");
		const auto titleAtOnce = runtime.PresentedValue("paused-title","color");
		Check(quitAtOnce && Near(static_cast<float>(quitAtOnce->data[0]),1,.001f) && runesGone && Near(static_cast<float>(runesGone->data[3]),0,.001f) &&
			titleAtOnce && Near(static_cast<float>(titleAtOnce->data[3]),1,.002f),"reduced motion shows the translated labels at once");
		runtime.SetReducedMotion(false,6.1);
		// The paused view softens as the Marine pause's does.
		host.softFocus = true; host.softened.clear();
		Check(runtime.RunEvent("open",7,open,error),"the Strogg pause opens over the softened view");
		runtime.Frame(viewport,7.4);
		Check(!host.softened.empty() && Near(host.softened.back().sigma,7.5f,.01f) && Near(host.softened.back().saturation,.8f,.001f),
			"the Strogg pause rests in modal.softfocus");
		host.softFocus = false;
		ActionInvocation invocation;
		Check(runtime.ResolveAction("resume",invocation,error) && std::get<std::string>(invocation.arguments.at("command")) == "resume",
			"RESUME returns to the game");
		// The Strogg OBJECTIVES page keeps the construction in the family's colors
		// and returns through the translation.
		Runtime::EventEffects page;
		Check(runtime.RunEvent("objectivesShow",20,page,error),"the Strogg OBJECTIVES page opens");
		runtime.Frame(viewport,20.9);
		const auto strogged = runtime.PresentedValue("objectives-heading","font-family");
		const auto serial = runtime.PresentedValue("objectives-serial","text");
		Check(strogged && strogged->text == "r_strogg" && serial && serial->text == "#str_200280","an R_Strogg heading and the STROGG NET serial");
		const auto backFace = runtime.PresentedValue("objectives_back-label","font-family");
		const auto backColour = runtime.PresentedValue("objectives_back-label","color");
		Check(backFace && backFace->text == "r_strogg" && backColour && Near(static_cast<float>(backColour->data[0]),0xFC/255.f,.002f) &&
			Near(static_cast<float>(backColour->data[2]),0xC8/255.f,.002f),"BACK is a Strogg plate with its label in R_Strogg");
		Check(runtime.RunEvent("objectivesHide",21,page,error),"Back leaves the Strogg page");
		runtime.Frame(viewport,21.05);
		const auto translating = runtime.PresentedValue("nav_resume-latin","opacity");
		Check(translating && Near(static_cast<float>(translating->data[0]),0,.001f),"returning plays the translation again");
	}
	// Loading: progress, the continue prompt and the multiplayer server card.
	{
		const auto source = Read(argv[3]);
		Document document; std::vector<Diagnostic> diagnostics;
		Check(document.Load(source,diagnostics) && document.Model().id == "openq4.loading" && document.Model().actions.empty(),"loading document validates");
		Runtime runtime(host);
		Check(runtime.Initialize() && runtime.LoadDocument(source,"guis/loading/loading.q4ui",diagnostics),"loading loads into a runtime");
		Viewport viewport; viewport.canvasHeight = 720;
		std::string error;
		Check(runtime.SetState({{"map_loading",0.5},{"loading_levelshot",std::string("gfx/guis/loadscreens/airdefense1")}},error,1),"publish progress");
		runtime.Frame(viewport,1);
		Bounds fill, labelSp, labelMp;
		// Remastered: a 240 u bar (360 dp) from 392 u, 160 px into a 16:9 view.
		Check(runtime.GetBounds("progress-fill-clip",fill) && Near(fill.width,360*.5f,1.5f) && Near(fill.x,160+588,1.5f),
			"the bar fills with map_loading");
		const auto percent = runtime.PresentedValue("progress-percent-value","text");
		Check(percent && percent->text == "50","the percentage follows map_loading");
		Check(runtime.SetState({{"loading_phase",std::string("ASSETS")},{"loading_count",std::string("412/1630")}},error,1.1),
			"publish the loader's phase");
		runtime.Frame(viewport,1.1);
		const auto phase = runtime.PresentedValue("progress-phase","text");
		const auto count = runtime.PresentedValue("progress-count","text");
		Check(phase && phase->text == "ASSETS" && count && count->text == "412/1630","the phase line shows the phase and its count");
		Bounds phaseBox, countBox;
		Check(runtime.GetBounds("progress-phase",phaseBox) && runtime.GetBounds("progress-count",countBox) &&
			countBox.x >= phaseBox.x+phaseBox.width,"the count follows its phase");
		// The fill's clip is exact: no clip is approximated by its bounds.
		Check(runtime.Statistics().clipMaskFallbacks == 0,"the fill clips exactly");
		// Remastered: the levelshot drifts in by 3% over the load, unless
		// motion is reduced.
		const auto drift = runtime.PresentedValue("load-shot","transform");
		Check(drift && Near(static_cast<float>(drift->data[2]),1.015f,.0005f) && Near(static_cast<float>(drift->data[3]),1.015f,.0005f),
			"half way through the load the levelshot has drifted 1.5%");
		host.reducedMotion = true;
		runtime.Frame(viewport,1.5);
		const auto held = runtime.PresentedValue("load-shot","transform");
		Check(held && Near(static_cast<float>(held->data[2]),1,.0005f),"reduced motion holds the levelshot still");
		host.reducedMotion = false;
		Check(runtime.GetBounds("progress-prompt-text",labelSp) && labelSp.y+labelSp.height <= fill.y,"LOADING stands above the bar");
		const auto hiddenGlyph = runtime.PresentedValue("progress-prompt-glyph","display");
		Check(hiddenGlyph && hiddenGlyph->text == "none","no device glyph while loading");
		Runtime::EventEffects effects;
		Check(runtime.RunEvent("FinishedLoading",2,effects,error),"FinishedLoading turns LOADING into the continue prompt");
		const auto prompt = runtime.PresentedValue("progress-prompt-text","text");
		Check(prompt && prompt->text == "#str_200937","the desktop continue prompt replaces LOADING");
		Check(runtime.SetState({{"loading_controller",true}},error,2.1),"a controller was used last");
		runtime.Frame(viewport,2.1);
		const auto controllerPrompt = runtime.PresentedValue("progress-prompt-text","text");
		const auto glyph = runtime.PresentedValue("progress-prompt-glyph","display");
		Check(controllerPrompt && controllerPrompt->text == "#str_200984" && glyph && glyph->text == "block",
			"a controller shows the south button and CONTINUE");
		Check(runtime.SetState({{"loading_controller",false}},error,2.2),"back to the desktop prompt");
		const auto spCard = runtime.PresentedValue("server","display");
		Check(spCard && spCard->text == "none","single player shows no server card");
		Check(runtime.SetState({{"loading_mp",true},{"loading_ready",false},{"map_loading",1.0},{"server_name",std::string("openQ4 Test Server")},
			{"server_gametype",std::string("Deathmatch")}},error,3),"multiplayer composition");
		runtime.Frame(viewport,3);
		// Remastered multiplayer keeps the band low, with the server card on the
		// leading side, clear of the lower corner bracket (388 u, 582 dp).
		const auto card = runtime.PresentedValue("server","display");
		const auto mode = runtime.PresentedValue("server-mode","text");
		Bounds cardBox;
		Check(card && card->text == "block" && mode && mode->text == "Deathmatch","multiplayer shows the server card");
		const auto joining = runtime.PresentedValue("progress-prompt-text","text");
		Check(joining && joining->text == "#str_230037","a finished multiplayer load reads JOINING");
		Check(runtime.GetBounds("server-card",cardBox) && Near(cardBox.x,160+27) && cardBox.y+cardBox.height <= 582,
			"the card stands on the leading side above the bracket and the band");
		Check(runtime.GetBounds("progress-prompt-text",labelMp) && Near(labelSp.y,labelMp.y),"the band and the bar stay low");
		// The card stands on 384 u (576 dp) and grows upward with what the
		// session publishes: the players by team under their heads on a 16 dp
		// pitch, a spectators line, then the server's message, wrapped and
		// clipped at three 20 dp lines (the test face advances 0.6 em).
		const auto noRoster = runtime.PresentedValue("server-roster","display");
		const auto noMessage = runtime.PresentedValue("server-message","display");
		Check(Near(cardBox.y+cardBox.height,576) && Near(cardBox.height,120) && noRoster && noRoster->text == "none" &&
			noMessage && noMessage->text == "none","with no players known and no message the card keeps its base height");
		const auto profont = runtime.PresentedValue("server-address","font-family");
		Check(profont && profont->text == "profont","the address is tabular detail in Profont");
		Check(runtime.SetState({{"server_roster_known",true},{"server_team_mode",true},{"server_roster_rows",3.0},
			{"server_team_a",std::string("Kane\nRhodes\nStrauss")},{"server_team_b",std::string("Makron\nGladiator")},
			{"server_roster_extra",std::string("Spectating: 1")}},error,3.1),"three marines, two strogg and a spectator");
		runtime.Frame(viewport,3.1);
		Bounds headA, headB, teamA, extraLine;
		const auto byTeam = runtime.PresentedValue("server-teams","display");
		const auto everyone = runtime.PresentedValue("server-all","display");
		Check(byTeam && byTeam->text == "block" && everyone && everyone->text == "none","a team mode lists the players by team");
		Check(!host.glyphs.count('\n'),"a list's line breaks draw no glyph");
		Check(runtime.GetBounds("server-card",cardBox) && Near(cardBox.y+cardBox.height,576) && Near(cardBox.height,120+22+3*16+16),
			"the card grows upward by the heads, three rows and the spectators line");
		Check(runtime.GetBounds("server-team-a-head",headA) && runtime.GetBounds("server-team-b-head",headB) &&
			runtime.GetBounds("server-team-a",teamA) && runtime.GetBounds("server-roster-extra",extraLine) &&
			Near(headA.y,cardBox.y+108+4) && Near(headA.x,160+27+15) && Near(headB.x,160+27+15+(375-42)/2.f+12) && Near(headB.y,headA.y) &&
			Near(teamA.y,cardBox.y+108+22) && Near(extraLine.y,cardBox.y+108+22+3*16),
			"the lists stand side by side under their heads, the spectators line beneath them");
		const auto marineHead = runtime.PresentedValue("server-team-a-head","color");
		const auto stroggHead = runtime.PresentedValue("server-team-b-head","color");
		Check(marineHead && Near(static_cast<float>(marineHead->data[0]),0x6a/255.f,.002f) && stroggHead &&
			Near(static_cast<float>(stroggHead->data[0]),1,.002f),"the heads read in the team colors");
		Check(runtime.SetState({{"server_message",std::string("Welcome to the openQ4 test server")}},error,3.2),"a one-line message");
		runtime.Frame(viewport,3.2);
		Bounds message;
		Check(runtime.GetBounds("server-card",cardBox) && runtime.GetBounds("server-message",message) && Near(message.height,20) &&
			Near(cardBox.height,120+86+6+20) && Near(cardBox.y+cardBox.height,576) && Near(message.y,cardBox.y+108+86+6),
			"the message takes a line under the roster");
		Check(runtime.SetState({{"server_message",std::string("Frag limit 30 and no camping near the rail. Teams are balanced every map. "
			"Vote kicks need a majority. Be excellent to each other and have fun out there.")}},error,3.3),"a long message");
		runtime.Frame(viewport,3.3);
		Check(runtime.GetBounds("server-card",cardBox) && runtime.GetBounds("server-message",message) && Near(message.height,60) &&
			Near(cardBox.height,120+86+6+60) && cardBox.y >= 178.5f,"a long message wraps and clips at three lines, the card clear of the top band");
		Check(runtime.SetState({{"server_team_mode",false},{"server_roster_rows",7.0},
			{"server_players",std::string("One\nTwo\nThree\nFour\nFive\nSix\n+3 more")},{"server_roster_extra",std::string("")},
			{"server_message",std::string("")}},error,3.4),"seven rows of free-for-all players");
		runtime.Frame(viewport,3.4);
		const auto allShown = runtime.PresentedValue("server-all","display");
		const auto teamsHidden = runtime.PresentedValue("server-teams","display");
		Check(allShown && allShown->text == "block" && teamsHidden && teamsHidden->text == "none" && runtime.GetBounds("server-card",cardBox) &&
			Near(cardBox.height,120+22+7*16),"outside team modes one list holds every player");
		Check(runtime.SetState({{"server_roster_rows",0.0},{"server_players",std::string("")},
			{"server_roster_extra",std::string("Connecting: 2")}},error,3.5),"only players still connecting");
		runtime.Frame(viewport,3.5);
		const auto allEmpty = runtime.PresentedValue("server-all","display");
		Check(allEmpty && allEmpty->text == "none" && runtime.GetBounds("server-card",cardBox) && runtime.GetBounds("server-roster-extra",extraLine) &&
			Near(cardBox.height,120+4+16) && Near(extraLine.y,cardBox.y+108+4),"with no names the line stands alone, without heads");
		Check(runtime.SetState({{"server_roster_known",false},{"server_roster_extra",std::string("")}},error,3.6),"a fresh connection");
		runtime.Frame(viewport,3.6);
		Check(runtime.GetBounds("server-card",cardBox) && Near(cardBox.height,120),"a load that knows no players shows none");
		// The arsenal: each kind of item fades in over 150 ms in its color code,
		// two rows of ten in the thick band's leading part.
		host.materials.clear();
		Check(runtime.SetState({{"load_icon_1",1.0},{"load_icon_src_1",std::string("gfx/guis/hud/icons/item_railgun")},
			{"load_icon_r_1",0.0},{"load_icon_g_1",1.0},{"load_icon_b_1",0.0},
			{"load_icon_11",1.0},{"load_icon_src_11",std::string("gfx/guis/hud/icons/item_armorlarge")}},error,4),"two items spawn");
		Check(runtime.PlayTimeline("arsenal1",4) && runtime.PlayTimeline("arsenal11",4),"their icons fade in");
		runtime.Frame(viewport,4.075);
		const auto half = runtime.PresentedValue("arsenal-1","opacity");
		const auto tint = runtime.PresentedValue("arsenal-1","image-color");
		const auto unspawned = runtime.PresentedValue("arsenal-2","display");
		Check(half && Near(static_cast<float>(half->data[0]),.5f,.02f) && tint && Near(static_cast<float>(tint->data[0]),0,.001f) &&
			Near(static_cast<float>(tint->data[1]),1,.001f) && unspawned && unspawned->text == "none",
			"an icon is half in at 75 ms, tinted in the item's color code; an unspawned kind shows nothing");
		runtime.Frame(viewport,4.2);
		const auto full = runtime.PresentedValue("arsenal-11","opacity");
		Bounds first, eleventh;
		Check(full && Near(static_cast<float>(full->data[0]),1,.001f) && runtime.GetBounds("arsenal-1",first) &&
			runtime.GetBounds("arsenal-11",eleventh) && Near(first.x,160+216*1.5f,1) && Near(eleventh.x,first.x,1) &&
			Near(eleventh.y-first.y,18*1.5f,1) && Near(first.width,24,1) && first.y >= 426*1.5f,
			"the second row starts under the first, inside the thick band");
		Check(std::find(host.materials.begin(),host.materials.end(),"gfx/guis/hud/icons/item_railgun") != host.materials.end(),
			"the icon draws its image");
		Check(runtime.SetState({{"loading_mp",false}},error,4.3),"single player again");
		runtime.Frame(viewport,4.3);
		const auto spArsenal = runtime.PresentedValue("arsenal","display");
		Check(spArsenal && spArsenal->text == "none","single player has no arsenal");
		// Single player tips (section 14.17): under a TIP tag in the band's
		// leading part, each cross-fading in over 250 ms in the other slot.
		const auto noTips = runtime.PresentedValue("tips","display");
		Check(noTips && noTips->text == "none","no tip is shown until the session publishes one");
		Check(runtime.SetState({{"loading_tip_a",std::string("#str_230052")}},error,4.4) && runtime.PlayTimeline("tipA",4.4),"the first tip");
		runtime.Frame(viewport,4.525);
		const auto tipsShown = runtime.PresentedValue("tips","display");
		const auto halfTip = runtime.PresentedValue("tip-a","color");
		const auto tipText = runtime.PresentedValue("tip-a","text");
		Bounds tipBox, tagBox;
		Check(tipsShown && tipsShown->text == "block" && halfTip && Near(static_cast<float>(halfTip->data[3]),.35f,.02f) && tipText &&
			tipText->text == "#str_230052","the first tip fades in over 250 ms");
		Check(runtime.GetBounds("tip-a",tipBox) && runtime.GetBounds("tip-tag",tagBox) && Near(tipBox.x,160+216*1.5f,1) &&
			Near(tipBox.width,168*1.5f,1) && tagBox.y < tipBox.y && tipBox.y+tipBox.height <= 480*1.5f && tipBox.y >= 426*1.5f,
			"the tip sits under its tag in the thick band, from the riser to the bar");
		Check(runtime.SetState({{"loading_tip_b",std::string("#str_230053")}},error,10.4) && runtime.PlayTimeline("tipB",10.4),"the next tip");
		runtime.Frame(viewport,10.65);
		const auto outgoing = runtime.PresentedValue("tip-a","color");
		const auto incoming = runtime.PresentedValue("tip-b","color");
		Check(outgoing && Near(static_cast<float>(outgoing->data[3]),0,.001f) && incoming && Near(static_cast<float>(incoming->data[3]),.7f,.001f),
			"the next tip cross-fades in the other slot");
		Check(runtime.SetState({{"loading_ready",true}},error,10.66),"the level is ready");
		runtime.Frame(viewport,10.66);
		const auto readyTips = runtime.PresentedValue("tips","display");
		Check(readyTips && readyTips->text == "none","the continue prompt takes the band once the level is ready");
		Check(runtime.SetState({{"loading_ready",false},{"loading_mp",true}},error,10.7),"multiplayer");
		runtime.Frame(viewport,10.7);
		const auto mpTips = runtime.PresentedValue("tips","display");
		Check(mpTips && mpTips->text == "none","multiplayer shows its arsenal instead of tips");
		Check(runtime.SetState({{"loading_mp",false},{"loading_tip_a",std::string("")},{"loading_tip_b",std::string("")}},error,10.8),"reset");
		// A multiplayer join hands the screen to the Welcome card: handoff fades
		// it whole over 250 ms (80 ms under reduced motion), and present makes
		// it whole again for the next load.
		const auto opacity = [&]() {
			const auto value = runtime.PresentedValue("screen","opacity");
			Check(value.has_value(),"the screen's opacity");
			return static_cast<float>(value->data[0]);
		};
		runtime.Frame(viewport,11);
		Check(Near(opacity(),1,.001f),"the screen presents whole");
		Check(runtime.RunEvent("handoff",11,effects,error),"handoff plays");
		runtime.Frame(viewport,11.125);
		Check(opacity() > .3f && opacity() < .7f,"half way through the hand-off");
		runtime.Frame(viewport,11.26);
		Check(Near(opacity(),0,.001f),"handed off after 250 ms");
		Check(runtime.RunEvent("present",11.5,effects,error),"present plays");
		runtime.Frame(viewport,11.51);
		Check(Near(opacity(),1,.001f),"whole again for the next load");
		host.reducedMotion = true;
		runtime.SetReducedMotion(true,12);
		Check(runtime.RunEvent("handoff",12,effects,error),"handoff under reduced motion");
		runtime.Frame(viewport,12.04);
		Check(opacity() > .3f && opacity() < .7f,"half way after 40 ms");
		runtime.Frame(viewport,12.09);
		Check(Near(opacity(),0,.001f),"handed off within 80 ms");
		Check(runtime.RunEvent("present",12.2,effects,error),"present under reduced motion");
		runtime.Frame(viewport,12.21);
		Check(Near(opacity(),1,.001f),"whole again");
		host.reducedMotion = false;
		runtime.SetReducedMotion(false,12.3);
	}
	// The Single Player page and its Campaign sub-page (sections 8 and 9, the
	// sub-page level of 1.10): their rest states, going deeper and Back.
	{
		const auto pageSource = Read(argv[5]);
		const auto subSource = Read(argv[6]);
		Document pageDocument, subDocument; std::vector<Diagnostic> diagnostics;
		Check(pageDocument.Load(pageSource,diagnostics) && subDocument.Load(subSource,diagnostics),"the selector documents validate");
		for (const auto& diagnostic : diagnostics) std::fprintf(stderr,"selectors %s: %s\n",diagnostic.pointer.c_str(),diagnostic.message.c_str());
		Runtime page(host), sub(host);
		Check(page.Initialize() && page.LoadDocument(pageSource,"guis/menu/singleplayer.q4ui",diagnostics) &&
			sub.Initialize() && sub.LoadDocument(subSource,"guis/menu/campaigns.q4ui",diagnostics),"the selectors load into runtimes");
		Viewport viewport; viewport.canvasHeight = 720;
		std::string error;
		Runtime::EventEffects effects;
		Check(page.RunEvent("onActivate",1,effects,error) && sub.RunEvent("onActivate",1,effects,error),"activation places both at rest");
		page.Frame(viewport,1.1); sub.Frame(viewport,1.1);
		// At rest: the page title in the band's slot; on the sub-page the top
		// band one notch pitch on, the bottom band docked, the crumb 7 u up at
		// 80 % and 0.40 in the band's thin span, and the sub-page title at the
		// step's foot.
		Bounds pageTitle, subTitle, crumbClip;
		Check(page.GetBounds("title",pageTitle) && Near(pageTitle.x,160+39*1.5f,1) && Near(pageTitle.y,19*1.5f,1),"the page titles itself at 39,19 u");
		const auto pageTop = page.PresentedValue("band-top","transform");
		const auto subTop = sub.PresentedValue("band-top","transform");
		const auto pageBottom = page.PresentedValue("band-bottom","transform");
		const auto subBottom = sub.PresentedValue("band-bottom","transform");
		Check(pageTop && subTop && pageBottom && subBottom && Near(static_cast<float>(subTop->data[0]-pageTop->data[0]),97*1.5f,.05f) &&
			Near(static_cast<float>(subTop->data[1]),static_cast<float>(pageTop->data[1]),.01f) &&
			Near(static_cast<float>(subBottom->data[0]),static_cast<float>(pageBottom->data[0]),.01f),
			"the sub-page's top band sits one notch pitch on; the bottom band stays docked");
		// SINGLE PLAYER would overrun the band's thin span at 80 %, so the crumb
		// shrinks to fit it (0.714 of the title, measured from marine.ttf).
		const auto crumb = sub.PresentedValue("crumb","transform");
		const auto crumbColour = sub.PresentedValue("crumb","color");
		const auto crumbText = sub.PresentedValue("crumb","text");
		Check(crumb && Near(static_cast<float>(crumb->data[2]),.7224f,.002f) && crumbColour && Near(static_cast<float>(crumbColour->data[3]),.4f,.001f) &&
			crumbText && crumbText->text == "#str_42000","the parent title is the crumb at 0.40, shrunk to fit the span");
		// The crumb's top: 19 u less 7 u, with the scale about the box center.
		Bounds crumbBox;
		Check(sub.GetBounds("crumb",crumbBox) && Near(crumbBox.y+static_cast<float>(crumb->data[1])+crumbBox.height*(1-static_cast<float>(crumb->data[2]))/2,
			12*1.5f,.5f),"the crumb rises 7 u into the band's thin span");
		// Italian's GIOCATORE SINGOLO stops shrinking at the 13 dp type floor.
		host.language = "italian";
		Check(sub.RunEvent("onActivate",1.2,effects,error),"activation in Italian");
		sub.Frame(viewport,1.3);
		const auto floored = sub.PresentedValue("crumb","transform");
		Check(floored && Near(static_cast<float>(floored->data[2])*18,13,.05f),"a crumb never shrinks below the 13 dp type floor");
		// French's UN JOUEUR fits the span at the full 80 %.
		host.language = "french";
		Check(sub.RunEvent("onActivate",1.32,effects,error),"activation in French");
		sub.Frame(viewport,1.35);
		const auto french = sub.PresentedValue("crumb","transform");
		Check(french && Near(static_cast<float>(french->data[2]),.8f,.001f),"a crumb that fits keeps 80 % of the title");
		host.language = "english";
		Check(sub.RunEvent("onActivate",1.4,effects,error),"activation in English");
		sub.Frame(viewport,1.5);
		Check(sub.GetBounds("crumb-clip",crumbClip) && Near(crumbClip.x,160+39*1.5f,1) && Near(crumbClip.width,83*1.5f,1),
			"the crumb is cut at the band's step");
		Check(sub.GetBounds("title",subTitle) && Near(subTitle.x,160+136*1.5f,1) && Near(subTitle.y,19*1.5f,1),
			"the sub-page title starts at the step's foot");
		// Going deeper: the plates fade over 150 ms while the page sweeps
		// 640 u; the title becomes the crumb in 150 ms; from 50 ms the band
		// steps and CAMPAIGN carries into the slot at the step's foot.
		Check(page.RunEvent("subpageEnter",2,effects,error),"Campaign leads deeper");
		page.Frame(viewport,2.075);
		const auto fading = page.PresentedValue("content","opacity");
		const auto stepping = page.PresentedValue("band-top","transform");
		const auto sweeping = page.PresentedValue("content","transform");
		Check(sweeping && Near(static_cast<float>(sweeping->data[0]),640*1.5f/4,.5f),"the page sweeps linearly (a quarter at 75 ms)");
		Check(fading && Near(static_cast<float>(fading->data[0]),.5f,.02f) && stepping &&
			stepping->data[0] > pageTop->data[0] && stepping->data[0] < subTop->data[0],"at 75 ms the plates are half gone and the band is stepping");
		page.Frame(viewport,2.15);
		const auto crumbed = page.PresentedValue("title","transform");
		const auto crumbedColour = page.PresentedValue("title","color");
		const auto gone = page.PresentedValue("content","opacity");
		Check(crumbed && Near(static_cast<float>(crumbed->data[2]),static_cast<float>(crumb->data[2]),.001f) &&
			Near(static_cast<float>(crumbed->data[0]),static_cast<float>(crumb->data[0]),.01f) &&
			Near(static_cast<float>(crumbed->data[1]),static_cast<float>(crumb->data[1]),.01f) && crumbedColour &&
			Near(static_cast<float>(crumbedColour->data[3]),.4f,.001f) && gone && Near(static_cast<float>(gone->data[0]),0,.001f),
			"by 150 ms the title is the crumb and the plates are gone");
		page.Frame(viewport,2.35);
		const auto stepped = page.PresentedValue("band-top","transform");
		const auto swept = page.PresentedValue("content","transform");
		const auto carried = page.PresentedValue("subpage-carry","transform");
		const auto carriedColour = page.PresentedValue("subpage-carry","color");
		Bounds carry;
		Check(stepped && Near(static_cast<float>(stepped->data[0]),static_cast<float>(subTop->data[0]),.05f) && swept &&
			Near(static_cast<float>(swept->data[0]),640*1.5f,.5f) && carried && Near(static_cast<float>(carried->data[2]),.75f,.001f) &&
			carriedColour && Near(static_cast<float>(carriedColour->data[3]),.5f,.001f) && page.GetBounds("subpage-carry",carry) &&
			Near(carry.x,160+136*1.5f,1),"at 350 ms the band has stepped, the page has swept and CAMPAIGN sits at the step's foot");
		// The session presents the sub-page at 350 ms: plates and title at once,
		// the backing fading in over 150 ms (its activation).
		Check(sub.RunEvent("onDeactivate",2.9,effects,error) && sub.RunEvent("onActivate",3,effects,error),"the sub-page appears");
		sub.Frame(viewport,3.075);
		const auto backing = sub.PresentedValue("details","opacity");
		const auto plates = sub.PresentedValue("content","opacity");
		const auto shownTitle = sub.PresentedValue("title","color");
		Check(backing && Near(static_cast<float>(backing->data[0]),.5f,.02f) && plates && Near(static_cast<float>(plates->data[0]),1,.001f) &&
			shownTitle && Near(static_cast<float>(shownTitle->data[3]),.5f,.001f),"its plates and title show at once, its backing fades in");
		// Back: the sub-page title drops at once, the sub-page sweeps 640 u
		// toward the leading edge and the band steps back from the start; the
		// crumb returns over the last 150 ms.
		Check(sub.RunEvent("subpageLeave",4,effects,error),"Back climbs one level");
		sub.Frame(viewport,4.01);
		const auto dropped = sub.PresentedValue("title","color");
		const auto leaving = sub.PresentedValue("band-top","transform");
		const auto heldCrumb = sub.PresentedValue("crumb","transform");
		Check(dropped && Near(static_cast<float>(dropped->data[3]),0,.001f) && leaving && leaving->data[0] < subTop->data[0] &&
			heldCrumb && Near(static_cast<float>(heldCrumb->data[2]),static_cast<float>(crumb->data[2]),.001f),
			"the title drops at once and the band steps back while the crumb holds");
		sub.Frame(viewport,4.225);
		const auto returning = sub.PresentedValue("crumb","transform");
		Check(returning && returning->data[2] > crumb->data[2] && returning->data[2] < 1,"the crumb returns over the last 150 ms");
		sub.Frame(viewport,4.3);
		const auto home = sub.PresentedValue("band-top","transform");
		const auto returned = sub.PresentedValue("crumb","transform");
		const auto sweptLeft = sub.PresentedValue("content","transform");
		const auto backingOut = sub.PresentedValue("details","opacity");
		Check(home && Near(static_cast<float>(home->data[0]),static_cast<float>(pageTop->data[0]),.05f) && returned &&
			Near(static_cast<float>(returned->data[2]),1,.001f) && Near(static_cast<float>(returned->data[1]),0,.01f) && sweptLeft &&
			Near(static_cast<float>(sweptLeft->data[0]),-640*1.5f,.5f) && backingOut && Near(static_cast<float>(backingOut->data[0]),0,.001f),
			"by 300 ms the band is docked, the crumb is the title, the backing is out and the sub-page has swept out");
		// Hidden, the sub-page goes back to rest, so it never presents moved.
		Check(sub.RunEvent("onDeactivate",4.4,effects,error),"the sub-page leaves the screen");
		sub.Frame(viewport,4.45);
		const auto restedTitle = sub.PresentedValue("title","color");
		const auto restedContent = sub.PresentedValue("content","transform");
		const auto restedCrumb = sub.PresentedValue("crumb","transform");
		const auto subRestBand = sub.PresentedValue("band-top","transform");
		const auto restedBacking = sub.PresentedValue("details","opacity");
		Check(restedTitle && Near(static_cast<float>(restedTitle->data[3]),.5f,.001f) && restedContent && Near(static_cast<float>(restedContent->data[0]),0,.01f) &&
			restedCrumb && Near(static_cast<float>(restedCrumb->data[2]),static_cast<float>(crumb->data[2]),.001f) && subRestBand &&
			Near(static_cast<float>(subRestBand->data[0]),static_cast<float>(subTop->data[0]),.05f) && restedBacking &&
			Near(static_cast<float>(restedBacking->data[0]),0,.001f),"hidden, the sub-page rests in the sub-page state with its backing out");
		// The page returns at 300 ms: its plates and content fade in over 150 ms.
		Check(page.RunEvent("onDeactivate",3,effects,error),"the page left the screen at the hand-over");
		Check(page.RunEvent("onActivate",5,effects,error) && page.RunEvent("subpageReturn",5,effects,error),"the page returns");
		page.Frame(viewport,5.0005);
		const auto firstFrame = page.PresentedValue("band-top","transform");
		Check(firstFrame && Near(static_cast<float>(firstFrame->data[0]),static_cast<float>(pageTop->data[0]),.05f),
			"its first frame already shows it docked, never moved");
		page.Frame(viewport,5.075);
		const auto back = page.PresentedValue("content","opacity");
		const auto placed = page.PresentedValue("content","transform");
		const auto restored = page.PresentedValue("title","transform");
		const auto restedBand = page.PresentedValue("band-top","transform");
		const auto noCarry = page.PresentedValue("subpage-carry","opacity");
		Check(back && Near(static_cast<float>(back->data[0]),.5f,.02f) && placed && Near(static_cast<float>(placed->data[0]),0,.01f) &&
			restored && Near(static_cast<float>(restored->data[2]),1,.001f) && restedBand &&
			Near(static_cast<float>(restedBand->data[0]),static_cast<float>(pageTop->data[0]),.05f) && noCarry && Near(static_cast<float>(noCarry->data[0]),0,.001f),
			"the page fades back in place with its title in the slot and no carry");
		// Back while going deeper: every part returns from where it stands.
		page.Frame(viewport,5.3);
		Check(page.RunEvent("subpageEnter",6,effects,error),"Campaign leads deeper again");
		page.Frame(viewport,6.12);
		const auto partway = page.PresentedValue("band-top","transform");
		Check(page.RunEvent("subpageReverse150",6.12,effects,error),"Back reverses the change");
		page.Frame(viewport,6.125);
		const auto reversing = page.PresentedValue("band-top","transform");
		Check(partway && reversing && reversing->data[0] <= partway->data[0] + .01f && reversing->data[0] > pageTop->data[0],
			"the band starts back from where it stood");
		page.Frame(viewport,6.3);
		const auto reversed = page.PresentedValue("band-top","transform");
		const auto reversedContent = page.PresentedValue("content","transform");
		const auto reversedOpacity = page.PresentedValue("content","opacity");
		const auto reversedTitle = page.PresentedValue("title","transform");
		const auto reversedCarry = page.PresentedValue("subpage-carry","opacity");
		Check(reversed && Near(static_cast<float>(reversed->data[0]),static_cast<float>(pageTop->data[0]),.05f) && reversedContent &&
			Near(static_cast<float>(reversedContent->data[0]),0,.01f) && reversedOpacity && Near(static_cast<float>(reversedOpacity->data[0]),1,.001f) &&
			reversedTitle && Near(static_cast<float>(reversedTitle->data[2]),1,.001f) && reversedCarry && Near(static_cast<float>(reversedCarry->data[0]),0,.001f),
			"by 150 ms the page is back as it was");
		// Reduced motion: the session hands over at once and the arrival fades
		// in within 80 ms.
		sub.SetReducedMotion(true,6.9);
		Check(sub.RunEvent("onDeactivate",6.9,effects,error) && sub.RunEvent("onActivate",7,effects,error),"the sub-page arrives at once");
		sub.Frame(viewport,7.04);
		const auto halfIn = sub.PresentedValue("details","opacity");
		sub.Frame(viewport,7.09);
		const auto fullIn = sub.PresentedValue("details","opacity");
		Check(halfIn && halfIn->data[0] > 0 && halfIn->data[0] < 1 && fullIn && Near(static_cast<float>(fullIn->data[0]),1,.001f),
			"reduced motion fades the arrival in within 80 ms");
		sub.SetReducedMotion(false,7.2);
	}
	CheckEscape(host,argv[7]);
	CheckVote(host,argv[7]);
	CheckSettings(host,argv[7],argv[8]);
	CheckWelcome(host,argv[8]);
	Check(host.errors == 0,"no retained diagnostics");
	std::printf("retained screens: %d checks passed\n",checks);
	return 0;
}
