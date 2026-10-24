"""Offline diagnostic comparison; never changes the application's active model.

v1 is a model-selection reference. v2 was frozen before this comparison. No
patterns, model weights or annotations may be tuned against reported errors
while continuing to call that corpus an independent acceptance set.
"""
from collections import Counter
import gc
from hashlib import sha256
from importlib import metadata, util
import json
from pathlib import Path
import platform
import resource
import sys
import time

CATEGORIES=('PERSONA','ORGANIZACION','UBICACION')
LABELS={'PER':'PERSONA','ORG':'ORGANIZACION','LOC':'UBICACION'}
ARTIFACTS={
    'es_core_news_sm':'e451a83d6df79b87e9eed0cb553f03e99e36a3bab18a7b79f0dcfd1fdf875e12',
    'es_core_news_md':'478b8bb3f3e8eb149192f7d80e7cd64f990b7e9bccbc5329df41a57e86326be2',
}
EXCLUDE=['parser','senter','morphologizer','attribute_ruler','lemmatizer']


def read_frozen_ner_corpus(path, manifest):
    raw=path.read_bytes();digest=sha256(raw).hexdigest()
    if digest!=json.loads(manifest.read_text())['sha256']:raise ValueError('CORPUS_CHANGED')
    cases=[c for c in json.loads(raw)['cases'] if c.get('suite')=='ner']
    counts=Counter()
    if len({c['id'] for c in cases})!=len(cases):raise ValueError('CORPUS_INVALID')
    for case in cases:
        for entity in case['expected']:
            if (entity['category'] not in CATEGORIES
                    or not 0<=entity['start']<entity['end']<=len(case['text'])):
                raise ValueError('CORPUS_INVALID')
            counts[entity['category']]+=1
    if any(counts[c]<100 for c in CATEGORIES):raise ValueError('CORPUS_TOO_SMALL')
    return cases,digest


def score_ner(cases, predict):
    metrics={c:{'tp':0,'fp':0,'fn':0,'cases':0,'positives':0} for c in CATEGORIES}
    errors=[]
    for case in cases:
        predicted=set(predict(case['text']))
        for category in CATEGORIES:
            expected={(e['start'],e['end']) for e in case['expected'] if e['category']==category}
            actual={(start,end) for start,end,cat in predicted if cat==category}
            metric=metrics[category];metric['tp']+=len(expected&actual)
            metric['fp']+=len(actual-expected);metric['fn']+=len(expected-actual)
            metric['cases']+=1;metric['positives']+=len(expected)
            if actual!=expected:
                errors.append({'case':case['id'],'category':category,
                               'false_negatives':sorted(expected-actual),'false_positives':sorted(actual-expected)})
    gates={}
    for category,metric in metrics.items():
        tp,fp,fn=(metric[k] for k in ('tp','fp','fn'))
        metric['precision']=tp/(tp+fp) if tp+fp else 0.0
        metric['recall']=tp/(tp+fn) if tp+fn else 0.0
        gates[category]=metric['positives']>=100 and metric['precision']>=.9 and metric['recall']>=.9
    return {'metrics':metrics,'gates':gates,'gates_passed':all(gates.values()),'errors':errors}


def compare():
    attempts=[]
    def deny_network(event,args):
        if event in {'socket.connect','socket.getaddrinfo','socket.sendto','urllib.Request'}:
            attempts.append(event);raise PermissionError('NETWORK_BLOCKED_FOR_COMPARISON')
    sys.addaudithook(deny_network)
    import spacy
    root=Path(__file__).parent/'fixtures'
    corpora={}
    for name,filename in (('v1_reference','evaluation-v1'),('v2_frozen','ner-comparison-v2')):
        cases,digest=read_frozen_ner_corpus(root/(filename+'.json'),root/(filename+'.manifest.json'))
        corpora[name]={'cases':cases,'sha256':digest}
    models={}
    for package in ARTIFACTS:
        spec=util.find_spec(package)
        if spec is None:raise RuntimeError('MODEL_UNAVAILABLE')
        model_path=Path(spec.origin).parent/(package+'-3.8.0')
        start=time.perf_counter()
        nlp=spacy.load(model_path,exclude=EXCLUDE)
        if (nlp.meta.get('lang')!='es' or nlp.meta.get('version')!='3.8.0'
                or nlp.meta.get('name')!=package.removeprefix('es_')
                or not set(LABELS)<=set(nlp.get_pipe('ner').labels)):
            raise RuntimeError('MODEL_MISMATCH')
        initialization=time.perf_counter()-start
        results={}
        for name,corpus in corpora.items():
            start=time.perf_counter()
            results[name]=score_ner(corpus['cases'],lambda text:tuple(
                (ent.start_char,ent.end_char,LABELS[ent.label_]) for ent in nlp(text).ents if ent.label_ in LABELS))
            results[name]['analysis_seconds']=time.perf_counter()-start
        models[package]={'version':metadata.version(package),'artifact_sha256':ARTIFACTS[package],
                         'pipeline':nlp.pipe_names,'initialization_seconds':initialization,'corpora':results}
        del nlp
        gc.collect()
    if attempts:raise RuntimeError('NETWORK_ATTEMPT_OBSERVED')
    return {'models':models,'spacy_version':metadata.version('spacy'),
            'corpora':{k:{'sha256':v['sha256'],'ner_cases':len(v['cases'])} for k,v in corpora.items()},
            'network_attempts_observed':len(attempts),'active_model_unchanged':'es_core_news_sm',
            'candidate_ner_gates_passed':models['es_core_news_md']['corpora']['v2_frozen']['gates_passed'],
            'peak_process_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'macos':platform.mac_ver()[0],'python':platform.python_version(),
            'limits':'Synthetic exact-span NER only, CPU, sequential model loading in one process. Python audit hooks cannot police native syscalls. No production model switch or general guarantee.'}


if __name__=='__main__':
    result=compare()
    path=Path(__file__).parents[1]/'docs'/'ner-model-comparison.json'
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    for model,data in result['models'].items():
        for corpus,score in data['corpora'].items():
            print(model,corpus,json.dumps(score['metrics'],ensure_ascii=False))
    print('Candidate passed v2 gates:',result['candidate_ner_gates_passed'])
    sys.exit(0 if result['candidate_ner_gates_passed'] else 2)
