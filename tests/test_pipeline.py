import json
import zipfile
from pathlib import Path
from energia_observada.pipeline import ingest, transform
from energia_observada.service import build_dossier, export_dossier

HEAD='NumCNPJDistribuidora;NomAgente;CodMunicipioIBGE;CodInterrupcao;CodConjUnidadeConsumidora;DscConjuntoUnidadeConsumidora;AnoCompetencia;MesCompetencia;DatInicioInterrupcao;DatFimInterrupcao;QtdConsumidoresAfetados\n'
def test_pipeline_and_export(tmp_path):
 rows=[]
 for month,base in [(1,100),(2,130)]:
  for n in range(10): rows.append(f'12345678000199;Teste;1234567;{month}-{n};C1;Conjunto teste;2026;{month:02d};01/{month:02d}/2026 00:00:00;01/{month:02d}/2026 02:00:00;{base}\n')
 source=tmp_path/'source.csv';source.write_text(HEAD+''.join(rows),encoding='utf-8')
 meta=ingest(2026,file=source,mode='sample',data_dir=tmp_path/'data')
 active=transform(tmp_path/'data')
 assert active['profile']['accepted_rows']==20
 d=build_dossier('12345678000199','C1','2026-02',data_dir=tmp_path/'data')
 assert d['assessment']['situation']['label']=='aumento relevante'
 bundle=export_dossier(d,output_dir=tmp_path/'exports')
 assert bundle.exists()
 with zipfile.ZipFile(bundle) as archive:
  assert set(archive.namelist()) == {'dossie.md','registros.csv','manifesto.json'}
