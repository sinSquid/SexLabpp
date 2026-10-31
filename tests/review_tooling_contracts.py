"""Real model export and Lua task callbacks; requires numpy, sklearn, pandas, joblib, lupa."""
import configparser
import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS
import tempfile
import unittest

import numpy as np
from lupa import LuaRuntime

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('review_export',ROOT/'scripts/ML/export.py')
export=importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)

class ToolContracts(unittest.TestCase):
    def test_softmax_keeps_independent_features_with_same_suffix(self):
        scaler=NS(mean_=np.array([1.,2.]),scale_=np.array([2.,3.]),feature_names_in_=np.array(['A_Distance','B_Distance']))
        clf=NS(classes_=np.array(['A','B','None']),coef_=np.array([[1.,2.],[-1.,-3.],[.5,.2]]),intercept_=np.array([.1,.2,.3]))
        model=NS(named_steps={'scaler':scaler,'clf':clf})
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'model.ini';export.export_softmax_model_to_ini(model,path)
            ini=configparser.ConfigParser();ini.read(path)
            self.assertEqual(set(ini['A']),{'bias','a_distance','b_distance'})
            for values in (np.array([2.,4.]),np.array([-1.,3.])):
                original=clf.coef_@((values-scaler.mean_)/scaler.scale_)+clf.intercept_
                actual=np.array([float(ini[c]['bias'])+float(ini[c]['a_distance'])*values[0]+float(ini[c]['b_distance'])*values[1] for c in clf.classes_])
                np.testing.assert_allclose(actual,original,rtol=1e-12,atol=1e-12)

    def test_real_sklearn_fit_and_export_predictions(self):
        import pandas as pd
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        rng=np.random.default_rng(810)
        values=rng.normal(size=(90,2))
        labels=np.where(values[:,0]>.5,'A',np.where(values[:,1]>.1,'B','None'))
        frame=pd.DataFrame(values,columns=['A_Distance','B_Distance'])
        fitted=make_pipeline(StandardScaler(),LogisticRegression(max_iter=1000)).fit(frame,labels)
        model=NS(named_steps={'scaler':fitted.named_steps['standardscaler'],'clf':fitted.named_steps['logisticregression']})
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'model.ini';export.export_softmax_model_to_ini(model,path)
            ini=configparser.ConfigParser();ini.read(path)
            scores=np.array([[float(ini[c]['bias'])+float(ini[c]['a_distance'])*x+float(ini[c]['b_distance'])*y for c in fitted.classes_] for x,y in values])
            probs=np.exp(scores-scores.max(axis=1,keepdims=True));probs/=probs.sum(axis=1,keepdims=True)
            np.testing.assert_allclose(probs,fitted.predict_proba(frame),rtol=1e-10,atol=1e-10)

    def lua(self):
        lua=LuaRuntime(unpack_returned_tuples=True)
        lua.execute('''
import=function()end
option={get=function(k)return ({target='SexLab.esm',install=true,installdir='override'})[k] end}
config={load=function()end}
table.wrap=function(v)return type(v)=='table' and v or {v} end
table.clone=function(v)local r={} for k,x in pairs(v)do r[k]=x end return r end
path={join=function(a,b)return a..'/'..b end}
project={target=function()return {installdir=function()return 'configured' end,targetdir=function()return 'dist' end,values=function()return 'source' end}end}
spriggit={load_meta=function()return {ModKey='SexLab.esm',GameRelease='SkyrimSE',PackageName='yaml',Version='1'}end}
find_tool=function()return {program='spriggit'}end
cprint=function()end
os.vrunv=function(program,args) captured=args end
''')
        return lua

    def test_serializer_honors_explicit_install_directory(self):
        lua=self.lua();lua.execute((ROOT/'xmake/spriggit/serialize.lua').read_text())
        lua.globals().main()
        self.assertEqual(lua.globals().captured[3],'override/SexLab.esm')

    def test_top_level_task_forwards_install_directory(self):
        lua=self.lua()
        lua.execute("on_run=function(f) run_task=f end;set_menu=function()end;task={run=function(name,args)if name=='spriggit.serialize'then forwarded=args end end}")
        block=(ROOT/'xmake.lua').read_text().split('task("serialize")',1)[1].split('task_end()',1)[0]
        lua.execute(block);lua.globals().run_task()
        self.assertEqual(lua.globals().forwarded.installdir,'override')

    def test_papyrus_rebuild_tracks_imported_scripts_and_flags(self):
        lua=LuaRuntime(unpack_returned_tuples=True)
        lua.execute('''
import=function()end
find_tool=function()return {program='compiler'}end
path={join=function(a,b)return a..'/'..b end,basename=function()return 'Child' end,
 absolute=function(p)return p end,normalize=function(p)return p end,
 extension=function()return '.psc' end,directory=function()return 'out' end}
os.projectdir=function()return '.' end
os.files=function(pattern)return {'includes/Parent.psc'}end
os.isfile=function(p)return p=='includes/TESV_Papyrus_Flags.flg' end
depend={on_changed=function(callback,options) tracked=options end}
local objects={}
target={targetdir=function()return 'out' end,data=function()return {flags='TESV_Papyrus_Flags.flg',optimize=false,anonymize=false}end,
 objectfiles=function()return objects end,get=function()return {'includes'}end,
 dependfile=function()return 'cache' end,is_rebuilt=function()return false end}
''')
        lua.execute((ROOT/'xmake/papyrus/papyrus.lua').read_text())
        lua.globals().on_build_file(lua.globals().target,'Child.psc',lua.table_from({'progress':0}))
        files=lua.globals().tracked.files
        actual={files} if isinstance(files,str) else set(files.values())
        self.assertTrue({'Child.psc','includes/Parent.psc','includes/TESV_Papyrus_Flags.flg'} <= actual,actual)

if __name__=='__main__':unittest.main()
