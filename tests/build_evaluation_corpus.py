"""One-time synthetic holdout construction, independent of detector output.

Refuses replacement. Once used to tune a detector this corpus is development
material; create an independent version for further acceptance claims.
"""
from hashlib import sha256
import json
from pathlib import Path


def build():
    cases=[]
    def add(suite,i,pieces):
        text='';expected=[]
        for piece in pieces:
            if isinstance(piece,tuple):
                value,category=piece;expected.append({'start':len(text),'end':len(text)+len(value),'category':category});text+=value
            else:text+=piece
        cases.append({'id':f'{suite}-{i:03d}','suite':suite,'text':text,'expected':expected})
    letters='TRWAGMYFPDXBNJZSQVHLCKE'
    for i in range(50):
        email=[f'evaluacion.{i}@example.com',f'ev+{i}@example.org',f'ev_{i}@example.net',f'ev-{i}@sub.example.com',f"ev{i}.o'hara@example.com"][i%5]
        add('email',i,['Contacto de prueba: ',(email,'CORREO'),'.'])
        number=str(600100000+i*37)
        phone=[number,'+34 '+number,'0034 '+number,number[:3]+' '+number[3:6]+' '+number[6:],'+34 '+number[:3]+'-'+number[3:6]+'-'+number[6:]][i%5]
        add('phone',i,['Llama al ',(phone,'TELEFONO'),' para la prueba.'])
        n=45000000+i*7919;nif=f'{n:08d}'+letters[n%23]
        add('nif',i,['Identificación: ',(nif if i%2 else nif[:-1]+'-'+nif[-1],'DOCUMENTO'),'.'])
        prefix='XYZ'[i%3];digits=f'{1000000+i*3719:07d}';control=letters[int(str(i%3)+digits)%23];nie=prefix+digits+control
        add('nie',i,['Documento de prueba: ',(nie,'DOCUMENTO'),'.'])
        def ccc_digit(s):
            value=11-sum(int(c)*w for c,w in zip(s,(1,2,4,8,5,10,9,7,3,6)))%11
            return str(0 if value==11 else 1 if value==10 else value)
        bank='21000418';account=f'{200051332+i*71:010d}'
        bban=bank+ccc_digit('00'+bank)+ccc_digit(account)+account
        iban='ES'+f'{98-int(bban+"142800")%97:02d}'+bban
        formatted=[iban,' '.join(iban[j:j+4] for j in range(0,24,4)),'-'.join(iban[j:j+4] for j in range(0,24,4)),iban.lower()][i%4]
        add('iban',i,['Cuenta para ensayo: ',(formatted,'IBAN'),'.'])
        passport='Q'+chr(65+i%26)+chr(65+(i*7)%26)+f'{230000+i*137:06d}'
        add('passport',i,['Pasaporte sintético: ',(passport,'DOCUMENTO'),'.'])
        day=1+i%28;month=1+i%12;year=2030+i%7
        date=[f'{day:02d}/{month:02d}/{year}',f'{year}-{month:02d}-{day:02d}',f'{day:02d}.{month:02d}.{year}',f'{day} de octubre de {year}',f'{day:02d}-{month:02d}-{year}'][i%5]
        add('date',i,['La fecha prevista es ',(date,'FECHA'),'.'])
        neg_email=[f'ev{i}example.com',f'ev{i}@localhost',f'ev{i}@','@example.com',f'ev{i} at example.com'][i%5]
        add('email',50+i,['Dato incompleto: '+neg_email])
        neg_phone=[str(120000+i),str(12345678900+i),f'+1 202-555-{100+i:04d}',str(190000000+i),f'600ABC{i:03d}'][i%5]
        add('phone',50+i,['Referencia incompleta: '+neg_phone])
        add('nif',50+i,['NIF erróneo: '+f'{n:08d}'+letters[(n%23+1)%23]])
        add('nie',50+i,['NIE erróneo: '+prefix+digits+letters[(int(str(i%3)+digits)%23+1)%23]])
        bad_iban=iban[:2]+f'{(int(iban[2:4])+1)%100:02d}'+iban[4:]
        add('iban',50+i,['Cuenta errónea: '+bad_iban])
        add('passport',50+i,['Referencia: '+['QA123456','QABC123456','QAB12345','QAB1234567','123QAB456'][i%5]])
        add('date',50+i,['Fecha inválida: '+['44/13/2032','2032-13-44','00/10/2035','32.12.2035','10 de mesinventado de 2035'][i%5]])
    first=['Lucía','Marcos','Elena','Javier','Paula','Sergio','Marta','Daniel','Clara','Pablo','Irene','Diego','Alba','Rubén','Nuria','Hugo','Silvia','Andrés','Carmen','Víctor']
    last=['Serrano','Molina','Cabrera','Navarro','Vega','Romero','Campos','Torres','Gil','Fuentes','Ramos','Santos','Vidal','Blanco','Ortiz','Suárez','Castro','Morales','Delgado','Reyes']
    companies=['Editorial Bruma','Estudios Horizonte','Producciones Horizonte','Banco del Río','Luz Azul','Televisión Costera','Sonido Prisma','Distribuidora Estrella','Fundación Encuentro','Teatro Aurora','Agencia Nexo','Cine Atlántico','Radio Capital','Taller Sónico','Imprenta Central','Laboratorios Delta','Clínica Alameda','Universidad del Norte','Orquesta del Puerto','Transportes Sierra']
    cities=['Madrid','Barcelona','Valencia','Sevilla','Bilbao','Málaga','Zaragoza','Granada','Córdoba','Toledo','Salamanca','Valladolid','Alicante','Santander','Burgos','Pamplona','Cáceres','Oviedo','Murcia','Segovia']
    for i in range(100):
        person=(first[i%20]+' '+last[(i*7+i//20)%20],'PERSONA')
        org=(companies[(i*3+i//20)%20],'ORGANIZACION');loc=(cities[(i*11+i//20)%20],'UBICACION')
        templates=[
            [person,' trabaja para ',org,' y vive en ',loc,'.'],
            ['La entrevista con ',person,' se realizó en ',loc,' para ',org,'.'],
            [org,' encargó a ',person,' la revisión de sonido en ',loc,'.'],
            ['Desde ',loc,', ',person,' envió la propuesta a ',org,'.'],
            ['El contrato entre ',person,' y ',org,' se firmó en ',loc,'.'],
            ['Ayer ',person,' presentó en ',loc,' un informe para ',org,'.'],
            ['El equipo de ',org,' viajó a ',loc,' con ',person,'.'],
            ['Hablamos con ',person,' sobre las grabaciones de ',org,' en ',loc,'.'],
            ['La reunión de ',org,' en ',loc,' contó con ',person,'.'],
            [person,' revisará el montaje que ',org,' prepara en ',loc,'.'],
        ]
        add('ner',i,templates[i%10])
    for i in range(50):
        term=f'Niebla Azul {i:02d}'
        add('literal',i,['😀 ',(term,'PROYECTO'),'; X'+term+'; '+term+'X; '+term.lower()])
    add('unknown_production',0,['El largometraje ficticio Cristal de Mercurio presenta al personaje Nárvex.'])
    return {'schema_version':1,'purpose':'Synthetic holdout v1; not detector training data','cases':cases}


if __name__=='__main__':
    root=Path(__file__).parent/'fixtures';root.mkdir(exist_ok=True)
    raw=(json.dumps(build(),ensure_ascii=False,indent=2)+'\n').encode()
    with (root/'evaluation-v1.json').open('xb') as f:f.write(raw)
    manifest={'sha256':sha256(raw).hexdigest(),'cases':len(build()['cases']),
              'frozen_against_commit':'8c23fccc67c0d377180e483e7fa1c82bf260ca2b',
              'policy':'Never tune against these results and continue calling v1 independent acceptance.'}
    with (root/'evaluation-v1.manifest.json').open('x') as f:json.dump(manifest,f,indent=2);f.write('\n')
