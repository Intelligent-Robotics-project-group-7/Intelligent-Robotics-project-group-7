"""Choose a model by name, download it if needed, and return its file path."""
import argparse
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def model_catalog(root=ROOT):
    return json.loads((root / 'config/person_models.json').read_text())


def model_spec(model_id, root=ROOT):
    models = model_catalog(root)['models']
    if model_id not in models:
        raise ValueError(f"Unknown model {model_id!r}; choose: {', '.join(models)}")
    return dict(models[model_id], model_id=model_id)


def get_model_path(model_id, root=ROOT):
    model = model_spec(model_id, root)
    path = root / 'downloads/phase2/models' / model['file']
    if not path.is_file() or path.stat().st_size == 0:
        if model.get('local_export'):
            raise FileNotFoundError(f'Missing {model_id}; run scripts/export_person_pose.py with your local pose .pt weights')
        raise FileNotFoundError(f'Missing or empty {model_id}; run: python3 scripts/person_models.py download {model_id}')
    return path


def download_model(model_id, root=ROOT):
    model = model_spec(model_id, root)
    path = root / 'downloads/phase2/models' / model['file']
    if path.is_file() and path.stat().st_size > 0:
        return path
    if model.get('local_export'):
        raise ValueError(f'{model_id} requires a local export; use scripts/export_person_pose.py')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.onnx.part')
    try:
        request = urllib.request.Request(model['url'], headers={'User-Agent': 'TurtleBot4-Perception/1.0'})
        with urllib.request.urlopen(request, timeout=90) as response, temporary.open('wb') as stream:
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)
        if temporary.stat().st_size == 0:
            raise RuntimeError('Downloaded model is empty: ' + model_id)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['list', 'download', 'path'])
    parser.add_argument('models', nargs='*')
    args = parser.parse_args()
    if args.command == 'path':
        if len(args.models) != 1:
            parser.error('path requires exactly one model name')
        print(get_model_path(args.models[0]))
        return
    model_ids = args.models or [name for name, spec in model_catalog()['models'].items()
                               if args.command != 'download' or not spec.get('local_export')]
    # Check names before starting any downloads.
    models = [model_spec(model_id) for model_id in model_ids]
    for model in models:
        if args.command == 'list':
            print(f"{model['model_id']:10} {model['file']}")
        else:
            print(f"{model['model_id']}: {download_model(model['model_id'])}", flush=True)


if __name__ == '__main__':
    main()
