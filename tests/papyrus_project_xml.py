"""Execute the actual project generator; target/xmake I/O are stand-ins."""
from pathlib import Path
from xml.etree import ElementTree
from lupa import LuaRuntime
ROOT=Path(__file__).resolve().parents[1]
lua=LuaRuntime(unpack_returned_tuples=True)
lua.execute(r'''
import=function()end
function string.startswith(s,p)return s:sub(1,#p)==p end
function string.endswith(s,p)return s:sub(-#p)==p end
option={get=function(k)return k=='target' and 'scripts' or '/out' end}
config={load=function()end};task={run=function()end}
path={absolute=function(p)return p end,normalize=function(p)return p end,relative=function(p)return p end,
translate=function(p)return p end,basename=function(p)return p end,directory=function(p)return '/source&A' end,
join=function(a,b)return a..'/'..b end}
os.projectdir=function()return '/' end
local target={}
function target:data()return {flags='Flags&A.flg',game='sse',optimize=true,anonymize=true}end
function target:basename()return 'scripts' end
function target:targetdir()return '/output&A' end
function target:get(key)return key=='includedirs' and {'/imports&A'} or {'/source&A/*.psc'} end
project={target=function()return target end}
lines={};io.open=function()return {print=function(_,s,...)lines[#lines+1]=string.format(s,...)end,close=function()end}end
''')
lua.execute((ROOT/'xmake/papyrus/project.lua').read_text())
lua.globals().main()
xml='\n'.join(lua.globals().lines.values())
root=ElementTree.fromstring(xml)
assert root.attrib['Flags']=='Flags&A.flg'
assert root.attrib['Output']=='/output&A'
assert root.find('{PapyrusProject.xsd}Imports')[0].text=='/imports&A'
assert root.find('{PapyrusProject.xsd}Folders')[0].text=='/source&A'
print('PASS: Papyrus project XML preserves ampersands in paths and flags')
