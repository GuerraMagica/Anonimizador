"""Exact-span evaluation; offline audit hook, no production inputs."""
import sys, json, time, resource, os
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root/'src'),str(root/'tests')]
os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
attempts=[]
def offline(event,args):
    if event in {'socket.connect','socket.getaddrinfo','socket.sendto','urllib.Request'}:
        attempts.append(event);raise PermissionError('NETWORK_BLOCKED')
sys.addaudithook(offline)
from compare_ner_models import read_frozen_ner_corpus, score_ner
from local_anonymizer.ner import EnhancedDetector
start=time.perf_counter();detector=EnhancedDetector(root/'.venv/models/gliner-multi-v2.1');initialization=time.perf_counter()-start
names=sys.argv[1:] or ['evaluation-v1','ner-comparison-v2']
results={}
for name in names:
    cases,digest=read_frozen_ner_corpus(root/f'tests/fixtures/{name}.json',root/f'tests/fixtures/{name}.manifest.json')
    start=time.perf_counter()
    results[name]=score_ner(cases,lambda text:[(f.start,f.end,f.category.value) for f in detector.analyze(text,'evaluation')])
    results[name].update(sha256=digest,seconds=time.perf_counter()-start)
    print(name,results[name]['metrics'],flush=True)
output={'fingerprint':detector.fingerprint,'initialization_seconds':initialization,'results':results,'network_attempts':attempts,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'limits':'Synthetic exact-span evaluation. Audit hook does not police native syscalls; OS sandbox also applied by launcher when available.'}
(root/('docs/ner-enhanced-'+('-'.join(names))+'.json')).write_text(json.dumps(output,indent=2)+'\n')
