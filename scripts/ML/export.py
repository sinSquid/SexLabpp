import configparser
from pathlib import Path

import joblib
import numpy as np


def _validate_model_or_path(model):
    if isinstance(model, (str, Path)):
        model_path = Path(model)
        if not model_path.exists() or model_path.suffix != ".pkl":
            raise ValueError(f"Model file not found or invalid: {model}")
        model = joblib.load(model_path)
    return model

def _ensure_ini_path(ini_path: str | Path) -> Path:
    ini_path = Path(ini_path)
    if ini_path.suffix != ".ini":
        raise ValueError(f"INI path must have .ini extension: {ini_path}")
    return ini_path

def _normalize_feature_name(feature_name: str) -> str:
    return feature_name.split("_")[-1] if "_" in feature_name else feature_name

def export_binary_model_to_ini(model, interaction_name: str, out_path: str | Path) -> None:
    model = _validate_model_or_path(model)
    scaler = model.named_steps["scaler"]
    clf = model.named_steps["clf"]

    w_scaled = clf.coef_[0]
    b_scaled = clf.intercept_[0]

    means = scaler.mean_
    stds = scaler.scale_

    # Convert to raw feature space
    w_raw = w_scaled / stds
    b_raw = b_scaled - np.sum((w_scaled * means) / stds)

    feature_names = scaler.feature_names_in_

    config = configparser.ConfigParser()
    if interaction_name not in config:
        config[interaction_name] = {}

    config[interaction_name]["bias"] = str(b_raw)
    config[interaction_name]["schema"] = "legacy"

    normalized = [_normalize_feature_name(name) for name in feature_names]
    if len({name.casefold() for name in normalized}) != len(normalized):
        raise ValueError("Binary model contains aliased feature columns; train on one interaction only")
    for name, weight in zip(normalized, w_raw):
        config[interaction_name][name] = str(weight)

    with open(out_path, "w") as f:
        config.write(f)

    print(f"Exported {interaction_name} to {out_path}")


def export_softmax_model_to_ini(model_or_path, out_path: str | Path) -> None:
    model = _validate_model_or_path(model_or_path)

    scaler = model.named_steps["scaler"]
    clf = model.named_steps["clf"]

    means = scaler.mean_
    stds = scaler.scale_
    feature_names = scaler.feature_names_in_

    config = configparser.ConfigParser()

    classes = clf.classes_
    # Prevent previously exported class models from participating in this cluster
    # when the new training set has no examples of those classes.
    feature_types = {str(name).rsplit("_", 1)[0] for name in feature_names}
    for absent in feature_types - set(classes):
        config[absent] = {"schema": "cluster-v2", "bias": "-1e30"}

    for class_index, class_name in enumerate(classes):

        if len(classes) == 2 and len(clf.coef_) == 1:
            # sklearn's binary sigmoid(z) equals softmax([-z/2, z/2]).
            sign = -0.5 if class_index == 0 else 0.5
            w_scaled = clf.coef_[0] * sign
            b_scaled = clf.intercept_[0] * sign
        else:
            w_scaled = clf.coef_[class_index]
            b_scaled = clf.intercept_[class_index]

        # Convert to raw feature space
        w_raw = w_scaled / stds
        b_raw = b_scaled - np.sum((w_scaled * means) / stds)

        # Create section if missing
        if class_name not in config:
            config[class_name] = {}

        config[class_name]["bias"] = str(b_raw)
        config[class_name]["schema"] = "cluster-v2"
        if len({str(name).casefold() for name in feature_names}) != len(feature_names):
            raise ValueError("Duplicate cluster feature names")
        for feature_name, weight in zip(feature_names, w_raw):
            config[class_name][str(feature_name)] = str(weight)

        print(f"Exported class {class_name}")

    with open(out_path, "w") as f:
        config.write(f)

    print(f"Softmax model exported to {out_path}")

def unify_ini_files(ini_path: str | Path, out_path: str | Path) -> None:
    ini_root = Path(ini_path)
    out_path = _ensure_ini_path(out_path)

    ini_files = []
    if ini_root.is_dir():
        ini_files = sorted(ini_root.glob("*.ini"))
    elif ini_root.is_file() and ini_root.suffix == ".ini":
        ini_files = [ini_root]
    else:
        raise ValueError(f"INI path must be a directory or .ini file: {ini_root}")

    unified_config = configparser.ConfigParser()
    if out_path.exists():
        unified_config.read(out_path)

    for ini_file in ini_files:
        if ini_file.resolve() == out_path.resolve():
            continue
        config = configparser.ConfigParser()
        config.read(ini_file)
        for section in config.sections():
            # Replace the section so old schemas/coefficients cannot survive retraining.
            unified_config[section] = dict(config[section])

    with open(out_path, "w") as f:
        unified_config.write(f)

    print(f"Unified INI file exported to {out_path}")
