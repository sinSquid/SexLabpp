"""Binary coefficient representation tested independently against logistic probabilities."""
import ast
import configparser
from pathlib import Path
from types import SimpleNamespace as NS
import tempfile
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
tree=ast.parse((ROOT/'scripts/ML/export.py').read_text())
tree.body=[n for n in tree.body if isinstance(n, ast.FunctionDef)]
env=dict(np=np,configparser=configparser,Path=Path)
exec(compile(tree,'export.py','exec'),env)
with tempfile.TemporaryDirectory() as directory:
    path=Path(directory)/'model.ini'
    for mode in ('auto','multinomial'):
        clf=NS(classes_=np.array(['a','b']),coef_=np.array([[2.0]]),intercept_=np.array([.5]),multi_class=mode)
        model=NS(named_steps=dict(scaler=NS(mean_=np.array([3.]),scale_=np.array([2.]),feature_names_in_=np.array(['p_value'])),clf=clf))
        env['export_softmax_model_to_ini'](model,path)
        ini=configparser.ConfigParser();ini.read(path)
        for x in (-2.,0.,3.,7.):
            scores=np.array([float(ini[c]['bias'])+float(ini[c]['value'])*x for c in ('a','b')])
            probs=np.exp(scores-scores.max());probs/=probs.sum()
            z=2*(x-3)/2+.5
            expected=1/(1+np.exp(-(2 if mode=='multinomial' else 1)*z))
            assert np.isclose(probs[1],expected)
print('PASS: binary logistic and explicit multinomial coefficient export')
