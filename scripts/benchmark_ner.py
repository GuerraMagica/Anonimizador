"""Bounded synthetic runtime measurement; never an accuracy acceptance corpus."""
import json
from pathlib import Path
import resource
import sys
import time

root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'src'))
attempts=[]
def offline(event,args):
    if event in {'socket.connect','socket.getaddrinfo','socket.sendto','urllib.Request'}:
        attempts.append(event);raise PermissionError('NETWORK_BLOCKED')
sys.addaudithook(offline)
from local_anonymizer.ner import EnhancedDetector
start=time.perf_counter();detector=EnhancedDetector(root/'.venv/models/gliner-multi-v2.1')
initialization=time.perf_counter()-start
tail='\nMaría García vive en Madrid.'
text=(('Texto técnico del informe. '*4000)[:100000-len(tail)]+tail)
assert len(text)==100000
start=time.perf_counter();findings=detector.analyze(text,'synthetic-runtime');elapsed=time.perf_counter()-start
expected=(text.rindex('María García'),text.rindex('María García')+len('María García'))
result={'characters':len(text),'fingerprint':detector.fingerprint,'initialization_seconds':initialization,
        'analysis_seconds':elapsed,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'findings':len(findings),'tail_person_detected':any((f.start,f.end)==expected for f in findings),
        'network_attempts':attempts,'limits':'One synthetic repeated low-density text on the development machine. Not an accuracy corpus or a worst-case latency/memory guarantee. Python audit hook; OS network denial applied by launcher.'}
(root/'docs/ner-runtime-100k.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
