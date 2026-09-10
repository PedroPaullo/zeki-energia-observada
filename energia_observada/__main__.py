import argparse,json,os,subprocess,sys
from pathlib import Path
from . import pipeline,service
p=argparse.ArgumentParser(); s=p.add_subparsers(dest='cmd',required=True)
for x in ('ingest','update'):
 q=s.add_parser(x);q.add_argument('--year',type=int,default=2026);q.add_argument('--data-dir',type=Path)
 if x=='ingest':
  q.add_argument('--file',type=Path);q.add_argument('--metadata',type=Path);q.add_argument('--mode',choices=['national','sample'],default='national')
for x in ('transform','status','demo'):
 q=s.add_parser(x);q.add_argument('--data-dir',type=Path)
 if x=='demo': q.add_argument('--launch',action='store_true');q.add_argument('--port',type=int,default=8502)
q=s.add_parser('dossier');q.add_argument('--cnpj',required=True);q.add_argument('--conjunto',required=True);q.add_argument('--period',required=True);q.add_argument('--data-dir',type=Path)
q=s.add_parser('verify');q.add_argument('package',type=Path)
a=p.parse_args();
if a.cmd=='ingest': r=pipeline.ingest(a.year,file=a.file,metadata=json.loads(a.metadata.read_text(encoding='utf-8')) if a.metadata else None,mode=a.mode,data_dir=a.data_dir)
elif a.cmd=='update': r=pipeline.update(a.year,data_dir=a.data_dir)
elif a.cmd=='transform': r=pipeline.transform(a.data_dir)
elif a.cmd=='demo':
 manifest=json.loads((Path(__file__).resolve().parent.parent/'demo'/'manifest.json').read_text(encoding='utf-8'))
 a.data_dir=a.data_dir or Path(__file__).resolve().parent.parent/'data-demo'
 r=pipeline.ingest(2026,file=Path(__file__).resolve().parent.parent/'demo'/'aneel_2026_enel_ce_jurema_13317.parquet',metadata=manifest,mode='sample',data_dir=a.data_dir)
 r=pipeline.transform(a.data_dir)
 if a.launch:
  project=Path(__file__).resolve().parent.parent
  raise SystemExit(subprocess.call([sys.executable,'-m','streamlit','run',str(project/'app.py'),'--server.port',str(a.port)],env=dict(os.environ,ENERGIA_DATA_DIR=str(a.data_dir.resolve())),cwd=project))
elif a.cmd=='dossier': r=service.build_dossier(a.cnpj,a.conjunto,a.period,data_dir=a.data_dir)
elif a.cmd=='verify': r=service.verify_export(a.package)
else:r=service.status(a.data_dir)
print(json.dumps(r,ensure_ascii=False,indent=2,default=str))
