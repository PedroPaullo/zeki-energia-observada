import json
import zipfile
from pathlib import Path
import pytest
from energia_observada.pipeline import ingest, transform, QualityError
from energia_observada.service import build_dossier, export_dossier, choices

HEAD='NumCNPJDistribuidora;NomAgente;CodMunicipioIBGE;CodInterrupcao;CodConjUnidadeConsumidora;DscConjuntoUnidadeConsumidora;AnoCompetencia;MesCompetencia;DatInicioInterrupcao;DatFimInterrupcao;QtdConsumidoresAfetados\n'
def test_pipeline_and_export(tmp_path):
 rows=[]
 for month,base in [(1,100),(2,130)]:
  for n in range(10): rows.append(f'12345678000199;Teste;1234567;{month}-{n};C1;Conjunto teste;2026;{month:02d};01/{month:02d}/2026 00:00:00;01/{month:02d}/2026 02:00:00;{base}\n')
 source=tmp_path/'source.csv';source.write_text(HEAD+''.join(rows),encoding='utf-8')
 meta=ingest(2026,file=source,mode='sample',data_dir=tmp_path/'data')
 active=transform(tmp_path/'data')
 assert active['profile']['accepted_rows']==20
 assert choices(tmp_path/'data')['distributors']==[{'cnpj':'12345678000199','display_name':'Teste'}]
 d=build_dossier('12345678000199','C1','2026-02',data_dir=tmp_path/'data')
 assert d['assessment']['situation']['label']=='aumento relevante'
 bundle=export_dossier(d,data_dir=tmp_path/'data',output_dir=tmp_path/'exports')
 assert bundle.exists()
 with zipfile.ZipFile(bundle) as archive:
  assert set(archive.namelist()) == {'dossie.md','registros.csv','manifesto.json'}
  exported=list(archive.open('registros.csv'))
  assert len(exported)==21

def test_idempotent_ingest_keeps_active_snapshot(tmp_path):
 source=tmp_path/'source.csv'; source.write_text(HEAD+'12345678000199;Teste;1234567;A;C1;Teste;2026;01;01/01/2026 00:00:00;01/01/2026 02:00:00;1\n'*10,encoding='utf-8')
 first=ingest(2026,file=source,data_dir=tmp_path/'data'); transform(tmp_path/'data')
 assert ingest(2026,file=source,data_dir=tmp_path/'data')['version']==first['version']

def test_schema_change_is_rejected_and_not_published(tmp_path):
 source=tmp_path/'invalid.csv'; source.write_text('coluna;errada\n1;2\n',encoding='utf-8')
 with pytest.raises(Exception): ingest(2026,file=source,data_dir=tmp_path/'data')
