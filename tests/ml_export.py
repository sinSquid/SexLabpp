"""Numerical export parity against sklearn and the production C++ cluster predictor."""
import configparser
from pathlib import Path
import subprocess
import sys
import tempfile
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from source_regressions import function, run, ROOT
sys.path.insert(0, str(ROOT / 'scripts/ML'))
from export import export_softmax_model_to_ini, export_binary_model_to_ini, unify_ini_files


def main():
    random = np.random.default_rng(190)
    features = ['Vaginal_Distance01', 'Vaginal_Time01', 'Anal_Distance01', 'Anal_Time01']
    X = pd.DataFrame(random.normal(size=(150, 4)), columns=features)
    # Shared suffixes deliberately have different input values.
    production = (ROOT / 'src/Thread/NiNode/NiDescriptor.h').read_text()
    predictor = function(production, 'float PredictCluster(const std::vector<const INiDescriptor*>& descriptors) const override')
    cases = []
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'model.ini'
        for count in (2, 3):
            labels = np.array(['Vaginal', 'Anal', 'Crotch_NONE'][:count])
            y = labels[np.arange(len(X)) % count]
            model = Pipeline([('scaler', StandardScaler()), ('clf', LogisticRegression(max_iter=1000))]).fit(X, y)
            export_softmax_model_to_ini(model, path)
            config = configparser.ConfigParser(); config.read(path)
            raw = []
            for label in model.classes_:
                section = config[label]
                assert section['schema'] == 'cluster-v2'
                weights = np.array([float(section[name]) for name in features])
                bias = float(section['bias'])
                raw.append(X.to_numpy() @ weights + bias)
                for index in (0, 1, 19):
                    cases.append((weights, bias, X.iloc[index].to_numpy(), raw[-1][index]))
            raw = np.array(raw).T
            probabilities = np.exp(raw - raw.max(axis=1, keepdims=True)); probabilities /= probabilities.sum(axis=1, keepdims=True)
            np.testing.assert_allclose(probabilities, model.predict_proba(X), rtol=1e-10, atol=1e-10)
        # Binary exports reject columns that would alias, rather than silently overwrite.
        rejected = False
        try: export_binary_model_to_ini(model, 'Vaginal', path)
        except ValueError: rejected = True
        assert rejected
        binary = Pipeline([('scaler', StandardScaler()), ('clf', LogisticRegression())]).fit(X.iloc[:, :2], np.arange(len(X)) % 2)
        export_binary_model_to_ini(binary, 'Vaginal', path)
        config = configparser.ConfigParser(); config.read(path)
        section = config['Vaginal']
        assert section['schema'] == 'legacy'
        combined = Path(directory) / 'combined.ini'
        combined.write_text('[Vaginal]\nschema=cluster-v2\nAnal_Distance01=123\n')
        unify_ini_files(path, combined)
        merged = configparser.ConfigParser(); merged.read(combined)
        assert merged['Vaginal']['schema'] == 'legacy'
        assert 'Anal_Distance01' not in merged['Vaginal']
        logits = X.iloc[:, :2].to_numpy() @ np.array([float(section['Distance01']), float(section['Time01'])]) + float(section['bias'])
        np.testing.assert_allclose(logits, binary.decision_function(X.iloc[:, :2]), rtol=1e-10, atol=1e-10)

    code = r'''
#include <array>
#include <vector>
#include <cmath>
#include <cassert>
#include <iostream>
enum class Feature { Distance01, Time01 };
namespace magic_enum { template<class T> constexpr auto enum_values() { return std::array{T::Distance01,T::Time01}; } }
struct INiDescriptor {
    virtual ~INiDescriptor() = default;
    virtual float PredictCluster(const std::vector<const INiDescriptor*>&) const=0;
    virtual float GetFeature(Feature) const=0;
    virtual int GetType() const=0;
};
struct Descriptor:INiDescriptor {
    int type=0; std::array<float,2> values{};
    bool clusterModel=true; float bias=0;
    std::array<std::array<float,2>,2> clusterCoefficients{};
    float Predict()const{return 123;}
    int GetType()const override{return type;}
    float GetFeature(Feature f)const override{return values[static_cast<size_t>(f)];}
'''+predictor+r'''
};
int main(){
'''
    def number(value): return f'{float(value):.9e}f'
    for weights, bias, values, expected in cases:
        code += '{Descriptor a,b,p; b.type=1;\n'
        code += 'a.values={' + ','.join(map(number, values[:2])) + '};\n'
        code += 'b.values={' + ','.join(map(number, values[2:])) + '};\n'
        code += 'p.bias=' + number(bias) + ';\n'
        code += 'p.clusterCoefficients={{{' + ','.join(map(number, weights[:2])) + '},{' + ','.join(map(number, weights[2:])) + '}}};\n'
        code += 'assert(std::abs(p.PredictCluster({&a,&b})-(' + number(expected) + '))<1e-5f);\n'
        code += 'assert(std::abs(p.PredictCluster({&a})-(' + number(values[:2] @ weights[:2] + bias) + '))<1e-5f);}\n'
    code += 'std::cout<<"PASS: sklearn -> INI -> production C++ cluster predictor (2/3 classes, absent descriptor)\\n";}\n'
    run('cluster_parity',code)

if __name__ == '__main__': main()
