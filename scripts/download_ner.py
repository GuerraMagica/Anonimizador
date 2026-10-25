"""Explicit preparation only: download pinned official resources and verify hashes.

Never called by the detector. No pickle files, remote Python or user documents.
"""
from hashlib import sha256
import json
from pathlib import Path
import urllib.request

root=Path(__file__).resolve().parents[1]
manifest_raw=(root/'docs/ner-resources.json').read_bytes()
manifest=json.loads(manifest_raw)
for resource in manifest['resources']:
    destination=root/'.venv/models'/resource['path']
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists():
        digest=sha256(destination.read_bytes()).hexdigest()
        if digest==resource['sha256']:continue
        raise RuntimeError('EXISTING_RESOURCE_MISMATCH')
    url=f"https://huggingface.co/{resource['repository']}/resolve/{resource['revision']}/{destination.name}"
    temporary=destination.with_suffix(destination.suffix+'.partial')
    digest=sha256();size=0
    with urllib.request.urlopen(url,timeout=120) as source,temporary.open('xb') as output:
        while block:=source.read(1024*1024):
            size+=len(block)
            if size>resource['bytes']:raise RuntimeError('RESOURCE_SIZE')
            output.write(block);digest.update(block)
    if size!=resource['bytes'] or digest.hexdigest()!=resource['sha256']:raise RuntimeError('RESOURCE_HASH')
    # Hard-link publishes exclusively, preserving concurrent/preexisting files.
    destination.hardlink_to(temporary);temporary.unlink()
(root/'.venv/models/gliner-multi-v2.1/manifest.json').write_bytes(manifest_raw)
print('Pinned local resources verified.')
