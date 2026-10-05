"""Execute production Lua with xmake 2.9.5's real dependency detector.
Requires lupa and XMAKE_DEPEND_SOURCE pointing to the pinned upstream depend.lua.
Compiler, filesystem timestamps and target are stand-ins, not a Windows build.
"""
from pathlib import Path
import hashlib
import os
from lupa import LuaRuntime
ROOT=Path(__file__).resolve().parents[1]
upstream=Path(os.environ['XMAKE_DEPEND_SOURCE'])
lua=LuaRuntime(unpack_returned_tuples=True)
lua.execute(r'''
_g={}; import=function()end
project={policy=function()return false end};cache={};times={};existing={};includeFiles={"inc/B.psc","inc/A.psc","inc/TESV_Papyrus_Flags.flg"};runs=0
function table.wrap(t)if type(t)=="table"then return t else return {t}end end
function table.join2(t,...)for _,a in ipairs({...})do if type(a)=="table"then for _,v in ipairs(a)do t[#t+1]=v end else t[#t+1]=a end end return t end
function table.unique(t)local out,seen={},{};for _,v in ipairs(t)do if not seen[v]then seen[v]=true;out[#out+1]=v end end return out end
os.isfile=function(f)return existing[f]==true end
os.mtime=function(f)return times[f]or 0 end
os.tmpfile=function()return "tmp"end
os.mkdir=function()end
os.files=function(pattern)local out={};for _,p in ipairs(includeFiles)do if (pattern:sub(-5)=="*.psc"and p:sub(-4)==".psc")or(pattern:sub(-5)=="*.flg"and p:sub(-4)==".flg")then out[#out+1]=p end end return out end
os.vexecv=function()runs=runs+1;existing["dist/A.pex"]=true;return 0 end
os.rm=function()end
io.readfile=function()return ""end
io.load=function(f)return cache[f]end
io.save=function(f,v)cache[f]=v;times[f]=100;existing[f]=true end
try=function(t)return t[1]()end
path={join=function(a,b)return a.."/"..b end,basename=function()return "A"end,absolute=function(p)return p end,normalize=function(p)return p end,directory=function(p)return "dist"end,extension=function(p)return ".psc"end}
os.projectdir=function()return "."end
find_tool=function()return {program="compiler.exe"}end
progress={show=function()end}
target={config={flags="TESV_Papyrus_Flags.flg",optimize=true,anonymize=false},objects={}}
function target:data()return self.config end
function target:targetdir()return "dist"end
function target:objectfiles()return self.objects end
function target:get()return {"inc"}end
function target:dependfile()return "A.d"end
function target:is_rebuilt()return false end
for _,f in ipairs({"A.psc","compiler.exe","inc/A.psc","inc/B.psc","inc/TESV_Papyrus_Flags.flg"})do existing[f]=true;times[f]=1 end
''')
lua.execute(upstream.read_text())
lua.execute('depend={on_changed=on_changed}; _g={};')
lua.execute((ROOT/'xmake/papyrus/papyrus.lua').read_text())
lua.execute(r'''
function build()_g={};on_build_file(target,"A.psc",{progress=1})end
build();assert(runs==1);build();assert(runs==1)
existing["dist/A.pex"]=false;build();assert(runs==2)
times["inc/B.psc"]=101;build();assert(runs==3);times["inc/B.psc"]=1
includeFiles[#includeFiles+1]="inc/New.psc";times["inc/New.psc"]=1;existing["inc/New.psc"]=true;build();assert(runs==4)
table.remove(includeFiles);build();assert(runs==5)
target.config.optimize=false;build();assert(runs==6);build();assert(runs==6)
target.config.anonymize=true
-- Replace import only for the anonymizer callback.
import=function(name)if name=="papyrus.anonymize"then return function()end end end
build();assert(runs==7);build();assert(runs==7)
target.config.flags="other.flg";build();assert(runs==8)
print("PASS: Lua dependency detector: no-op, missing PEX, include edits/add/delete, flags, optimize, anonymize")
''')
print('xmake v2.9.5 upstream depend.lua SHA256:',hashlib.sha256(upstream.read_bytes()).hexdigest())
# Parse and execute the actual spriggit callback with target/command stand-ins.
lua.execute(r'''
function rule()end;function rule_end()end;function add_moduledirs()end;function add_imports()end
function option()end;function option_end()end;function set_category()end;function set_description()end
function on_check()end;function after_check()end;function task()end;function on_run()end;function set_menu()end;function task_end()end;function on_config()end
function on_buildcmd_file(fn)spriggit_build=fn end
path=setmetatable(path,{__call=function(_,p)return p end})
spriggit={load_meta=function()return {ModKey="SexLab.esm"}end}
batch={files={},values={}}
function batch:show_progress()end;function batch:vrunv()end
function batch:add_depfiles(files)table.join2(self.files,table.wrap(files))end
function batch:add_depvalues(...)table.join2(self.values,{...})end
function batch:set_depmtime(t)self.mtime=t end
function batch:set_depcache(f)self.cache=f end
function target:add()end
os.files=function()return {"res/B.yaml","res/A.yaml"}end
spriggit_build=nil
''')
lua.execute((ROOT/'xmake/spriggit/xmake.lua').read_text())
lua.execute(r'''
spriggit_build(target,batch,"res",{progress=1})
assert(batch.files[1]=="res/A.yaml"and batch.files[2]=="res/B.yaml"and batch.files[3]=="compiler.exe")
assert(batch.values[1]=="res/A.yaml;res/B.yaml"and batch.values[2]=="compiler.exe")
assert(batch.mtime==0) -- missing output forces the upstream detector's lastmtime=0 path.
print("PASS: spriggit callback tracks source membership/tool and missing output timestamp")
''')
