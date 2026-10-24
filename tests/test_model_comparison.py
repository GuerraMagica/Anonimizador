import json
from pathlib import Path
import tempfile
import unittest

from compare_ner_models import score_ner, read_frozen_ner_corpus


class ComparisonTests(unittest.TestCase):
    def test_exact_spans_categories_and_missing_entities_are_scored(self):
        cases=[{'id':'synthetic','text':'Mara de Acme en Roma','expected':[
            {'start':0,'end':4,'category':'PERSONA'},
            {'start':8,'end':12,'category':'ORGANIZACION'},
            {'start':16,'end':20,'category':'UBICACION'}]}]
        result=score_ner(cases,lambda text:((0,4,'PERSONA'),(8,12,'UBICACION')))
        self.assertEqual(result['metrics']['PERSONA']['tp'],1)
        self.assertEqual(result['metrics']['ORGANIZACION']['fn'],1)
        self.assertEqual(result['metrics']['UBICACION']['fp'],1)
        self.assertEqual(result['metrics']['UBICACION']['fn'],1)
        self.assertFalse(result['gates_passed'])

    def test_frozen_comparison_corpus_has_100_entities_per_category(self):
        root=Path(__file__).parent/'fixtures'
        cases,digest=read_frozen_ner_corpus(root/'ner-comparison-v2.json',root/'ner-comparison-v2.manifest.json')
        self.assertEqual(len(cases),100);self.assertEqual(len(digest),64)
        result=score_ner(cases,lambda text:())
        for value in result['metrics'].values():self.assertEqual(value['fn'],100)

    def test_modified_corpus_is_rejected_before_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'corpus.json';manifest=Path(tmp)/'manifest.json'
            path.write_text('{"cases":[]}');manifest.write_text(json.dumps({'sha256':'0'*64}))
            with self.assertRaisesRegex(ValueError,'CORPUS_CHANGED'):
                read_frozen_ner_corpus(path,manifest)


if __name__=='__main__':unittest.main()
