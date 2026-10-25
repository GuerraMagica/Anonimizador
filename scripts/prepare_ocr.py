"""Explicit OCR preparation; analysis never downloads resources."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import urllib.request

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--download',action='store_true')
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    resources=json.loads((root/'docs/ocr-model-artifacts.json').read_text())['resources']
    target=root/'.venv/models/tessdata';target.mkdir(parents=True,exist_ok=True)
    for entry in resources:
        path=target/entry['filename']
        def matches(candidate):
            data=candidate.read_bytes()
            return len(data)==entry['bytes'] and hashlib.sha256(data).hexdigest()==entry['sha256']
        if path.exists():
            if path.is_symlink() or not matches(path):raise RuntimeError('EXISTING_RESOURCE_MISMATCH')
            continue
        if not args.download:raise RuntimeError('OCR_RESOURCE_MISSING_USE_EXPLICIT_DOWNLOAD')
        with tempfile.TemporaryDirectory(dir=target,prefix='.prepare-') as tmp:
            staged=Path(tmp)/'resource';size=0
            with urllib.request.urlopen(entry['url'],timeout=60) as source,staged.open('xb') as output:
                while block:=source.read(65536):
                    size+=len(block)
                    if size>entry['bytes']:raise RuntimeError('RESOURCE_SIZE')
                    output.write(block)
            if not matches(staged):raise RuntimeError('RESOURCE_HASH')
            path.hardlink_to(staged)
    print('OCR resources verified.')

if __name__=='__main__':main()
