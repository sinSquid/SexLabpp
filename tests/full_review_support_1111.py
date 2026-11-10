"""Maintenance regressions: real Python/Lua helpers; native source contracts.

No compiler, build or deployment. Use --lua-runtime-dir for an installed lupa
runtime and --xmake-depend-lua for the installed Xmake dependency module. Missing
optional runtimes/source files are explicitly skipped.
"""
from pathlib import Path
import argparse
import contextlib
import io
import re
import runpy
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--lua-runtime-dir', type=Path)
parser.add_argument('--xmake-depend-lua', type=Path)
options = parser.parse_args()
if options.lua_runtime_dir:
    sys.path.insert(0, str(options.lua_runtime_dir))
try:
    from lupa import LuaRuntime
except ImportError:
    LuaRuntime = None


def body(path, signature):
    text = (ROOT / path).read_text(encoding='utf-8-sig')
    start = text.index(signature)
    start = text.index('{', start)
    end, depth = start + 1, 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


class SupportRegressions(unittest.TestCase):
    def test_translation_preserves_existing_languages_and_bom(self):
        for bom in (False, True):
            with self.subTest(bom=bom), tempfile.TemporaryDirectory() as tmp:
                d = Path(tmp) / 'Translations'
                d.mkdir()
                script = d / 'translate.py'
                script.write_bytes((ROOT / 'dist/Interface/Translations/translate.py').read_bytes())
                encoding = 'utf-16' if bom else 'utf-16le'
                english = '$A\tEnglish {0}\n$B\tAdded %s\n'
                (d / 'SexLab_ENGLISH.txt').write_text(english, encoding=encoding)
                for lang in ('CHINESE', 'RUSSIAN', 'SPANISH', 'JAPANESE'):
                    (d / f'SexLab_{lang}.txt').write_text('$A\t原译文 {0}\n', encoding=encoding)
                with contextlib.redirect_stdout(io.StringIO()):
                    runpy.run_path(str(script), run_name='__main__')
                for lang in ('CHINESE', 'RUSSIAN', 'SPANISH', 'JAPANESE'):
                    raw = (d / f'SexLab_{lang}.txt').read_bytes()
                    text = raw.decode(encoding)
                    self.assertIn('$A\t原译文 {0}', text)
                    self.assertIn('$B\tAdded %s', text)
                    self.assertEqual(raw.startswith(b'\xff\xfe'), bom)
                self.assertEqual((d / 'SexLab_FRENCH.txt').read_bytes(), (d / 'SexLab_ENGLISH.txt').read_bytes())
                self.assertEqual((d / 'SexLab_ENGLISH.txt').read_text(encoding=encoding), english)

    def test_translation_repeat_run_keeps_existing_and_todo_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / 'Translations'
            d.mkdir()
            script = d / 'translate.py'
            script.write_bytes((ROOT / 'dist/Interface/Translations/translate.py').read_bytes())
            (d / 'SexLab_ENGLISH.txt').write_text('# TODO: $A\n$A\tNew {0}\n$B\tOther %s\n', encoding='utf-16le')
            (d / 'SexLab_CHINESE.txt').write_text('$A\t已译 {0}\n', encoding='utf-16le')
            for _ in range(2):
                with contextlib.redirect_stdout(io.StringIO()):
                    runpy.run_path(str(script), run_name='__main__')
            text = (d / 'SexLab_CHINESE.txt').read_text(encoding='utf-16le')
            self.assertIn('$A\t已译 {0}', text)
            self.assertIn('$B\tOther %s', text)

    def test_translation_keeps_crlf_and_separates_unterminated_existing_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / 'Translations'
            d.mkdir()
            script = d / 'translate.py'
            script.write_bytes((ROOT / 'dist/Interface/Translations/translate.py').read_bytes())
            (d / 'SexLab_ENGLISH.txt').write_bytes('$A\tOriginal\r\n$B\tAdded\r\n'.encode('utf-16le'))
            (d / 'SexLab_CHINESE.txt').write_bytes('$A\t译文'.encode('utf-16le'))
            with contextlib.redirect_stdout(io.StringIO()):
                runpy.run_path(str(script), run_name='__main__')
            text = (d / 'SexLab_CHINESE.txt').read_bytes().decode('utf-16le')
            self.assertIn('$A\t译文\r\n# TODO: $B\r\n$B\tAdded\r\n', text)

    def test_form_lookup_rejects_partial_numeric_prefix(self):
        code = body('src/Util/FormLookup.h', 'RE::FormID FormFromString(')
        self.assertIn('ptr != formIdStr.data() + formIdStr.size()', code)
        self.assertIn('base < 2 || base > 36', code)

    def test_data_config_errors_are_contained(self):
        code = body('src/UserData/Settings.cpp', 'void Settings::InitializeData()')
        self.assertIn('try {', code)
        self.assertIn('catch (const std::exception&', code)
        self.assertIn('SOS_ExcludeFactions.swap(', code)

    def test_strip_state_all_owners_synchronized(self):
        signatures = ('void StripData::AddArmor(', 'void StripData::RemoveArmor(',
                      'void StripData::RemoveArmorAll()', 'void StripData::Load()',
                      'void StripData::Save()', 'Strip StripData::CheckStrip(')
        for signature in signatures:
            with self.subTest(signature=signature):
                code = body('src/UserData/StripData.cpp', signature)
                self.assertRegex(code, r'std::(?:unique_lock|shared_lock|lock_guard) lock\{ _mutex \}')

    @unittest.skipIf(LuaRuntime is None, 'lupa runtime not installed; native compiler not used')
    def test_lua_dependencies_transitive_cycle_and_reselection(self):
        module = ROOT / 'xmake/papyrus/modules/papyrus/dependencies.lua'
        self.assertTrue(module.is_file(), 'dependency traversal module missing')
        lua = LuaRuntime(unpack_returned_tuples=True)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            primary, fallback = root / 'primary', root / 'fallback'
            primary.mkdir()
            fallback.mkdir()
            (primary / 'A.psc').write_text('Scriptname A extends B\nimport C\nD Property value Auto', encoding='utf-8')
            (primary / 'B.psc').write_text('Scriptname B extends D', encoding='utf-8')
            (primary / 'C.psc').write_text('Scriptname C\nA property cycle Auto', encoding='utf-8')
            (primary / 'D.psc').write_text('Scriptname D', encoding='utf-8')
            (primary / 'Unrelated.psc').write_text('Scriptname Unrelated', encoding='utf-8')
            (fallback / 'B.psc').write_text('Scriptname B\nUnrelated Property other Auto', encoding='utf-8')
            lua.globals().os.files = lambda pattern: lua.table_from([str(p) for p in sorted(Path(pattern).parent.glob(Path(pattern).name))])
            lua.globals().io.readfile = lambda path: Path(path).read_text(encoding='utf-8')
            lua.globals().path = lua.table_from(dict(join=lambda a, b: str(Path(a) / b),
                                                   basename=lambda p: Path(p).stem,
                                                   absolute=lambda p: str(Path(p).absolute()),
                                                   normalize=lambda p: str(Path(p))))
            lua.execute(module.read_text(encoding='utf-8'))
            dirs = lua.table_from([str(primary), str(fallback)])
            index = lua.globals().build_index(dirs)
            values = list(lua.globals().main(str(primary / 'A.psc'), index).values())
            self.assertEqual(set(values), {str(primary / name) for name in ['A.psc', 'B.psc', 'C.psc', 'D.psc']})
            # Removing the shadowing include changes both selected file and its closure.
            (primary / 'B.psc').unlink()
            index = lua.globals().build_index(dirs)
            values = list(lua.globals().main(str(primary / 'A.psc'), index).values())
            self.assertIn(str(fallback / 'B.psc'), values)
            self.assertIn(str(primary / 'Unrelated.psc'), values)

    def test_papyrus_cache_inputs_include_tool_and_flags(self):
        text = (ROOT / 'xmake/papyrus/papyrus.lua').read_text(encoding='utf-8')
        self.assertIn('dependencies.build_index(', text)
        self.assertIn('dependencies(sourcefile,', text)
        self.assertIn('compiler.program', text[text.index('dependfile ='):])
        self.assertIn('papyrus.flags', text[text.index('dependfile ='):])
        self.assertIn('table.concat(target:get("includedirs"), ";")', text[text.index('dependfile ='):])

    @unittest.skipIf(LuaRuntime is None, 'lupa runtime not installed; native compiler not used')
    def test_actual_lua_build_hook_captures_dependency_inputs(self):
        lua = LuaRuntime(unpack_returned_tuples=True)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            compiler = root / 'PapyrusCompiler.exe'
            compiler.write_bytes(b'not executed')
            flags = root / 'TESV_Papyrus_Flags.flg'
            flags.write_text('flags', encoding='utf-8')
            source = root / 'A.psc'
            source.write_text('Scriptname A extends B', encoding='utf-8')
            parent = root / 'B.psc'
            parent.write_text('Scriptname B', encoding='utf-8')
            lua.globals().os.files = lambda pattern: lua.table_from([str(p) for p in Path(pattern).parent.glob(Path(pattern).name)])
            lua.globals().os.isfile = lambda p: Path(p).is_file()
            lua.globals().os.projectdir = lambda: str(ROOT)
            lua.globals().io.readfile = lambda p: Path(p).read_text(encoding='utf-8')
            lua.globals().path = lua.table_from(dict(join=lambda a, b: str(Path(a) / b),
                                                   basename=lambda p: Path(p).stem,
                                                   extension=lambda p: Path(p).suffix,
                                                   directory=lambda p: str(Path(p).parent),
                                                   absolute=lambda p, *args: str(Path(p).absolute()),
                                                   normalize=lambda p: str(Path(p))))
            lua.execute((ROOT / 'xmake/papyrus/modules/papyrus/dependencies.lua').read_text(encoding='utf-8'))
            lua.globals().includes = lua.table_from([str(root)])
            lua.globals().compiler_path = str(compiler)
            lua.globals().target_dir = str(root / 'out')
            lua.execute('''
                dependency_module = {build_index=build_index}
                setmetatable(dependency_module, {__call=function(_, ...) return main(...) end})
                function import(name)
                    if name == "papyrus.dependencies" then return dependency_module end
                end
                function find_tool(_) return {program=compiler_path} end
                function table.join(a,b)
                    local t={} for _,v in ipairs(a) do t[#t+1]=v end
                    for _,v in ipairs(b) do t[#t+1]=v end return t
                end
                depend={on_changed=function(fn, opt) captured=opt end}
                local index=build_index(includes)
                target={}
                function target:data(key)
                    if key=="papyrus" then return {flags="TESV_Papyrus_Flags.flg",optimize=false,anonymize=false} end
                    return index
                end
                function target:get(_) return includes end
                function target:targetdir() return target_dir end
                function target:objectfiles() return {} end
                function target:dependfile(file) return file..".d" end
                function target:is_rebuilt() return false end
            ''')
            lua.execute((ROOT / 'xmake/papyrus/papyrus.lua').read_text(encoding='utf-8'))
            lua.globals().on_build_file(lua.globals().target, str(source), lua.table_from({}))
            captured = lua.globals().captured
            files = set(captured['files'].values())
            self.assertTrue({str(source), str(parent), str(flags), str(compiler)} <= files)
            values = list(captured['values'].values())
            self.assertIn(str(compiler), values)
            self.assertIn(str(root), values)
            self.assertIn('TESV_Papyrus_Flags.flg', values)
            self.assertEqual(values[-2:], ['optimize=false', 'anonymize=false'])

    @unittest.skipIf(LuaRuntime is None or options.xmake_depend_lua is None,
                     'pass lupa runtime and --xmake-depend-lua to exercise installed Xmake comparison')
    def test_flag_changes_invalidate_with_actual_xmake_comparator(self):
        # Use the installed comparison function, not an invented equality model.
        # The rest of Xmake is not run: all file mtimes are held unchanged and no
        # compiler/build callback is invoked.
        actual = options.xmake_depend_lua.read_text(encoding='utf-8-sig')
        comparator = re.search(r'(?ms)^function is_changed\(.*?^end\s*$', actual)
        self.assertIsNotNone(comparator, 'installed Xmake is_changed function not found')
        production = (ROOT / 'xmake/papyrus/papyrus.lua').read_text(encoding='utf-8')
        values = re.search(r'(?ms)^        values = \{(.*?)^        \},', production)
        self.assertIsNotNone(values, 'production dependency values not found')
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute('''
            _g = {}
            function table.wrap(value) return value or {} end
            function _is_show_diagnosis_info() return false end
            function os.mtime(_) return 1 end
        ''')
        lua.execute(comparator[0])
        make_values = lua.eval('''function(optimize, anonymize)
            local papyrus = {flags="flags", optimize=optimize, anonymize=anonymize}
            local compiler = {program="compiler"}
            local target = {get=function() return {"include"} end}
            local depfiles = {"source.psc"}
            return {''' + values[1] + '''}
        end''')
        files = lua.table_from(['source.psc'])
        for old in ((False, False), (False, True), (True, False), (True, True)):
            for new in ((False, False), (False, True), (True, False), (True, True)):
                with self.subTest(old=old, new=new):
                    before = lua.table_from(dict(files=files, values=make_values(*old)))
                    after = lua.table_from(dict(files=files, values=make_values(*new), lastmtime=2))
                    self.assertEqual(bool(lua.globals().is_changed(before, after)), old != new)


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]], verbosity=2)
