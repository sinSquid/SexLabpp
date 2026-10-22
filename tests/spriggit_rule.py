"""Execute the actual Xmake configuration callback with two source directories."""
from pathlib import Path
from lupa import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute('''
local function noop(...) end
for _, name in ipairs({"add_moduledirs", "option", "set_category", "set_description",
    "on_check", "after_check", "option_end", "task", "on_run", "set_menu", "task_end",
    "rule", "add_imports", "on_buildcmd_file", "rule_end"}) do _G[name] = noop end
function on_config(callback) captured_config = callback end
table.wrap = function(v) return type(v) == "table" and v or {v} end
path = {join = function(a,b) return a .. "/" .. b end}
spriggit = {load_meta = function(dir) return {ModKey = dir .. ".esm"} end}
''')
lua.execute((ROOT / 'xmake/spriggit/xmake.lua').read_text())
lua.execute('''
local files, installs = {}, {}
local target = {
    values = function(self, key) assert(key == "spriggit.srcdir"); return {"one", "two"} end,
    targetdir = function() return "out" end,
    add = function(self, kind, value)
        if kind == "files" then table.insert(files, value)
        elseif kind == "installfiles" then table.insert(installs, value)
        else error("unexpected addition") end
    end
}
captured_config(target)
assert(#files == 2 and files[1] == "one" and files[2] == "two")
assert(#installs == 2 and installs[1] == "out/one.esm" and installs[2] == "out/two.esm")
''')
print('PASS: Spriggit adds each source directory once')
