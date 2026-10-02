// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
// Production document, Runtime and SettingsTransaction; counted font/CVar host.
#define main PresetFixtureMain
#include "UiSystemPresetRuntimeTest.cpp"
#undef main

static constexpr const char* Row="settings_lightgrid_preload";
static constexpr const char* StatusLine="settings_lightgrid_preload-status";
static void Inside(const Bounds& a,const Bounds& b,const char* why) {
 const bool okay=a.x>=b.x-1&&a.y>=b.y-1&&a.x+a.width<=b.x+b.width+1&&a.y+a.height<=b.y+b.height+1;
 if(!okay)std::fprintf(stderr,"%s: %g,%g %gx%g in %g,%g %gx%g\n",why,a.x,a.y,a.width,a.height,b.x,b.y,b.width,b.height);
 Check(okay,why);
}
// What the service reports about the loaded map, and the line it shows.
struct LightGrid { bool committed,consumed,effective,pending; const char* text; };
static const LightGrid Loaded[]={
 {true,true,false,true,"#str_230078"},   // a saved preload waits for the next map
 {true,true,true,false,"#str_230079"},   // the map preloads its light grids
 {false,true,false,false,"#str_230080"}, // the map streams them
 {false,false,false,false,"#str_230081"},// the map has none
};
static void Status(View& v,const LightGrid& c,bool mapLoaded=true) {
 const StateValues s{{"settings.lightGrid.committed",c.committed},{"settings.lightGrid.mapLoaded",mapLoaded},
  {"settings.lightGrid.consumed",c.consumed},{"settings.lightGrid.effective",c.effective},{"settings.lightGrid.pending",c.pending}};
 Check(v.runtime.SetState(s,v.error,v.time),v.error.c_str());v.Frame();
}
static std::string Presented(View& v,const char* node,const char* property) {
 const auto value=v.runtime.PresentedValue(node,property);Check(value.has_value(),node);return value->text;
}
static void Run(const std::string& source,const std::string& folder,const char* locale,float expansion) {
 View v(source,folder+"/"+locale+"_openq4.lang",1,1280,720,expansion,folder+"/"+locale+"_guis.lang");
 Check(Presented(v,StatusLine,"display")=="none","no loaded map shows no light-grid status");
 // The toggle proposes the preload through the ordinary edit and writes nothing.
 Check(v.runtime.FocusControl(Row,v.time),"the preload toggle focuses");v.Frame();
 v.Key(MenuInput::Accept);auto actions=v.runtime.TakeActions();
 Check(actions.size()==1&&actions[0].proposal&&SettingsValueEqual(*actions[0].proposal,true),"the toggle proposes preloading");
 ActionInvocation invocation;Check(v.runtime.ResolveAction(actions[0].action,invocation,v.error,&*actions[0].proposal),"the preload action resolves");
 Check(invocation.operation=="settings.system.edit"&&invocation.arguments==StateValues({{"r_lightGridPreload",true}}),"the preload edits only its own setting");
 Check(v.tx.Edit(View::Owner,invocation.arguments).code==SettingsCode::Ok,"the preload draft is accepted");v.Sync();
 Check(v.runtime.AcknowledgeControlProposal(Row,actions[0].proposalToken,true),"readback precedes acknowledgment");v.Frame();
 Check(v.host.writes==0,"a draft writes no setting");
 Check(v.Alias("draftLightGridPreload")=="1"&&v.Alias("baselineLightGridPreload")=="0","aliases tell the draft from the applied choice");
 // The status line names what the loaded map does with its light grids.
 for(const auto& c:Loaded) {
  Status(v,c);
  Check(Presented(v,StatusLine,"display")=="block"&&Presented(v,StatusLine,"text")==c.text,"the status names the loaded map's light grids");
 }
 Status(v,Loaded[0],false);Check(Presented(v,StatusLine,"display")=="none","an unloaded map hides the status");
 // The help, status and deferred messages fit at every size and density.
 struct Case{int width,height;float density;};
 for(const auto c:{Case{1280,720,1},Case{1280,720,2},Case{640,480,1},Case{640,480,2}}) {
  std::fprintf(stderr,"Render options locale=%s expansion=%g viewport=%dx%d density=%g\n",locale,expansion,c.width,c.height,c.density);
  v.viewport.width=c.width;v.viewport.height=c.height;v.viewport.displayScale=c.density;v.viewport.FitToMinimum(640,480);v.Frame();
  for(const auto& s:Loaded) {
   // Each status changes the card's height; focus must reveal the whole card.
   Status(v,s);Check(v.runtime.FocusControl("settings_irradiance",v.time),"focus leaves the preload row");v.Frame();
   Check(v.runtime.FocusControl(Row,v.time),"the preload row receives focus");v.Frame();
   Inside(v.Box(Row),v.Box("settings-body"),"the focused preload card is revealed");
   Inside(v.Box(Row),{0,0,float(c.width),float(c.height)},"the preload card stays inside the physical viewport");
   TextFits(v,"settings_lightgrid_preload-label");TextFits(v,"settings_lightgrid_preload-help");TextFits(v,StatusLine);
  }
  for(const auto* m:{"#str_230073","#str_230074","#str_230075","#str_230076"}){v.message=m;v.Sync();v.Frame();TextFits(v,"settings-message");}
  v.message="#str_230007";v.Sync();v.Frame();
 }
 // Recovery titles the confirmation panel for any attempt.
 Check(v.runtime.SetState({{"settings.phase",3.0},{"settings.confirmationVisible",true}},v.error,v.time),v.error.c_str());v.Frame();
 Check(Presented(v,"confirmation-panel-title","text")=="#str_230077","recovery reads the neutral title");TextFits(v,"confirmation-panel-title");
 Check(v.runtime.SetState({{"settings.phase",1.0},{"settings.confirmationVisible",false}},v.error,v.time),v.error.c_str());v.Frame();
 Check(Presented(v,"confirmation-panel-title","text")=="#str_229993","otherwise the panel asks the Keep question");
}
int main(int argc,char** argv) {
 Check(argc==3||argc==4,"source, locale folder and optional locale");const auto source=Read(argv[1]);
 for(const auto* locale:{"english","spanish","polish","russian","french","italian","german"}) {
  if(argc==4&&std::string(argv[3])!=locale)continue;
  for(float expansion:{1.f,1.4f})Run(source,argv[2],locale,expansion);
 }
 std::printf("SYSTEM render options: %u checks passed\n",checks);
}
