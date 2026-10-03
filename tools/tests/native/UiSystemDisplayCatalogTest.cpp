// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
// Production document, Runtime and SettingsTransaction; counted font/CVar host.
// The display lists are published as the settings service publishes them; the
// service's own builder, token and pick checks are qualified separately.
#define main PresetFixtureMain
#include "UiSystemPresetRuntimeTest.cpp"
#undef main

static constexpr const char* Device="settings_display_device";
static constexpr const char* Span="settings_multiscreen";
static void Inside(const Bounds& a,const Bounds& b,const char* why) {
 const bool okay=a.x>=b.x-1&&a.y>=b.y-1&&a.x+a.width<=b.x+b.width+1&&a.y+a.height<=b.y+b.height+1;
 if(!okay)std::fprintf(stderr,"%s: %g,%g %gx%g in %g,%g %gx%g\n",why,a.x,a.y,a.width,a.height,b.x,b.y,b.width,b.height);
 Check(okay,why);
}
// The device list as the service publishes it to the page owner.
struct Lists { bool available=true,span=true; int count=2; std::vector<std::string> labels; std::string token="7"; };
static void Publish(View& v,const Lists& l) {
 StateValues s{{"settings.display.available",l.available},{"settings.display.spanAvailable",l.span},
  {"settings.display.catalog",l.token},{"settings.display.count",double(l.count)},{"settings.display.optionCount",double(1+l.labels.size())}};
 for(size_t i=0;i<8;++i)s["settings.display."+std::to_string(i)+".label"]=i<l.labels.size()?l.labels[i]:std::string();
 Check(v.runtime.SetState(s,v.error,v.time),v.error.c_str());v.Frame();
}
static const std::vector<std::string> Two{"1: Primary monitor","2: Secondary monitor"};
static std::string Id(const char* row,const char* part){return std::string(row)+part;}
static std::string Option(const char* row,int i){return std::string(row)+"-option-"+std::to_string(i);}
static std::string Shown(View& v,const char* id){const auto p=v.runtime.PresentedValue(id,"display");Check(p.has_value(),id);return p->text;}
static std::string ClosedText(View& v,const char* row){return v.Element(Id(row,"-value").c_str())->GetInnerRML();}
static std::string Encoded(const std::string& text){return Rml::StringUtilities::EncodeRml(text);}
// One label from a semicolon-separated localized list.
static std::string Segment(View& v,const char* key,unsigned index) {
 std::istringstream labels(v.host.strings.at(key));std::string label;
 for(unsigned i=0;i<=index;++i)std::getline(labels,label,';');
 return label;
}
static void Draft(View& v,const StateValues& values){Check(v.tx.Edit(View::Owner,values).code==SettingsCode::Ok,"the draft accepts the display values");v.Sync();v.Frame();}
// Begin again on these applied values, as after an Apply.
static void Applied(View& v,const StateValues& values) {
 Check(v.tx.Cancel(View::Owner).code==SettingsCode::Ok,"end the transaction");
 for(const auto& [key,value]:values)v.host.live[key]=value;
 Check(v.tx.Begin(View::Owner).code==SettingsCode::Ok,"begin on the applied values");v.Sync();v.Frame();
}
// The painted strength of an option label: 0.88 available, 0.40 unavailable.
static double Strength(View& v,const std::string& option){return v.Element((option+"-label").c_str())->GetComputedValues().color().alpha/255.0;}
static constexpr const char* Reason="settings_multiscreen-status";
// Display cards found taller than the scroll body.
static unsigned oversized=0;
static void Open(View& v,const char* row) {
 Check(v.runtime.FocusControl(row,v.time),"the display row focuses");v.Frame();
 v.Key(MenuInput::Accept);v.Frame();
 Check(v.runtime.GetWidgetState(row)->popupOpen,"the display row opens");Check(v.runtime.TakeActions().empty(),"opening proposes nothing");
}
static std::string Highlight(View& v,const char* row,MenuInput key){v.Key(key);v.Frame();return v.runtime.GetWidgetState(row)->highlight;}
static void Close(View& v,const char* row){v.Key(MenuInput::Back);v.Frame();Check(!v.runtime.GetWidgetState(row)->popupOpen&&v.runtime.TakeActions().empty(),"Back closes without a proposal");}
static ControlAction Pick(View& v) {
 v.Key(MenuInput::Accept);auto actions=v.runtime.TakeActions();
 Check(actions.size()==1&&actions[0].proposal&&actions[0].proposalToken,"one typed proposal");return actions[0];
}
static ActionInvocation Resolve(View& v,const ControlAction& pick) {
 ActionInvocation invocation;Check(v.runtime.ResolveAction(pick.action,invocation,v.error,&*pick.proposal),"the display action resolves");return invocation;
}
// One display: neither row shows, and keyboard order passes over both,
// unless a row holds something the player must be able to see or undo.
static void OneDisplay(View& v) {
 Applied(v,{{"r_screen",-1.0},{"r_multiScreen",0.0}});
 Publish(v,{true,false,1,{"1: Primary monitor"}});
 Check(Shown(v,Device)=="none"&&Shown(v,Span)=="none","one display hides both rows");
 Check(!v.runtime.FocusControl(Device,v.time)&&!v.runtime.FocusControl(Span,v.time),"hidden rows cannot take focus");
 Check(v.runtime.FocusControl("settings_text_scale",v.time),"focus the control before the display column");v.Frame();
 v.Key(MenuInput::Next);Check(v.runtime.FocusedControl()=="settings_fullscreen","keyboard order passes over the hidden rows");
 // A change not yet applied keeps its row, so it can be seen and undone.
 Draft(v,{{"r_screen",0.0}});Check(Shown(v,Device)=="block","a pending choice of the only display keeps the row");
 Draft(v,{{"r_screen",-1.0}});Check(Shown(v,Device)=="none","undoing it hides the row again");
 // The first display index past the count is already missing.
 Applied(v,{{"r_screen",1.0}});Publish(v,{true,false,1,{"1: Primary monitor","Display 2 (not connected)"}});
 Check(Shown(v,Device)=="block"&&ClosedText(v,Device)==Encoded("Display 2 (not connected)"),"an applied display one past the count shows the row");
 // An applied span shows its row, and so does turning it off until applied.
 Applied(v,{{"r_screen",-1.0},{"r_multiScreen",1.0}});Publish(v,{true,false,1,{"1: Primary monitor"}});
 Check(Shown(v,Device)=="none"&&Shown(v,Span)=="block","an applied span shows its row on one display");
 Draft(v,{{"r_multiScreen",0.0}});Check(Shown(v,Span)=="block","turning the span off keeps its row until it is applied");
 Applied(v,{{"r_multiScreen",0.0}});Check(Shown(v,Span)=="none","once applied the span row hides");
 // A display picked on two displays stays reachable when its monitor goes:
 // Apply needs the recorded monitor until the slot is chosen again.
 Publish(v,{true,true,2,Two});Draft(v,{{"r_screen",0.0}});
 Publish(v,{true,false,1,{"1: Secondary monitor"}});
 Check(Shown(v,Device)=="block","a recorded pick whose monitor changed keeps its row");
 Check(ClosedText(v,Device)==Encoded("1: Secondary monitor"),"the row names the display now at that index");
 Draft(v,{{"r_screen",-1.0}});Check(Shown(v,Device)=="none","taking the pick back hides the row");
}
// A display or span the lists cannot offer keeps its row, so it can be undone.
static void Stale(View& v) {
 Applied(v,{{"r_screen",2.0},{"r_multiScreen",1.0}});
 Publish(v,{true,false,1,{"1: Primary monitor","Display 2 (not connected)","Display 3 (not connected)"}});
 Check(Shown(v,Device)=="block"&&Shown(v,Span)=="block","a stale display or span shows its row on one display");
 Check(ClosedText(v,Device)==Encoded("Display 3 (not connected)"),"the closed choice names the missing display");
 Check(ClosedText(v,Span)==Encoded(Segment(v,"#str_200059",1)),"the closed choice names the span");
 Open(v,Device);
 Check(Highlight(v,Device,MenuInput::Home)==Option(Device,0),"Auto leads the device list");
 Check(Highlight(v,Device,MenuInput::End)==Option(Device,1),"a display that is not connected cannot be picked");
 Check(std::abs(Strength(v,Option(Device,0))-.88)<.01&&std::abs(Strength(v,Option(Device,1))-.88)<.01,"available displays read at full strength");
 Check(std::abs(Strength(v,Option(Device,2))-.40)<.01&&std::abs(Strength(v,Option(Device,3))-.40)<.01,"displays that are not connected read as unavailable");
 for(int i=1;i<4;++i)Check(v.Element(Option(Device,i).c_str())->IsVisible(true),"the list shows its slots");
 for(int i=4;i<9;++i)Check(!v.Element(Option(Device,i).c_str())->IsVisible(true),"slots past the list stay hidden");
 auto pick=Pick(v);Check(SettingsValueEqual(*pick.proposal,0.0),"the connected display is proposed");
 auto invocation=Resolve(v,pick);
 Check(invocation.operation=="settings.system.display"&&invocation.arguments==StateValues({{"index",0.0},{"catalog",std::string("7")}}),
  "a pick sends its slot and the list token, not a setting");
 // The service writes r_screen; the readback precedes the acknowledgment.
 Draft(v,{{"r_screen",0.0}});Check(v.runtime.AcknowledgeControlProposal(Device,pick.proposalToken,true),"the readback acknowledges the pick");v.Frame();
 Check(Shown(v,Device)=="block","the pick keeps its row until it is applied");
 Open(v,Span);
 Check(Highlight(v,Span,MenuInput::End)==Option(Span,0),"a span the lists cannot offer cannot be picked");
 pick=Pick(v);Check(SettingsValueEqual(*pick.proposal,0.0),"the primary display alone is proposed");
 invocation=Resolve(v,pick);
 Check(invocation.operation=="settings.system.edit"&&invocation.arguments==StateValues({{"r_multiScreen",0.0}}),"the span edits only r_multiScreen");
 Draft(v,{{"r_multiScreen",0.0}});Check(v.runtime.AcknowledgeControlProposal(Span,pick.proposalToken,true),"the readback acknowledges the span");v.Frame();
 Check(Shown(v,Span)=="block","turning the span off keeps its row until it is applied");
 Applied(v,{{"r_screen",0.0},{"r_multiScreen",0.0}});
 Check(Shown(v,Device)=="none"&&Shown(v,Span)=="none","once applied on one display both rows hide again");
}
// Several displays: both rows, the device pick and the token it carries.
static void Several(View& v) {
 Publish(v,{true,true,2,Two});
 Draft(v,{{"r_screen",-1.0},{"r_multiScreen",0.0},{"r_fullscreen",false},{"r_borderless",false},{"r_fullscreenDesktop",false}});
 Check(Shown(v,Device)=="block"&&Shown(v,Span)=="block","several displays show both rows");
 Check(ClosedText(v,Device)==Encoded(v.host.strings.at("#str_229914")),"Auto reads its localized label");
 Check(ClosedText(v,Span)==Encoded(Segment(v,"#str_200059",0)),"the primary display alone reads its localized label");
 Open(v,Device);
 Check(Highlight(v,Device,MenuInput::End)==Option(Device,2),"the list ends at the last display");
 Check(v.Element(Id(Option(Device,2).c_str(),"-label").c_str())->GetInnerRML()==Encoded(Two[1]),"a slot reads its published label");
 auto pick=Pick(v);Check(SettingsValueEqual(*pick.proposal,1.0),"the second display is proposed");
 auto invocation=Resolve(v,pick);
 Check(invocation.operation=="settings.system.display"&&invocation.arguments==StateValues({{"index",1.0},{"catalog",std::string("7")}}),
  "the pick sends slot 1 and the list token");
 Check(v.runtime.AcknowledgeControlProposal(Device,pick.proposalToken,false),"a refused pick is declined");v.Frame();
 Check(ClosedText(v,Device)==Encoded(v.host.strings.at("#str_229914")),"a declined pick keeps the accepted choice");
 pick=[&]{Open(v,Device);Highlight(v,Device,MenuInput::End);return Pick(v);}();
 Draft(v,{{"r_screen",1.0}});Check(v.runtime.AcknowledgeControlProposal(Device,pick.proposalToken,true),"the readback acknowledges the pick");v.Frame();
 Check(ClosedText(v,Device)==Encoded(Two[1]),"the closed choice names the picked display");
 Check(v.Alias("draftDisplayDevice")=="1"&&v.Alias("baselineDisplayDevice")=="0"&&v.Alias("draftMultiScreen")=="0","aliases tell the draft from the applied display");
 // A new list token travels with the next pick.
 Publish(v,{true,true,2,Two,"8"});
 Open(v,Device);Check(Highlight(v,Device,MenuInput::Home)==Option(Device,0),"Auto stays first");
 pick=Pick(v);invocation=Resolve(v,pick);
 Check(invocation.arguments==StateValues({{"index",-1.0},{"catalog",std::string("8")}}),"Auto sends -1 and the current token");
 Check(v.runtime.AcknowledgeControlProposal(Device,pick.proposalToken,false),"decline Auto");v.Frame();
 // A list that changes under the open popup closes it without a pick.
 Open(v,Device);
 Publish(v,{true,true,2,{"1: Primary monitor","2: Replacement monitor"},"9"});
 Check(!v.runtime.GetWidgetState(Device)->popupOpen&&v.runtime.TakeActions().empty(),"a changed list closes the open popup without a pick");
 Check(ClosedText(v,Device)==Encoded("2: Replacement monitor"),"the closed choice follows the new label");
}
// Spanning needs the lists to allow it and a borderless window or desktop
// fullscreen; exclusive fullscreen and an ordinary window cannot span.
static void Spanning(View& v) {
 for(unsigned bits=0;bits<16;++bits) {
  const bool fullscreen=bits&1,desktop=bits&2,borderless=bits&4,available=bits&8;
  // A span needs the lists to allow it, and desktop fullscreen or a
  // borderless window: an ordinary window drops it and exclusive refuses it.
  const bool offered=available&&((fullscreen&&desktop)||(!fullscreen&&borderless));
  Publish(v,{true,available,2,Two});
  Draft(v,{{"r_fullscreen",fullscreen},{"r_fullscreenDesktop",desktop},{"r_borderless",borderless},{"r_multiScreen",0.0}});
  Check(Shown(v,Reason)==(offered?"none":"block"),"a line says why spanning is unavailable, and only then");
  const auto reason=v.runtime.PresentedValue(Reason,"text");
  Check(reason&&reason->text==(available?"#str_230088":"#str_230089"),"the line names the missing window mode or the displays");
  Open(v,Span);
  Check(std::abs(Strength(v,Option(Span,1))-(offered?.88:.40))<.01,"Yes reads as unavailable exactly when it is");
  Check(Highlight(v,Span,MenuInput::End)==Option(Span,offered?1:0),"the span is offered only where it can apply");
  if(!offered){Close(v,Span);continue;}
  auto pick=Pick(v);Check(SettingsValueEqual(*pick.proposal,1.0),"the span is proposed");
  const auto invocation=Resolve(v,pick);
  Check(invocation.operation=="settings.system.edit"&&invocation.arguments==StateValues({{"r_multiScreen",1.0}}),"the span edits only r_multiScreen");
  Check(v.runtime.AcknowledgeControlProposal(Span,pick.proposalToken,false),"decline the span");v.Frame();
 }
 // A drafted span stays named while it cannot apply, and can be turned off.
 Draft(v,{{"r_fullscreen",true},{"r_fullscreenDesktop",false},{"r_borderless",false},{"r_multiScreen",1.0}});
 Check(ClosedText(v,Span)==Encoded(Segment(v,"#str_200059",1)),"an unoffered span still names itself");
 Open(v,Span);Check(Highlight(v,Span,MenuInput::Home)==Option(Span,0),"the primary display alone stays pickable");Close(v,Span);
 Draft(v,{{"r_fullscreen",false},{"r_multiScreen",0.0}});
}
// Without lists neither row can work, so both stay hidden.
static void Unavailable(View& v) {
 Publish(v,{false,false,0,{}});Draft(v,{{"r_screen",3.0},{"r_multiScreen",1.0}});
 Check(Shown(v,Device)=="none"&&Shown(v,Span)=="none","without lists both rows stay hidden");
 Check(!v.runtime.CanActivateControl(Device,v.time)&&!v.runtime.CanActivateControl(Span,v.time),"rows without lists cannot act");
 Draft(v,{{"r_screen",-1.0},{"r_multiScreen",0.0}});
}
// The page's shared editing rule gates both rows.
static void Guards(View& v) {
 Publish(v,{true,true,2,Two});
 for(const auto& blocked:StateValues{{"settings.busy",true},{"settings.confirmationVisible",true},{"page.discardVisible",true},
                                      {"ui.numberDraftsPending",true},{"settings.open",false},{"settings.phase",2.0}}) {
  v.Sync();Check(v.runtime.SetState({{blocked.first,blocked.second}},v.error,v.time),"publish a competing workflow");v.Frame();
  Check(!v.runtime.CanActivateControl(Device,v.time)&&!v.runtime.CanActivateControl(Span,v.time),"display picks wait for competing workflows");
  Check(v.runtime.SetState({{"page.discardVisible",false}},v.error,v.time),"clear the local discard dialog");
 }
 v.Sync();v.Frame();Check(v.runtime.CanActivateControl(Device,v.time)&&v.runtime.CanActivateControl(Span,v.time),"both rows act again");
}
// A long name and every slot: cards and popups fit and stay revealed.
static void Fit(View& v,const char* locale,float expansion) {
 // The builder cuts names to 48 code points; the slot adds "N: ".
 const std::string longest="1: "+std::string(47,'W')+"\xE2\x80\xA6";
 std::vector<std::string> eight;for(int i=0;i<8;++i)eight.push_back(std::to_string(i+1)+": Display "+std::to_string(i+1));
 struct Case{int width,height;float density,text;bool longName;};
 for(const auto c:{Case{1920,1080,1,1,false},Case{1280,720,1,1,true},Case{1280,720,1.25,1,true},Case{640,480,1,1,false},Case{640,480,1,2,false},Case{3440,1440,2,2,true}}) {
  std::fprintf(stderr,"Display lists locale=%s expansion=%g viewport=%dx%d density=%g text=%g\n",locale,expansion,c.width,c.height,c.density,c.text);
  v.viewport.width=c.width;v.viewport.height=c.height;v.viewport.displayScale=c.density;v.viewport.textScale=c.text;v.Frame();
  auto labels=eight;if(c.longName)labels[0]=longest;
  Publish(v,{true,true,8,labels});Draft(v,{{"r_screen",0.0},{"r_multiScreen",0.0}});
  for(const auto* row:{Device,Span}) {
   Check(v.runtime.FocusControl("settings_text_scale",v.time),"focus leaves the display column");v.Frame();
   Check(v.runtime.FocusControl(row,v.time),"the display row receives focus");v.Frame();
   // A card taller than the scroll body, as the span card with its reason
   // line is at 640x480 with 200% text, is revealed from its top.
   const auto card=v.Box(row),body=v.Box("settings-body");
   if(card.height>body.height+1){++oversized;Check(std::abs(card.y-body.y)<=1,"an oversized display card is revealed from its top");}
   else Inside(card,body,"the focused display card is revealed");
   TextFits(v,Id(row,"-label").c_str());TextFits(v,Id(row,"-value").c_str());
  }
  Open(v,Device);
  Inside(v.Box(Id(Device,"-popup").c_str()),v.Box("settings-body"),"the device popup stays in the scroll body");
  const auto last=Highlight(v,Device,MenuInput::End);Check(last==Option(Device,8),"the eighth display is reachable");
  Inside(v.Box(last.c_str()),v.Box(Id(Device,"-viewport").c_str()),"the last display is wholly visible");
  TextFits(v,(last+"-label").c_str());
  Check(Highlight(v,Device,MenuInput::Home)==Option(Device,0),"Home returns to Auto");
  // Eight rows show before the list scrolls, as the visual specification's
  // dropdowns do, where the scroll body holds them; at 1280x720 it holds
  // about seven, and the list shows what fits.
  if(c.width==1920&&c.density==1&&c.text==1&&!c.longName) {
   const auto viewport=v.Box(Id(Device,"-viewport").c_str());
   Inside(v.Box(Option(Device,7).c_str()),viewport,"the eighth row shows before the list scrolls");
   Check(v.Box(Option(Device,8).c_str()).y>=viewport.y+viewport.height-1,"the ninth row waits below the eighth");
  }
  if(c.longName){Check(Highlight(v,Device,MenuInput::Down)==Option(Device,1),"the long name is reachable");TextFits(v,(Option(Device,1)+"-label").c_str());}
  Close(v,Device);
 }
 v.viewport.width=1280;v.viewport.height=720;v.viewport.displayScale=1;v.viewport.textScale=1;v.Frame();
}
// Recreating the document reads the current lists and replays no pick.
static void Recreate(View& v,const std::string& source) {
 Publish(v,{true,true,2,Two});Draft(v,{{"r_screen",1.0},{"r_multiScreen",0.0}});
 std::string snapshot;Check(v.runtime.SaveSnapshot(snapshot,v.error,v.time),"the page snapshot saves");
 v.runtime.CloseDocument();std::vector<Diagnostic> diagnostics;
 Check(v.runtime.LoadDocument(source,"guis/menu/settings/system.q4ui",diagnostics)&&v.runtime.RestoreSnapshot(snapshot,v.error,v.time),"the display rows survive recreation");
 v.Sync();Publish(v,{true,true,2,Two});
 Check(ClosedText(v,Device)==Encoded(Two[1])&&v.runtime.TakeActions().empty(),"the recreated row reads the current list and replays no pick");
}
static void Run(const std::string& source,const std::string& folder,const char* locale,float expansion) {
 View v(source,folder+"/"+locale+"_openq4.lang",1,1280,720,expansion,folder+"/"+locale+"_guis.lang");
 for(const auto* key:{"#str_229912","#str_229914","#str_229915","#str_200059"})Check(v.host.strings.contains(key),"every display row label is translated");
 Check(Shown(v,Device)=="none"&&Shown(v,Span)=="none","before the service publishes lists both rows stay hidden");
 OneDisplay(v);Stale(v);Several(v);Spanning(v);Unavailable(v);Guards(v);Fit(v,locale,expansion);Recreate(v,source);
 // Begin, Edit and Cancel, which the page's edits and Cancel reach, never write.
 Check(v.tx.Cancel(View::Owner).code==SettingsCode::Ok&&v.host.writes==0,"Cancel ends the display drafts without a write");
}
int main(int argc,char** argv) {
 Check(argc==3||argc==4,"page, language folder and optional locale");const auto source=Read(argv[1]);
 unsigned ran=0;
 for(const auto* locale:{"english","spanish","polish","russian","french","italian","german"}) {
  if(argc==4&&std::string(argv[3])!=locale)continue;
  for(float expansion:{1.f,1.4f})Run(source,argv[2],locale,expansion);
  ++ran;
 }
 Check(ran>0,"the named locale is one this test covers");
 Check(oversized>0,"some display card outgrows the scroll body, so its reveal is checked");
 std::printf("SYSTEM display lists: %u checks passed\n",checks);
}
