import argparse,json
from pathlib import Path
from . import pipeline,service
p=argparse.ArgumentParser(); s=p.add_subparsers(dest='cmd',required=True)
for x in ('ingest','update'): q=s.add_parser(x);q.add_argument('--year',type=int,default=2026)
s.add_parser('transform');s.add_parser('status');s.add_parser('demo');q=s.add_parser('dossier');q.add_argument('--cnpj',required=True);q.add_argument('--conjunto',required=True);q.add_argument('--period',required=True)
a=p.parse_args();
if a.cmd=='ingest': r=pipeline.ingest(a.year)
elif a.cmd=='update': r=pipeline.update(a.year)
elif a.cmd=='transform': r=pipeline.transform()
elif a.cmd=='demo':
 manifest=json.loads((Path(__file__).resolve().parent.parent/'demo'/'manifest.json').read_text(encoding='utf-8'))
 r=pipeline.ingest(2026,file=Path(__file__).resolve().parent.parent/'demo'/'aneel_2026_enel_ce_jurema_13317.parquet',metadata=manifest,mode='sample')
 r=pipeline.transform()
elif a.cmd=='dossier': r=service.build_dossier(a.cnpj,a.conjunto,a.period)
else:r=service.status()
print(json.dumps(r,ensure_ascii=False,indent=2,default=str))
