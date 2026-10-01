#!/usr/bin/env python3
"""Run the production retained target allocator against a counted renderer.

Checks mixed viewport sizes, the shared byte budget and non-destructive failed
allocation, and that layer composites sample GL row order on every backend,
which the Vulkan executor's render-texture contract (pinned below) provides.
No graphics device, game window or host input is accessed.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
from filesystem_case_segments import function_body

ROOT = Path(__file__).resolve().parents[2]
SUPPORT = r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cmath>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>
namespace openq4::ui {
struct Vertex {float x=0,y=0,u=0,v=0,r=1,g=1,b=1,a=1;};
struct Bounds {float x=0,y=0,width=0,height=0;};
}
struct idImageOpts {int width=0,height=0,format=0,numLevels=0;bool isPersistant=false;};
enum {FMT_RGBA8,TF_NEAREST,DS_DEFAULTED};
struct idImage {};
struct idMaterial {int GetState() const {return 1;}};
struct idRenderTexture {bool destroyed=false;};
struct Renderer {
    int creates=0,destroys=0,clears=0,defaultBinds=0;bool failImage=false;
    std::vector<std::unique_ptr<idImage>> images;
    std::vector<std::unique_ptr<idRenderTexture>> targets;
    idRenderTexture* bound=nullptr;
    idImage* CreateImage(const char*,idImageOpts*,int){
        ++creates;if(failImage)return nullptr;
        images.push_back(std::make_unique<idImage>());return images.back().get();
    }
    idRenderTexture* CreateRenderTexture(idImage*,void*){
        targets.push_back(std::make_unique<idRenderTexture>());return targets.back().get();
    }
    void DestroyRenderTexture(idRenderTexture* target){assert(target && !target->destroyed);target->destroyed=true;++destroys;}
    // Only a composite may bind the default target (null); allocation never does.
    void BindRenderTexture(idRenderTexture* target,void*){assert(!target || !target->destroyed);defaultBinds+=!target;bound=target;}
    void ClearRenderTarget(bool color,bool depth,int,float r,float g,float b,float a){assert(color && !depth && r==0 && g==0 && b==0 && a==0);++clears;}
} renderer;
Renderer* renderSystem=&renderer;
struct Declarations {idMaterial material;const idMaterial* FindMaterial(const char*){return &material;}} declarations;
Declarations* declManager=&declarations;
const char* va(const char* format,unsigned value){static char text[128];std::snprintf(text,sizeof text,format,value);return text;}
struct Host {
    struct Layer {idRenderTexture* target=nullptr;const idMaterial* material=nullptr;const idMaterial* maskMaterial=nullptr;int width=0,height=0;};
    std::vector<Layer> layers;
    int viewportWidth=1280,viewportHeight=720;
    std::vector<openq4::ui::Vertex> drawn;std::uintptr_t drawnMaterial=0;
    void Draw(const std::vector<openq4::ui::Vertex>& vertices,const std::vector<int>& indices,std::uintptr_t material){
        assert(indices.size()==6);drawn=vertices;drawnMaterial=material;
    }
'''
MAIN = r'''
};
int main(){
    Host host;
    assert(host.BeginLayer(1,1280,720));
    auto first=host.layers[0].target;
    assert(host.BeginLayer(2,800,600));
    auto second=host.layers[1].target;
    assert(host.layers[0].target==first && !first->destroyed && renderer.destroys==0);
    assert(host.BeginLayer(1,1280,720) && renderer.creates==2 && renderer.bound==first);
    assert(host.BeginLayer(1,640,480));
    assert(first->destroyed && renderer.destroys==1 && host.layers[1].target==second && !second->destroyed);
    const int created=renderer.creates,cleared=renderer.clears;
    auto resized=host.layers[0].target;
    assert(!host.BeginLayer(0,100,100) && !host.BeginLayer(49,100,100));
    assert(!host.BeginLayer(3,0,100) && !host.BeginLayer(3,100,-1));
    assert(!host.BeginLayer(3,8192,8192)); // Existing targets count toward the 256 MiB cap.
    assert(!host.BeginLayer(1,8192,8192)); // Budget failure must not destroy this old target.
    assert(renderer.creates==created && renderer.clears==cleared);
    assert(host.layers[0].target==resized && !resized->destroyed && !second->destroyed);
    assert(host.BeginLayer(3,4096,4096));
    renderer.failImage=true;
    assert(!host.BeginLayer(4,320,200));
    assert(host.layers[0].target==resized && !resized->destroyed && !second->destroyed);
    renderer.failImage=false;
    Host empty;
    assert(empty.BeginLayer(48,8192,8192)); // Sparse slot ID is not a memory multiplier.
    assert(!empty.BeginLayer(1,1,1));
    // Composites sample every backend's layers in GL row order: the view's
    // top row is v=1. Sampling Vulkan layers top-origin mirrored them onto
    // empty rows, so every faded or masked element vanished there.
    assert(renderer.defaultBinds==0);
    const auto near=[](float a,float b){return std::fabs(a-b)<1e-5f;};
    host.CompositeLayer(2,0,.5f,{100,200,300,50});
    assert(renderer.defaultBinds==1 && renderer.bound==nullptr && host.drawn.size()==4);
    assert(host.drawnMaterial==reinterpret_cast<std::uintptr_t>(host.layers[1].material));
    assert(near(host.drawn[0].y,200) && near(host.drawn[0].u,100.f/1280) && near(host.drawn[0].v,1-200.f/720));
    assert(near(host.drawn[2].y,250) && near(host.drawn[2].u,400.f/1280) && near(host.drawn[2].v,1-250.f/720));
    for (const auto& vertex : host.drawn) assert(near(vertex.r,.5f) && near(vertex.a,.5f)); // Premultiplied opacity.
    host.MaskLayer(1,2,{0,0,1280,720});
    assert(renderer.bound==host.layers[1].target && near(host.drawn[0].v,1) && near(host.drawn[2].v,0) && near(host.drawn[0].a,1));
    std::puts("retained layer pool: mixed viewport preservation, exact shared byte budget, failure isolation and GL-order composites passed");
}
'''


DRAW_SUPPORT = r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
typedef unsigned char byte;
typedef int glIndex_t;
namespace openq4::ui { struct Vertex {float x=0,y=0,u=0,v=0,r=1,g=1,b=1,a=1;}; }
struct idVec3 {float x=0,y=0,z=0; void Set(float a,float b,float c){x=a;y=b;z=c;}};
struct idVec2 {float x=0,y=0; void Set(float a,float b){x=a;y=b;}};
struct idDrawVert {idVec3 xyz; idVec2 st; idVec3 normal; idVec3 tangents[2]; byte color[4]={}; byte color2[4]={}; void Clear(){*this=idDrawVert{};}};
template<class T> struct idList {std::vector<T> items; void SetNum(int n){items.resize(n);} T& operator[](int i){return items[i];} T* Ptr(){return items.data();}};
template<class T> T Min(T a,T b){return a<b?a:b;}
struct idStr {static int Icmpn(const char* a,const char* b,int n){return std::strncmp(a,b,n);} static int Icmp(const char* a,const char* b){return std::strcmp(a,b);}};
struct idMath {static float ClampFloat(float low,float high,float value){return value<low?low:value>high?high:value;}};
struct idMaterial {std::string name; const char* GetName() const {return name.c_str();}};
struct Renderer {
    std::vector<idDrawVert> drawn; const idMaterial* material=nullptr;
    void SetColor4(float,float,float,float){}
    void DrawStretchPic(const idDrawVert* vertices,const glIndex_t*,int count,int,const idMaterial* used,bool){drawn.assign(vertices,vertices+count);material=used;}
} renderer;
Renderer* renderSystem=&renderer;
struct Declarations {idMaterial solid{"_retainedSolid"}; const idMaterial* FindMaterial(const char*){return &solid;}} declarations;
Declarations* declManager=&declarations;
struct Host {
    int viewportWidth=1280,viewportHeight=720;
'''
DRAW_MAIN = r'''
};
int main(){
    // Half-tinted premultiplied quad: rgb and a at 0.5.
    std::vector<openq4::ui::Vertex> quad(4);
    for (auto& vertex : quad) {vertex.r=vertex.g=vertex.b=vertex.a=.5f;}
    const std::vector<int> indices{0,1,2,0,2,3};
    Host host;
    idMaterial additive{"_retainedAdd/gfx/guis/mainmenu/q4text"},picture{"_retained/gfx/guis/mainmenu/level_mcc"};
    // Additive light keeps its premultiplied tint and carries no coverage, so
    // it never writes a composition layer's alpha (an opaque box on composite).
    host.Draw(quad,indices,reinterpret_cast<std::uintptr_t>(&additive));
    assert(renderer.material==&additive && renderer.drawn.size()==6);
    for (const auto& vertex : renderer.drawn) assert(vertex.color[0]==128 && vertex.color[3]==0);
    // A straight image is unpremultiplied and keeps its coverage.
    host.Draw(quad,indices,reinterpret_cast<std::uintptr_t>(&picture));
    for (const auto& vertex : renderer.drawn) assert(vertex.color[0]==255 && vertex.color[3]==128);
    std::puts("retained host draw: additive pictures write no coverage, straight images keep theirs");
}
'''


def main():
    source=(ROOT/'src/ui/RetainedUI.cpp').read_text()
    source_text=source
    bodies=[function_body(source,signature).replace(' override','') for signature in (
        'bool BeginLayer(','void CompositeLayer(','void MaskLayer(','void DrawLayer(')]
    # The Vulkan executor's side of the row-order contract the composites rely on.
    executor=(ROOT/'src/renderer/Vulkan/vk_GuiExecutor.cpp').read_text(encoding='utf-8')
    assert 'vkExec.activePipelineTarget.lowerOrigin = true;' in function_body(executor,'bool VK_Exec_SetRenderTarget('),\
        'Vulkan render textures must keep GL row order, which retained layer composites sample'
    assert 'VK_Exec_MarkCanonicalWrites();' in function_body(executor,'void VK_GuiExecutor_Draw2DView('),\
        '2D writes into a layer must be marked as canonical rows'
    assert 'passPlan.textureFlipY = imageEntry->materialSampleFlipY;' in executor,\
        'GUI stages must flip an image written in the other row order'
    code=SUPPORT+'\n'.join(bodies)+MAIN
    compiler=next((found for name in ('clang++','g++','c++') if (found:=shutil.which(name))),None)
    if not compiler:
        raise RuntimeError('C++ compiler required')
    (ROOT/'.tmp').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ui-layer-pool-',dir=ROOT/'.tmp') as temp:
        source=Path(temp)/'pool.cpp';binary=Path(temp)/'pool.exe'
        source.write_text(code,encoding='utf-8')
        subprocess.run([compiler,'-std=c++17',str(source),'-o',str(binary)],check=True)
        subprocess.run([str(binary)],check=True)
        draw=Path(temp)/'draw.cpp';drawBinary=Path(temp)/'draw.exe'
        draw.write_text(DRAW_SUPPORT+function_body(source_text,'void Draw(').replace(' override','')+DRAW_MAIN,encoding='utf-8')
        subprocess.run([compiler,'-std=c++17',str(draw),'-o',str(drawBinary)],check=True)
        subprocess.run([str(drawBinary)],check=True)


if __name__=='__main__':
    main()
