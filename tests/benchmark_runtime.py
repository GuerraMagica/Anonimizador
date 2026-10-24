"""Measured local synthetic workload, no latency promise or native memory sandbox."""
import json
from pathlib import Path
import platform
import resource
import subprocess
import time

start=time.perf_counter()
from local_anonymizer.detectors import LocalDetector,default_model_path
base=LocalDetector(default_model_path());cold=time.perf_counter()-start
start=time.perf_counter();second=LocalDetector(default_model_path());warm=time.perf_counter()-start
del second
unit='La técnica de sonido revisa el montaje y prepara la mezcla final.\n'
measurements={}
for size in (20000,100000):
    text=(unit*(size//len(unit)+1))[:size];runs=[]
    for i in range(3):
        start=time.perf_counter();result=base.analyze(text,'benchmark');runs.append(time.perf_counter()-start)
    measurements[str(size)]={'seconds':runs,'candidates':len(result)}
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from local_anonymizer.gui import MainWindow
from local_anonymizer.domain import Document,FileIdentity
app=QApplication([]);window=MainWindow(detector=base)
text=(unit*(100000//len(unit)+1))[:100000]
window.set_document(Document('benchmark',0,Path('.'),FileIdentity(0,0),text,''));window.show()
ticks=[];cancellation={};start=time.perf_counter()
def tick():
    now=time.perf_counter();ticks.append(now)
    if window._thread is None and 'requested' in cancellation:
        cancellation['completed']=now-start;window.close();app.quit()
def cancel():
    cancellation['requested']=time.perf_counter()-start;cancellation['was_busy']=window.session.busy
    window.cancel_work()
timer=QTimer();timer.timeout.connect(tick);timer.start(20)
window.start_analysis();QTimer.singleShot(50,cancel);QTimer.singleShot(60000,app.quit);app.exec()
cancellation['wait_after_request_seconds']=cancellation.get('completed',60)-cancellation['requested']
cancellation['max_heartbeat_gap_seconds']=max((b-a for a,b in zip(ticks,ticks[1:])),default=None)
cancellation['result_applied']=window.session.review is not None
try:cpu=subprocess.check_output(['/usr/sbin/sysctl','-n','machdep.cpu.brand_string'],text=True,stderr=subprocess.DEVNULL).strip()
except Exception:cpu=platform.machine()
result={'platform':platform.system(),'macos':platform.mac_ver()[0],'cpu':cpu,'python':platform.python_version(),
        'model_initialization_new_process_seconds':cold,'second_initialization_seconds':warm,
        'analysis':measurements,'cancellation':cancellation,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'notes':'Single process, synthetic prose, three warm analyses per size. Cold means first initialization in a new process; OS filesystem caches were not flushed. Offscreen Qt heartbeat, not manual GUI usability or worst-case document performance.'}
(Path(__file__).parents[1]/'docs'/'runtime-benchmark.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
