"""Frozen structured-recognizer gates used by EnhancedDetector; no NER claim."""
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
import sys

root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'src'))
from local_anonymizer.detectors import LocalDetector

raw=(root/'tests/fixtures/evaluation-v1.json').read_bytes()
manifest=json.loads((root/'tests/fixtures/evaluation-v1.manifest.json').read_text())
if sha256(raw).hexdigest()!=manifest['sha256']:raise RuntimeError('CORPUS_CHANGED')
detector=LocalDetector(None,structured_only=True)
config={'email':'presidio:email','phone':'presidio:phone:ES','nif':'presidio:nif:ES',
        'nie':'presidio:nie:ES','iban':'presidio:iban:ES','passport':'presidio:passport:ES','date':'presidio:date:es'}
totals=defaultdict(lambda:dict(tp=0,fp=0,fn=0,cases=0,positives=0,negatives=0));errors=[]
for case in json.loads(raw)['cases']:
    suite=case['suite']
    if suite not in config:continue
    expected={(e['start'],e['end']) for e in case['expected']}
    found={(f.start,f.end) for f in detector.analyze(case['text'],case['id']) if config[suite] in f.provenance}
    values=dict(tp=len(expected&found),fp=len(found-expected),fn=len(expected-found),cases=1,
                positives=len(expected),negatives=int(not expected))
    for key,value in values.items():totals[suite][key]+=value
    if values['fp'] or values['fn']:errors.append({'case':case['id'],'suite':suite,'fp':sorted(found-expected),'fn':sorted(expected-found)})
gates={}
for suite,m in totals.items():
    m['precision']=m['tp']/(m['tp']+m['fp']) if m['tp']+m['fp'] else 0
    m['recall']=m['tp']/(m['tp']+m['fn']) if m['tp']+m['fn'] else 0
    if suite not in ('passport','date'):
        gates[suite]=m['positives']>=50 and m['negatives']>=50 and m['fn']==0 and m['precision']>=.95
result={'corpus_sha256':manifest['sha256'],'structured_detector_fingerprint':detector.fingerprint,
        'metrics':dict(totals),'gates':gates,'passed':all(gates.values()),'errors':errors,
        'limits':'Synthetic exact-span named-recognizer scores; excludes cross-category collisions. Passport/date measured without acceptance gates. Enhanced NER scored separately.'}
(root/'docs/identifier-gates-2026-10-25.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2));sys.exit(0 if result['passed'] else 2)
