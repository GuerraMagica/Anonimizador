"""Corpus integrity/measurement tests; model acceptance is a separate command."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import unittest
from evaluate_detection import evaluate_sets

FIXTURES=Path(__file__).parent/'fixtures'

class AcceptanceMeasurementTests(unittest.TestCase):
    def test_exact_span_metrics_count_false_negatives_and_positives(self):
        self.assertEqual(evaluate_sets({(1,3)}, {(1,3),(4,7)}),{'tp':1,'fp':1,'fn':0})
        self.assertEqual(evaluate_sets({(1,3)}, {(1,4)}),{'tp':0,'fp':1,'fn':1})

    def test_corpus_is_frozen_with_required_denominators(self):
        raw=(FIXTURES/'evaluation-v1.json').read_bytes()
        manifest=json.loads((FIXTURES/'evaluation-v1.manifest.json').read_text())
        self.assertEqual(sha256(raw).hexdigest(),manifest['sha256'])
        cases=json.loads(raw)['cases'];self.assertEqual(len({c['id'] for c in cases}),len(cases))
        for suite in ('email','phone','nif','nie','iban','passport','date'):
            selected=[c for c in cases if c['suite']==suite]
            self.assertEqual(sum(bool(c['expected']) for c in selected),50)
            self.assertEqual(sum(not c['expected'] for c in selected),50)
        counts=Counter(e['category'] for c in cases if c['suite']=='ner' for e in c['expected'])
        self.assertEqual(counts,{'PERSONA':100,'ORGANIZACION':100,'UBICACION':100})
        for c in cases:
            for e in c['expected']:self.assertTrue(0<=e['start']<e['end']<=len(c['text']))

if __name__=='__main__':unittest.main()
