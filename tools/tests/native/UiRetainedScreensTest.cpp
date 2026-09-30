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
	bool ReadCVar(const std::string& name, size_t type, StateValue& value) override {
		if (name != "ui_retainedReducedMotion" || type != 1) return false;
		value = reducedMotion; return true;
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
	bool BeginLayer(std::uint32_t id, int, int) override { activeLayer = id; return true; }
	void CompositeLayer(std::uint32_t, std::uint32_t destination, float, const Bounds&) override { activeLayer = destination; }
	void MaskLayer(std::uint32_t, std::uint32_t destination, const Bounds&) override { activeLayer = destination; }
	void EndLayer(std::uint32_t restore) override { activeLayer = restore; }
	FontMetrics GetFontMetrics(const std::string&, int size) override { return {size*.8f,size*.2f,size*1.2f,size*.5f}; }
	Glyph GetGlyph(const std::string&, int size, std::uint32_t) override {
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
	"mods","demos","updates","credits","quit","resume","restartLevel","quitToMenu"};

static void CheckSessionActions(const Document& document) {
	for (const auto& [id,action] : document.Model().actions) {
		Check(action.operation == "session.menu","production screens request only session operations");
		const auto command = action.arguments.find("command");
		Check(command != action.arguments.end() && action.arguments.size() == 1,"one command argument");
		Check(SessionCommands.contains(std::get<std::string>(command->second.literal)),"every command is in the session allowlist");
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

int main(int argc, char** argv) {
	Check(argc == 4,"usage: title.q4ui pause.q4ui loading.q4ui");
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
		const auto shown = runtime.PresentedValue("emblem-glint","display");
		host.reducedMotion = true;
		runtime.Frame(viewport,11);
		const auto hidden = runtime.PresentedValue("emblem-glint","display");
		Check(shown && shown->text == "block" && hidden && hidden->text == "none" && runtime.Statistics().maskApplications == 0,
			"reduced motion hides the glint");
		host.reducedMotion = false;
	}
	// Pause: the level block binds the mission, difficulty, objectives and shot.
	{
		const auto source = Read(argv[2]);
		Document document; std::vector<Diagnostic> diagnostics;
		Check(document.Load(source,diagnostics) && document.Model().id == "openq4.pause","pause document validates");
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
		ActionInvocation invocation;
		Check(runtime.ResolveAction("resume",invocation,error) && std::get<std::string>(invocation.arguments.at("command")) == "resume","RESUME returns to the game");
	}
	// Loading: progress, the continue prompt and the multiplayer composition.
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
		Check(runtime.GetBounds("progress-fill-clip",fill) && Near(fill.width,607.5f*.5f,1.5f),"the bar fills with map_loading");
		// The bar's group carries the multiplayer raise transform, so the fill
		// is clipped through the clip mask, never left whole.
		const auto statistics = runtime.Statistics();
		Check(statistics.clipMasks > 0 && statistics.clipMaskFallbacks == 0,"the fill clips exactly under the raise transform");
		Check(runtime.GetBounds("progress-label",labelSp),"LOADING laid out");
		Runtime::EventEffects effects;
		Check(runtime.RunEvent("FinishedLoading",2,effects,error),"FinishedLoading turns LOADING into the continue prompt");
		const auto prompt = runtime.PresentedValue("progress-label","text");
		Check(prompt && prompt->text == "#str_200937","the continue prompt replaces LOADING");
		Check(runtime.SetState({{"loading_mp",true}},error,3),"multiplayer composition");
		runtime.Frame(viewport,3);
		// Transforms move presentation, not layout boxes: read the presented value.
		const auto raised = runtime.PresentedValue("progress","transform");
		const auto band = runtime.PresentedValue("load-bottom","transform");
		Check(raised && Near(static_cast<float>(raised->data[1]),-177,.01f) && band && Near(static_cast<float>(band->data[1]),-177,.01f),
			"multiplayer raises the bottom band to 227 u and the bar to 313 u");
		Check(runtime.GetBounds("progress-label",labelMp) && Near(labelSp.y,labelMp.y),"the raise leaves layout untouched");
	}
	Check(host.errors == 0,"no retained diagnostics");
	std::printf("retained screens: %d checks passed\n",checks);
	return 0;
}
