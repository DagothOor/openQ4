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
	std::vector<float> compositeOpacities;
	bool BeginLayer(std::uint32_t id, int, int) override { activeLayer = id; return true; }
	void CompositeLayer(std::uint32_t, std::uint32_t destination, float opacity, const Bounds&) override {
		compositeOpacities.push_back(opacity); activeLayer = destination;
	}
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
		{
			Runtime::EventEffects shown;
			Check(runtime.RunEvent("exitModalShow",14,shown,error),"the exit confirmation opens");
			runtime.Frame(viewport,14.1);
			const auto scrim = runtime.PresentedValue("exitModal","background-color");
			const auto frameIn = runtime.PresentedValue("exitModal-frame","opacity");
			const auto waiting = runtime.PresentedValue("exitModal-contents","display");
			Check(scrim && Near(static_cast<float>(scrim->data[3]),.47f,.02f) && frameIn && Near(static_cast<float>(frameIn->data[0]),.5f,.02f) &&
				waiting && waiting->text == "none","half way in, the scrim and frame rise while the contents wait");
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
			const auto held = runtime.PresentedValue("exitModal","background-color");
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
		// SAVE GAME's label carries from its row at 212.2 u into the title slot.
		Runtime::EventEffects carry;
		Check(runtime.RunEvent("carry_saveGame",2,carry,error),"a pause page hand-off carries its label");
		runtime.Frame(viewport,2.002);
		const auto begin = runtime.PresentedValue("title-carry","transform");
		const auto carried = runtime.PresentedValue("title-carry","text");
		Check(begin && Near(static_cast<float>(begin->data[1]),(212.2f+2.8f-19)*1.5f,.2f) && carried && carried->text == "#str_200003",
			"SAVE GAME starts on its row");
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
	}
	Check(host.errors == 0,"no retained diagnostics");
	std::printf("retained screens: %d checks passed\n",checks);
	return 0;
}
