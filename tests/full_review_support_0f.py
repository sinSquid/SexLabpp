"""No-compiler configuration/save/output-existence repair checks.

The PEX case runs production hook options and installed Xmake dependency logic
with an inert callback, not a build. Native settings checks are source contracts.
"""
from pathlib import Path
import argparse
import ast
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--lua-runtime-dir', type=Path)
parser.add_argument('--xmake-depend-lua', type=Path)
options = parser.parse_args()


def source(path):
    return (ROOT / path).read_text(encoding='utf-8-sig')


def body(path, signature):
    text = source(path)
    start = text.index('{', text.index(signature))
    end, depth = start + 1, 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


class SupportRepairs(unittest.TestCase):
    def test_settings_scalar_storage_and_serialization(self):
        header = source('src/UserData/Settings.h')
        self.assertIn('using Type = std::atomic<T>', header)
        self.assertIn('static inline Storage<decltype(DEFAULT)> STR', header)
        self.assertIn('std::atomic<float>*', header)
        self.assertIn('std::atomic<int>*', header)
        self.assertIn('std::atomic<bool>*', header)
        save = body('src/UserData/Settings.cpp', 'void Settings::Save()')
        self.assertIn('const auto lock = Lock()', save)
        self.assertIn('settings[#STR] = Read(STR)', save)
        load = body('src/UserData/Settings.cpp', 'void Settings::InitializeYAML()')
        self.assertIn('decltype(Settings::Read(a_out))', load)
        self.assertIn('yaml[a_key].as<Value>()', load)

    def test_compound_settings_readers_and_writers_share_lock(self):
        path = 'src/Papyrus/sslSystemConfig.cpp'
        for name in ['GetSettingStr', 'GetSettingIntA', 'GetSettingFltA',
                     'SetSettingStr', 'SetSettingIntA', 'SetSettingFltA']:
            with self.subTest(name=name):
                self.assertIn('Settings::Lock()', body(path, name + '('))
        get = body(path, 'GetSetting(VM*')
        self.assertIn('Settings::Storage<std::remove_pointer_t<T>>*', get)

    def test_save_jobs_are_serialized(self):
        handler = source('src/main.cpp').split('case SKSE::MessagingInterface::kSaveGame:', 1)[1].split('break;', 1)[0]
        self.assertIn('Util::AsyncIO::Submit(', handler)
        self.assertNotIn('.detach()', handler)
        self.assertLess(handler.index('Settings::Save()'), handler.index('Library::GetSingleton()->Save()'))
        self.assertIn('auto task = std::move(_tasks.front())', source('src/Util/AsyncIO.cpp'))

    @unittest.skipIf(options.lua_runtime_dir is None or options.xmake_depend_lua is None,
                     'pass Lua runtime and installed Xmake depend.lua to run the real dependency logic')
    def test_deleted_pex_forces_rebuild_but_present_output_does_not(self):
        # Reuse the fixture that captures the actual on_build_file options,
        # then feed them into the installed on_changed implementation.
        support = source('tests/full_review_support_1111.py')
        tree = ast.parse(support)
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                      and n.name == 'test_actual_lua_build_hook_captures_dependency_inputs')
        method.decorator_list = []
        code = ast.unparse(method) + '''
        installed = DEPEND.read_text(encoding='utf-8')
        lua.execute("_g={}; function table.wrap(v) return v or {} end; function _is_show_diagnosis_info() return false end; function os.mtime(_) return 1 end; function load(_) return previous_metadata end; function save(...) end; function table.join2(a,b) for _,v in ipairs(b) do a[#a+1]=v end return a end")
        lua.execute(re.search(r'(?ms)^function is_changed\\(.*?^end\\s*$', installed)[0])
        lua.execute(re.search(r'(?ms)^function on_changed\\(.*?^end\\s*$', installed)[0])
        lua.execute("previous_metadata={files=captured.files,values=captured.values}; requests=0; on_changed(function() requests=requests+1 end,captured)")
        self.assertEqual(lua.globals().requests, 1, 'missing PEX was skipped')
        output = root / 'out' / 'A.pex'
        output.parent.mkdir()
        output.write_bytes(b'present output, not executed')
        lua.globals().on_build_file(lua.globals().target, str(source), lua.table_from({}))
        lua.execute("requests=0; on_changed(function() requests=requests+1 end,captured)")
        self.assertEqual(lua.globals().requests, 0, 'unchanged present output rebuilt needlessly')
'''
        scope = dict(__file__=str(ROOT / 'tests/full_review_support_1111.py'), DEPEND=options.xmake_depend_lua)
        previous = sys.argv
        try:
            sys.argv = ['fixture', '--lua-runtime-dir', str(options.lua_runtime_dir)]
            exec(support[:support.index("if __name__ == '__main__':")], scope)
        finally:
            sys.argv = previous
        exec(code, scope)
        scope['test_actual_lua_build_hook_captures_dependency_inputs'](self)


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]], verbosity=2)
