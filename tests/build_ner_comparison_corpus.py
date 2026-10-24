"""Freeze a second synthetic NER corpus before comparing the approved models.

No detector is imported or queried. Refuses to replace an existing corpus.
"""
from hashlib import sha256
import json
from pathlib import Path


def build():
    first=['Adriana','Bruno','Beatriz','Emilio','Eva','Félix','Gabriela','Gonzalo','Inés','Ismael',
           'Julia','Leonor','Lorenzo','Manuel','Olga','Ramón','Raquel','Rocío','Teresa','Tomás']
    last=['Aguilar','Arias','Benítez','Cano','Cortés','Domínguez','Durán','Escobar','Esteban','Ferrero',
          'Galán','Herrera','Iglesias','León','Luna','Méndez','Pascual','Prieto','Salas','Valdés']
    real_orgs=['Iberdrola','Telefónica','Repsol','Acciona','Endesa','Airbus','Renfe','Seat','Inditex','Mapfre']
    fictional_orgs=['Estudios Umbral','Producciones Faro','Montaje Eclipse','Editorial Astrolabio','Sonido Albor',
                    'Laboratorio Boreal','Fundación Ronda','Agencia Claroscuro','Teatro Azabache','Transportes Junco']
    cities=['Logroño','León','Huesca','Teruel','Soria','Cuenca','Ávila','Lugo','Ourense','Pontevedra',
            'Albacete','Badajoz','Girona','Lleida','Tarragona','Castellón','Almería','Huelva','Jaén','Zamora']
    cases=[]
    for i in range(100):
        person=(first[i%20]+' '+last[(i*3+i//20)%20],'PERSONA')
        orgs=real_orgs if i%2==0 else fictional_orgs
        organization=(orgs[(i//2+i//20)%10],'ORGANIZACION');location=(cities[(i*7+i//20)%20],'UBICACION')
        contexts=[
            ['El informe fue revisado por ',person,' antes de su entrega a ',organization,' en ',location,'.'],
            ['Durante el ensayo celebrado en ',location,', ',person,' representó a ',organization,'.'],
            ['A petición de ',organization,', la supervisión en ',location,' quedó a cargo de ',person,'.'],
            ['Para preparar la sesión, ',person,' acudió a la oficina de ',organization,' en ',location,'.'],
            ['La responsable del archivo, ',person,', confirmó la recepción del material de ',organization,' desde ',location,'.'],
            ['El acta identifica a ',person,' como interlocutor de ',organization,' para las jornadas de ',location,'.'],
            ['La sede de la reunión estaba en ',location,'; participaron ',person,' y un equipo de ',organization,'.'],
            ['Un técnico de ',organization,' acompañó a ',person,' al estudio situado en ',location,'.'],
            ['Se acordó que ',person,' tramitaría desde ',location,' las solicitudes dirigidas a ',organization,'.'],
            ['La documentación de ',organization,' lleva la firma de ',person,' y está fechada en ',location,'.'],
        ]
        text='';expected=[]
        for part in contexts[i%10]:
            if isinstance(part,tuple):
                value,category=part;expected.append({'start':len(text),'end':len(text)+len(value),'category':category});text+=value
            else:text+=part
        cases.append({'id':f'ner-v2-{i:03d}','suite':'ner','text':text,'expected':expected,
                      'organization_kind':'public_name_in_fictional_context' if i%2==0 else 'invented_name'})
    return {'schema_version':1,'purpose':'Second synthetic NER evaluation, frozen before approved sm/md comparison',
            'annotation_policy':'Exact full person/organization/location names; all scenarios synthetic; 50 public organization names in fictional contexts and 50 invented organization names.',
            'cases':cases}


if __name__=='__main__':
    root=Path(__file__).parent/'fixtures'
    raw=(json.dumps(build(),ensure_ascii=False,indent=2)+'\n').encode()
    with (root/'ner-comparison-v2.json').open('xb') as f:f.write(raw)
    manifest={'sha256':sha256(raw).hexdigest(),'cases':100,'entities_per_category':100,
              'frozen_against_commit':'51ae1c1498083984807937c1917f9607d8b42129',
              'candidate_chosen_before_corpus':'es_core_news_md 3.8.0; user-authorized local comparison',
              'policy':'Frozen before either model analyzed v2. If used to tune/choose further changes, it becomes development data.'}
    with (root/'ner-comparison-v2.manifest.json').open('x') as f:json.dump(manifest,f,indent=2);f.write('\n')
