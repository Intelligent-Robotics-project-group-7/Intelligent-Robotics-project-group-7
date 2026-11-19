"""Choose a model by name, download it if needed, and return its file path."""
import argparse
import hashlib
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
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
        raise FileNotFoundError(f'Missing or empty {model_id}. Run bash scripts/setup_person_models.sh {model_id}')
    verify_model(path, model['sha256'])
    return path


def verify_model(path, expected):
    with path.open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    if actual != expected:
        raise ValueError(f'Model checksum mismatch for {path}. Remove the corrupt file before downloading again.')


def download_model(model_id, root=ROOT):
    model = model_spec(model_id, root)
    path = root / 'downloads/phase2/models' / model['file']
    if path.is_file() and path.stat().st_size > 0:
        return get_model_path(model_id, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        request = urllib.request.Request(model['url'], headers={'User-Agent': 'TurtleBot4-Perception/1.0'})
        with NamedTemporaryFile(dir=path.parent, prefix=f'.{path.name}.', suffix='.part', delete=False) as stream:
            temporary = Path(stream.name)
            with urllib.request.urlopen(request, timeout=90) as response:
                while chunk := response.read(1024 * 1024):
                    stream.write(chunk)
        verify_model(temporary, model['sha256'])
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['list', 'download', 'path'])
    parser.add_argument('models', nargs='*')
    args = parser.parse_args()
    catalog = model_catalog()
    if args.command == 'path':
        if len(args.models) > 1:
            parser.error('path accepts at most one model name')
        print(get_model_path(args.models[0] if args.models else catalog['default_model']))
        return
    model_ids = args.models or list(catalog['models'])
    # Check names before starting any downloads.
    models = [model_spec(model_id) for model_id in model_ids]
    for model in models:
        if args.command == 'list':
            print(f"{model['model_id']:10} {model['file']}")
        else:
            print(f"{model['model_id']}: {download_model(model['model_id'])}", flush=True)


if __name__ == '__main__':
    main()
