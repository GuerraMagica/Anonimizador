"""Independent exact-span evaluation. Exit 2 means acceptance gates failed."""
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
import sys
from local_anonymizer.detectors import LocalDetector,default_model_path,literal_findings
from local_anonymizer.domain import Category,Document,FileIdentity


def evaluate_sets(expected,predicted):
    return {'tp':len(expected&predicted),'fp':len(predicted-expected),'fn':len(expected-predicted)}


def evaluate():
    root=Path(__file__).parent/'fixtures';raw=(root/'evaluation-v1.json').read_bytes()
    manifest=json.loads((root/'evaluation-v1.manifest.json').read_text())
    if sha256(raw).hexdigest()!=manifest['sha256']:raise RuntimeError('CORPUS_CHANGED')
    detector=LocalDetector(default_model_path());totals=defaultdict(lambda:{'tp':0,'fp':0,'fn':0,'cases':0,'positives':0,'negatives':0})
    errors=[];unknown=[]
    suite_config={
        'email':('CORREO','presidio:email'),'phone':('TELEFONO','presidio:phone:ES'),
        'nif':('DOCUMENTO','presidio:nif:ES'),'nie':('DOCUMENTO','presidio:nie:ES'),
        'iban':('IBAN','presidio:iban:ES'),'passport':('DOCUMENTO','presidio:passport:ES'),
        'date':('FECHA','presidio:date:es')}
    for case in json.loads(raw)['cases']:
        text=case['text'];suite=case['suite'];expected=case['expected']
        if suite=='literal':
            term=text[expected[0]['start']:expected[0]['end']]
            doc=Document(case['id'],0,Path('.'),FileIdentity(0,0),text,'')
            findings=literal_findings(doc,((term,Category.PROYECTO),));categories=['PROYECTO']
        else:
            findings=detector.analyze(text,case['id'])
            if suite=='unknown_production':
                unknown.append({'id':case['id'],'automatic_candidates':[(f.start,f.end,f.category.value) for f in findings],
                                'supported_automatic_project_or_character_detection':False});continue
            categories=['PERSONA','ORGANIZACION','UBICACION'] if suite=='ner' else [suite_config[suite][0]]
            if suite!='ner':findings=tuple(f for f in findings if suite_config[suite][1] in f.provenance)
        for category in categories:
            exp={(e['start'],e['end']) for e in expected if e['category']==category}
            pred={(f.start,f.end) for f in findings if f.category.value==category}
            key=category if suite=='ner' else suite
            metric=evaluate_sets(exp,pred);total=totals[key]
            for k,v in metric.items():total[k]+=v
            total['cases']+=1;total['positives']+=len(exp);total['negatives']+=not exp
            if metric['fp'] or metric['fn']:
                errors.append({'case':case['id'],'metric':key,'false_negatives':sorted(exp-pred),'false_positives':sorted(pred-exp)})
    gates={}
    for key,total in totals.items():
        tp,fp,fn=(total[k] for k in ('tp','fp','fn'))
        total['precision']=tp/(tp+fp) if tp+fp else 0.0;total['recall']=tp/(tp+fn) if tp+fn else 0.0
        if key in ('PERSONA','ORGANIZACION','UBICACION'):
            gates[key]=total['positives']>=100 and total['precision']>=.9 and total['recall']>=.9
        elif key not in ('passport','date'):
            gates[key]=fn==0 and total['precision']>=(1 if key=='literal' else .95)
    return {'corpus_sha256':manifest['sha256'],'detector_fingerprint':detector.fingerprint,
            'metrics':dict(totals),'gates':gates,'detection_gates_passed':all(gates.values()),
            'errors':errors,'unknown_productions':unknown,
            'limits':'Synthetic fixtures only; no guarantee for production documents. Identifier suites score their named recognizer; cross-category collisions remain for human review.'}


if __name__=='__main__':
    result=evaluate();out=Path(__file__).parents[1]/'docs'/'evaluation-v1-results.json'
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    for name,value in result['metrics'].items():print(name,json.dumps(value,ensure_ascii=False))
    print('Detection gates:',result['detection_gates_passed'])
    sys.exit(0 if result['detection_gates_passed'] else 2)
