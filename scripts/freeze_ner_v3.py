"""Freeze independent synthetic evaluation; no detector import or execution."""
from pathlib import Path
from hashlib import sha256
import json

root=Path(__file__).resolve().parents[1]/'tests'/'fixtures'
first=['Alicia','Alberto','Celia','Cristóbal','Daniela','Diego','Elena','Enrique','Fátima','Héctor','Irene','Javier','Lidia','Marcos','Natalia','Nicolás','Patricia','Rubén','Silvia','Víctor']
last=['Alonso','Blanco','Castro','Delgado','Espinosa','Fuentes','Garrido','Hidalgo','Jiménez','Lara','Medina','Navarro','Ortega','Paredes','Quintana','Ramos','Serrano','Torres','Vega','Zúñiga']
public=['Microsoft','Google','Amazon','Netflix','Santander','BBVA','Ikea','Samsung','Toyota','Nestlé']
invented=['Estudios Cobalto','Producciones Madroño','Editorial Alondra','Fundación Lentisco','Transportes Granate','Laboratorio Nébula','Agencia Arrayán','Sonido Dársena','Teatro Celaje','Montaje Quimera']
cities=['Barcelona','Valencia','Sevilla','Zaragoza','Málaga','Murcia','Palma','Bilbao','Alicante','Córdoba','Valladolid','Vigo','Gijón','Granada','Oviedo','Pamplona','Santander','Toledo','Segovia','Salamanca']
templates=[['El contrato entre ', ' y ', ' se firmó en ', '.'],['Desde ', ', ', ' envió una propuesta a ', '.'],['La portavoz de ', ', ', ', asistió al encuentro de ', '.'],['En ', ' recibieron a ', ', que trabaja para ', '.'],['La carta de ', ' a ', ' menciona su próxima visita a ', '.']]
# Explicit slots prevent organization kind from being correlated with wording.
orders=[('p','o','l'),('l','p','o'),('o','p','l'),('l','p','o'),('o','p','l')]
cases=[]
for kind,orgs in [('public_name_in_fictional_context',public),('invented_name',invented)]:
    for template_i in range(5):
        for j in range(10):
            i=template_i*10+j
            values={'p':(first[i%20]+' '+last[(i*7+i//20)%20],'PERSONA'),'o':(orgs[j],'ORGANIZACION'),'l':(cities[(i*3+i//20)%20],'UBICACION')}
            text=templates[template_i][0];expected=[]
            for slot,suffix in zip(orders[template_i],templates[template_i][1:]):
                value,category=values[slot];expected.append({'start':len(text),'end':len(text)+len(value),'category':category});text+=value+suffix
            cases.append({'id':f'v3-{kind}-{i:03d}','suite':'ner','text':text,'expected':expected,'organization_kind':kind,'template':template_i})
raw=(json.dumps({'schema_version':1,'purpose':'Independent synthetic exact-span NER evaluation frozen before candidate measurement; public/invented organization types fully crossed with five templates.','cases':cases},ensure_ascii=False,indent=2)+'\n').encode()
with (root/'ner-independent-v3.json').open('xb') as f:f.write(raw)
manifest={'sha256':sha256(raw).hexdigest(),'entities_per_category':100,'cases':100,'frozen_before_measurement':True,'candidate':'urchade/gliner_multi-v2.1@443d26d654e0324125a96bebd8e796c14ff2efe6','policy':'Never tune against this corpus while claiming independent acceptance. Both organization kinds have 10 examples in every template.'}
with (root/'ner-independent-v3.manifest.json').open('x') as f:json.dump(manifest,f,indent=2);f.write('\n')
print(manifest)
