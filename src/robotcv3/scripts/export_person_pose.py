"""Export existing YOLO26 pose weights for the project's CPU ONNX detector.

Run in a Python environment with ultralytics, torch and onnx installed.
The original weights are copied before export and remain unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from person_models import ROOT, model_spec


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('weights', type=Path)
    parser.add_argument('--model', required=True, choices=['yolo26x-pose', 'yolo26n-pose'])
    args = parser.parse_args()
    from ultralytics import YOLO
    import onnx
    spec = model_spec(args.model)
    weights = args.weights.resolve(strict=True)
    destination = ROOT / 'downloads/phase2/models'
    destination.mkdir(parents=True, exist_ok=True)
    copied = destination / (args.model + '.pt')
    if weights != copied:
        shutil.copy2(weights, copied)
    model = YOLO(copied)
    if model.task != 'pose':
        parser.error('The supplied weights must be a pose model')
    exported = Path(model.export(format='onnx', imgsz=640, opset=17, device='cpu',
                                 dynamic=False, simplify=False, nms=False, end2end=False))
    graph = onnx.load(str(exported))
    onnx.checker.check_model(graph)
    shape = [dim.dim_value for dim in graph.graph.output[0].type.tensor_type.shape.dim]
    # The pinned C++ Pose decoder expects raw xywh + person confidence + 17*(x,y,conf).
    if shape != [1, 56, 8400] or graph.ir_version > 10:
        raise RuntimeError(f'Export incompatible with pinned Pose decoder: shape={shape}, IR={graph.ir_version}')
    receipt = {'model_id': args.model, 'source_weights': str(weights),
               'source_sha256': hashlib.sha256(weights.read_bytes()).hexdigest(),
               'onnx_sha256': hashlib.sha256(exported.read_bytes()).hexdigest(),
               'output_shape': shape, 'ir_version': graph.ir_version,
               'export': {'imgsz': 640, 'opset': 17, 'end2end': False, 'nms': False}}
    (destination / (spec['file'] + '.source.json')).write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(exported)


if __name__ == '__main__':
    main()
