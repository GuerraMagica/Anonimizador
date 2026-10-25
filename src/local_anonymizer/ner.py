"""Local label-conditioned NER with bounded overlapping character windows."""
from pathlib import Path, PurePosixPath
from .domain import AnonymizerError

PINNED_MANIFEST_SHA256="3b4c40bb8744f0f1496fbaf0967eecb9eb181f556ffc98264a4c439ec00eaa89"


def text_windows(text, *, size=384, overlap=96):
    if not 0 <= overlap < size:
        raise ValueError('INVALID_WINDOW_CONFIG')
    start=0
    while start < len(text):
        end=min(start+size,len(text))
        yield start,text[start:end]
        if end==len(text):break
        start=end-overlap


class EnhancedDetector:
    def __init__(self, model_path: Path):
        from hashlib import sha256
        from importlib.metadata import version
        import json
        try:
            model_path=Path(model_path)
            # The manifest names the directories consumed below, not an
            # arbitrary sibling selected by the caller. Refuse links before
            # resolving: a link must not redirect a verified resource.
            if model_path.name != 'gliner-multi-v2.1' or model_path.is_symlink():
                raise ValueError('RESOURCE_SELECTION')
            model_path=model_path.resolve(strict=True)
            backbone=model_path.parent/'mdeberta-v3-base'
            if backbone.is_symlink() or not backbone.is_dir():
                raise ValueError('RESOURCE_SELECTION')
            if (model_path/'manifest.json').is_symlink():
                raise ValueError('RESOURCE_SELECTION')
            manifest_bytes=(model_path/'manifest.json').read_bytes()
            if sha256(manifest_bytes).hexdigest()!=PINNED_MANIFEST_SHA256:raise ValueError('RESOURCE_MANIFEST')
            manifest=json.loads(manifest_bytes)
            verified={}
            expected={'gliner-multi-v2.1':{'manifest.json'},'mdeberta-v3-base':set()}
            for resource in manifest['resources']:
                relative=PurePosixPath(resource['path'])
                if (len(relative.parts)!=2 or relative.parts[0] not in expected
                        or relative.name in ('.','..') or relative.as_posix()!=resource['path']
                        or relative.as_posix() in verified):
                    raise ValueError('RESOURCE_PATH')
                path=model_path.parent/relative
                if path.is_symlink() or not path.is_file():raise ValueError('RESOURCE_PATH')
                digest=sha256()
                with path.open('rb') as stream:
                    for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
                if digest.hexdigest()!=resource['sha256'] or path.stat().st_size!=resource['bytes']:
                    raise ValueError('RESOURCE_CHANGED')
                verified[relative.as_posix()]=path
                expected[relative.parts[0]].add(relative.name)
            required={'gliner-multi-v2.1/gliner_config.json','gliner-multi-v2.1/model.safetensors',
                      'mdeberta-v3-base/config.json','mdeberta-v3-base/tokenizer_config.json',
                      'mdeberta-v3-base/spm.model'}
            if not required.issubset(verified):raise ValueError('RESOURCE_MISSING')
            # AutoTokenizer/AutoConfig discover optional files by directory.
            # A tokenizer.json or added_tokens.json would change tokenization
            # without entering the fingerprint. Permit only manifest members.
            for name,allowed in expected.items():
                directory=model_path.parent/name
                if {path.name for path in directory.iterdir()}!=allowed:
                    raise ValueError('RESOURCE_EXTRA')
            from gliner.model import UniEncoderSpanGLiNER
            from gliner.config import GLiNERConfig
            from transformers import AutoTokenizer
            from safetensors.torch import load_file
            from .detectors import LocalDetector
            import torch
            config=json.loads(verified['gliner-multi-v2.1/gliner_config.json'].read_text())
            if config['model_name']!='microsoft/mdeberta-v3-base':raise ValueError('ARCHITECTURE')
            config['model_name']=str(backbone)
            tokenizer=AutoTokenizer.from_pretrained(str(backbone),local_files_only=True,trust_remote_code=False,fix_mistral_regex=False)
            # No truncation in tokenizer; adapter bounds and verifies encoded size.
            tokenizer.model_max_length=10**9
            self._model=UniEncoderSpanGLiNER(GLiNERConfig(**config),tokenizer=tokenizer,
                                            backbone_from_pretrained=False,local_files_only=True)
            self._model._resize_token_embeddings(self._model,self._model.config,tokenizer)
            self._model.model.load_state_dict(load_file(str(verified['gliner-multi-v2.1/model.safetensors'])),strict=True)
            self._model.eval()
            self._structured=LocalDetector(None,structured_only=True)
            fingerprint={'resources':manifest,'labels':['person','organization','location'],
                         'threshold':0.5,'flat_ner':False,'multi_label':True,'window':384,'overlap':96,
                         'adapter_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
                         'structured':self._structured.fingerprint,
                         'versions':{p:version(p) for p in ('gliner','torch','transformers','safetensors','sentencepiece')}}
            self._fingerprint='gliner-es:v1:'+sha256(json.dumps(fingerprint,sort_keys=True).encode()).hexdigest()
        except Exception:
            raise AnonymizerError('MODEL_UNAVAILABLE') from None

    @property
    def fingerprint(self):
        return self._fingerprint

    def _predict(self, text):
        # Actual GLiNER prompt tokenization, checked before inference: neither
        # its word cap nor transformer position cap may silently drop a suffix.
        processor=self._model.data_processor
        words=[token for token,_,_ in processor.words_splitter(text)]
        labels=['person','organization','location']
        if len(words)>self._model.config.max_len:raise ValueError('WORD_LIMIT')
        inputs,_=processor.prepare_inputs([words],[labels])
        ids=processor.transformer_tokenizer(inputs,is_split_into_words=True,truncation=False)['input_ids'][0]
        if len(ids)>512:raise ValueError('TOKEN_LIMIT')
        return self._model.predict_entities(text,labels,threshold=.5,flat_ner=False,multi_label=True)

    def analyze(self, text, session_id):
        return self.analyze_cancellable(text, session_id, lambda: False)

    def analyze_cancellable(self, text, session_id, cancelled):
        from .detectors import MAX_ANALYSIS_CHARACTERS
        from .domain import Finding, Category, Confidentiality
        from uuid import uuid4
        if not isinstance(text,str) or len(text)>MAX_ANALYSIS_CHARACTERS:
            raise AnonymizerError('ANALYSIS_LIMIT')
        labels={'person':Category.PERSONA,'organization':Category.ORGANIZACION,'location':Category.UBICACION}
        try:
            if cancelled():raise AnonymizerError('CANCELLED')
            findings=list(self._structured.analyze(text,session_id))
            seen=set()
            for offset,window in text_windows(text):
                if cancelled():raise AnonymizerError('CANCELLED')
                for entity in self._predict(window):
                    start,end=entity['start'],entity['end']
                    if not (isinstance(start,int) and isinstance(end,int) and 0<=start<end<=len(window)):
                        raise ValueError('INVALID_OFFSETS')
                    category=labels[entity['label']]
                    key=(offset+start,offset+end,category)
                    if key in seen:continue
                    seen.add(key)
                    findings.append(Finding(uuid4().hex,session_id,*key,Confidentiality.PII,
                                            ('gliner:multi-v2.1',),float(entity['score'])))
            if cancelled():raise AnonymizerError('CANCELLED')
            return tuple(sorted(findings,key=lambda f:(f.start,f.end,f.category,f.provenance)))
        except AnonymizerError as error:
            if error.code=='CANCELLED':raise AnonymizerError('CANCELLED') from None
            raise AnonymizerError('ANALYSIS_FAILED') from None
        except Exception:
            raise AnonymizerError('ANALYSIS_FAILED') from None
