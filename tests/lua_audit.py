"""Parse all project Lua files and execute the XML-escaping helper (requires lupa)."""
import glob
import os
from pathlib import Path
from lupa import LuaRuntime

ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT)
lua=LuaRuntime(unpack_returned_tuples=True)
lua.globals().os.files=lambda pattern: lua.table_from(glob.glob(pattern.replace('**.', '**/*.'),recursive=True))
lua.globals().io.readfile=lambda path: Path(path).read_text(encoding='utf-8')
lua.execute((ROOT/'tests/lua_audit.lua').read_text())
lua.globals().main()
