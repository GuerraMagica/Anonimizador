"""Record hashes of already downloaded, revision-pinned official resources."""
from pathlib import Path
from hashlib import sha256
import json
root=Path(__file__).resolve().parents[1]/'.venv/models'
resources=[]
for folder,repo,revision,license in [('gliner-multi-v2.1','urchade/gliner_multi-v2.1','443d26d654e0324125a96bebd8e796c14ff2efe6','Apache-2.0'),('mdeberta-v3-base','microsoft/mdeberta-v3-base','a0484667b22365f84929a935b5e50a51f71f159d','MIT')]:
    for path in sorted((root/folder).iterdir()):
        if path.name=='manifest.json':continue
        h=sha256()
        with path.open('rb') as f:
            for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
        resources.append({'path':path.relative_to(root).as_posix(),'sha256':h.hexdigest(),'bytes':path.stat().st_size,'repository':repo,'revision':revision,'license':license})
manifest={'schema_version':1,'resources':resources}
raw=json.dumps(manifest,indent=2)+'\n'
(root/'gliner-multi-v2.1/manifest.json').write_text(raw)
(Path(__file__).resolve().parents[1]/'docs/ner-resources.json').write_text(raw)
print('Total resource bytes:',sum(r['bytes'] for r in resources))
