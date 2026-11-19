"""Record resolved vendors and immutable test inputs, not just requested versions."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
def command(args):
    result = subprocess.run(args, capture_output=True, text=True, check=True)
    return result.stdout.strip()

vendor = ROOT / 'research_ws/build/yolo_hfhub_vendor/_deps/yolo_hfhub-src'
report = {
    'base_image_id': json.loads((ROOT / 'evidence/phase2/base_image.json').read_text())[0]['Id'],
    'yolo_ros_commit': '94d2dd500cb26027ee9c019f4d3a02029ac615cc',
    'yolo_ros_version': '5.0.0',
    'onnxruntime_version_verified_in_runtime_log': '1.20.0',
    'huggingface_hub_cpp_commit': command(['git','-C',str(vendor),'rev-parse','HEAD']),
    'huggingface_hub_cpp_requested_tag': '1.1.5',
    'assets': json.loads((ROOT / 'config/phase2_assets.lock.json').read_text()),
    'project_files': {},
}
for directory in ('config','launch','scripts'):
    for path in sorted((ROOT / directory).rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            report['project_files'][path.relative_to(ROOT).as_posix()] = hashlib.file_digest(path.open('rb'),'sha256').hexdigest()
(ROOT / 'evidence/phase2/provenance.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({key:value for key,value in report.items() if key not in ('assets','project_files')},indent=2))
