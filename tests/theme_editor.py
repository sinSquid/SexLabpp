"""Run the actual editor entry with bad edits; engine UI calls are stand-ins."""
from source_regressions import ROOT, function, run
source=(ROOT/'src/Thread/Interface/Elements/ElementCtrlPanel.cpp').read_text()
code=r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <limits>
#include <utility>
namespace ImGuiMCP {
struct ImVec2 {float x{},y{};};struct ImVec4{};
struct IO {ImVec2 DisplaySize{1920,1080};};IO* GetIO(){static IO io;return &io;}
struct Style {ImVec2 WindowPadding;float ScrollbarSize=1;};Style* GetStyle(){static Style s;return &s;}
int GetFont(){return 0;}
constexpr int ImGuiCond_Appearing=0,ImGuiWindowFlags_NoCollapse=1,ImGuiWindowFlags_AlwaysAutoResize=2,ImGuiCol_Text=3;
void SetNextWindowPos(ImVec2,int,ImVec2){}void SetNextWindowSizeConstraints(ImVec2,ImVec2){}
bool Begin(const char*,bool*,int){return true;}void End(){}void PushStyleColor(int,ImVec4){}void PopStyleColor(){}void SetWindowFontScale(float){}
}
namespace UI {
struct Scale {float Px(float v){return v;}float TextPx(float v){return v;} };
namespace Theme {
struct Data {float value=1;};Data data;int validations=0;
struct GeometryT {float panelTabWidth=1,panelTabGap=1;};GeometryT Geometry;
struct SpacingT {float sm=1;};SpacingT Spacing;
struct FontT {float body=12;};FontT FontSize;
struct ColorT {int textSecondary=0;};ColorT Color;
ImGuiMCP::ImVec4 ToVec4(int){return {};}
// The real validator's individual fields have their own boundary tests. Here
// count invocations and apply a minimal equivalent domain to check UI publication.
void Validate(Data& d){++validations;if(!std::isfinite(d.value)||d.value<=0||d.value>10000)d.value=1;}
}
}
struct SceneHUD {UI::Scale scale;UI::Scale& GetScale(){return scale;} };
struct ElementCtrlPanel {bool _showThemeEditor=true;void RenderThemeEditor(SceneHUD&);};
void SetWindowFontSize(float){}
float MeasureThemeFieldsWidth(UI::Theme::Data&,int,float,const ImGuiMCP::Style&){return 100;}
float edited=0;
void DrawThemeFields(UI::Theme::Data& value){value.value=edited;}
'''
code+=function(source,'void ElementCtrlPanel::RenderThemeEditor(')
code+=r'''
int main(){SceneHUD hud;ElementCtrlPanel editor;
 for(float bad:{0.f,-1.f,std::numeric_limits<float>::quiet_NaN(),std::numeric_limits<float>::infinity(),std::numeric_limits<float>::max()}){
  edited=bad;UI::Theme::data.value=2;UI::Theme::validations=0;
  editor.RenderThemeEditor(hud);assert(UI::Theme::data.value==1);
 }
 edited=4;editor.RenderThemeEditor(hud);assert(UI::Theme::data.value==4);
 editor._showThemeEditor=false;edited=0;editor.RenderThemeEditor(hud);assert(UI::Theme::data.value==4);
}
'''
run('theme_editor',code)
print('PASS: editor validates bad edits before publishing and preserves valid edits')
