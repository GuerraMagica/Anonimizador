"""Repeat the 3,000-candidate GUI workload with bounded visible pages.

Uses a deterministic detector double, not NLP. Run as a fresh offscreen process
so peak RSS is comparable with the separately recorded pre-pagination run.
"""
import json
from pathlib import Path
import platform
import resource
import time

from PySide6.QtWidgets import QApplication
from local_anonymizer.domain import Category, Confidentiality, Document, FileIdentity, Finding
from local_anonymizer.gui import MainWindow


class EmptyDetector:
    fingerprint = 'benchmark:1'
    def analyze(self, text, session_id):
        return ()


def measure():
    app = QApplication.instance() or QApplication([])
    window = MainWindow(detector=EmptyDetector())
    window.set_document(Document('dense', 0, Path('.'), FileIdentity(0, 0), 'Ana ' * 3000, ''))
    window.show()
    app.processEvents()
    window.session.set_findings(tuple(
        Finding(str(i), 'dense', 4*i, 4*i+3, Category.PERSONA,
                Confidentiality.PII, ('synthetic:v1',)) for i in range(3000)))
    start = time.perf_counter()
    window.render_review()
    app.processEvents()
    render_seconds = time.perf_counter() - start
    visible = window.table.rowCount()
    start = time.perf_counter()
    window.change_page(1)
    app.processEvents()
    navigation_seconds = time.perf_counter() - start
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    start = time.perf_counter()
    window.clear_document()
    app.processEvents()
    clear_seconds = time.perf_counter() - start
    window.close()
    return {
        'cases': 1, 'characters': 12000, 'candidates': 3000, 'visible_rows': visible,
        'render_seconds': render_seconds, 'next_page_seconds': navigation_seconds,
        'clear_seconds': clear_seconds, 'peak_rss_bytes': rss,
        'backend': app.platformName(), 'macos': platform.mac_ver()[0],
        'python': platform.python_version(), 'detector': 'deterministic_test_double',
        'limits': 'Single fresh-process GUI workload; no NLP efficacy, worst-case guarantee or manual visual validation.',
    }


if __name__ == '__main__':
    result = measure()
    destination = Path(__file__).parents[1] / 'docs' / 'runtime-dense-table-paged.json'
    destination.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
