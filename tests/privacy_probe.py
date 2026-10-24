"""Fresh-process privacy probe. Python audit hooks do not police native syscalls."""
import sys
attempts=[]
def deny_network(event,args):
    if event in {'socket.connect','socket.getaddrinfo','socket.sendto','urllib.Request'}:
        attempts.append(event);raise PermissionError('NETWORK_BLOCKED_FOR_TEST')
sys.addaudithook(deny_network)

from collections import Counter
import io
import json
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from local_anonymizer.detectors import LocalDetector,default_model_path
from local_anonymizer.domain import Category,Decision,Disposition
from local_anonymizer.export import publish_text
from local_anonymizer.ingest import load_document
from local_anonymizer.report import build_report,save_report
from local_anonymizer.session import Session

log=io.StringIO();handler=logging.StreamHandler(log);logging.getLogger().addHandler(handler)
logging.getLogger().setLevel(logging.DEBUG)
sentinel='sentinelprivacy47@example.com';raw=(sentinel+'\r\n').encode()
with TemporaryDirectory() as tmp:
    root=Path(tmp);source=root/'source.txt';source.write_bytes(raw)
    detector=LocalDetector(default_model_path());s=Session();s.load(load_document(source))
    s.set_findings(detector.analyze(s.review.document.text,s.review.document.session_id))
    s.set_decisions(tuple(Decision(f.id,Disposition.ACCEPT if f.category==Category.CORREO else Disposition.REJECT) for f in s.review.findings))
    s.preview();s.confirm();v=s.verify(detector)
    if v.residuals:
        s.reject_residuals(tuple(c.key for c in v.residuals));v=s.verify(detector)
    assert v.ok
    receipt=publish_text(s.review,s.current_preview,v,root/'new.txt')
    counts=Counter(d.disposition.value for d in s.review.decisions)
    report=build_report(receipt,dict(counts),{'application':'0.1.0','model':'3.8.0'})
    save_report(report,root/'report.json')
    private=any(sentinel.encode() in p.read_bytes() for p in root.iterdir() if p!=source)
    assert not list(root.glob('.anonimizador-*'))
    assert sentinel not in log.getvalue()
    assert sentinel not in repr(s.review)+repr(s.current_preview)+repr(v)+repr(receipt)
    print(json.dumps({'network_attempts':len(attempts),'original_preserved':source.read_bytes()==raw,
                      'no_private_artifacts':not private}))
    s.close()
