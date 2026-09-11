import json
import zipfile
import pytest
from energia_observada.pipeline import ingest, transform
from energia_observada.service import build_dossier, export_dossier, verify_export, queue, national_overview

HEAD='NumCNPJDistribuidora;NomAgente;CodMunicipioIBGE;CodInterrupcao;CodConjUnidadeConsumidora;DscConjuntoUnidadeConsumidora;AnoCompetencia;MesCompetencia;DatInicioInterrupcao;DatFimInterrupcao;QtdConsumidoresAfetados\n'
CNPJ='12345678000199'

def records(group='A', cnpj=CNPJ, months=(1,2), quantity=100, municipality='1234567', duration=2):
 return [f'{cnpj};Agente;{municipality};{group}-{month}-{n};{group};Conjunto {group};2026;{month};01/{month:02d}/2026 00:00:00;01/{month:02d}/2026 {duration:02d}:00:00;{quantity*(2 if month==2 else 1)}\n' for month in months for n in range(10)]

def publish(tmp_path, lines, mode='national'):
 source=tmp_path/'input.csv'; source.write_text(HEAD+''.join(lines),encoding='utf-8')
 ingest(file=source,mode=mode,data_dir=tmp_path/'data'); return transform(tmp_path/'data')

def test_context_population_and_portable_reproduction(tmp_path):
 lines=records()+records('B',quantity=50,duration=4)+records('C',cnpj='99999999000199',quantity=200,duration=8)+records('D',months=(2,))
 publish(tmp_path,lines)
 dossier=build_dossier(CNPJ,'A','2026-02',data_dir=tmp_path/'data')
 context=dossier['context']
 assert context['distributor']['included']==1
 assert context['distributor']['excluded']==1
 assert context['distributor']['median_changes']['affected']==100
 national=context['national']; assert national['included']==3 and national['excluded']==1
 assert national['distributor_metrics']['2026-02']['p90_hours']==4
 assert national['other_metrics']['2026-02']['p90_hours']==8
 package=export_dossier(dossier,data_dir=tmp_path/'data',output_dir=tmp_path/'export')
 assert verify_export(package)['status']=='verified'

def test_sample_blocks_national_and_history_uses_six_prior_months(tmp_path):
 publish(tmp_path,records(months=range(1,8)),mode='sample')
 dossier=build_dossier(CNPJ,'A','2026-07',data_dir=tmp_path/'data')
 assert dossier['context']['national']['status']=='desativado'
 assert dossier['context']['own_history']['periods']==[f'2026-{m:02d}' for m in range(1,7)]
 assert dossier['context']['own_history']['median']['affected']==1000
 # A historical selection must not use later observations for confidence.
 earlier=build_dossier(CNPJ,'A','2026-02',data_dir=tmp_path/'data')
 assert len(earlier['history'])==2
 assert earlier['assessment']['confidence']['level']=='adequada'

def test_municipality_filter_is_applied_to_metrics_queue_and_export(tmp_path):
 publish(tmp_path,records()+records('A',quantity=300,municipality='7654321'))
 dossier=build_dossier(CNPJ,'A','2026-02',municipio='1234567',data_dir=tmp_path/'data')
 assert dossier['current']['affected']==2000
 assert queue('2026-02',municipio='1234567',data_dir=tmp_path/'data')[0]['affected']==2000
 package=export_dossier(dossier,data_dir=tmp_path/'data',output_dir=tmp_path/'export')
 assert verify_export(package)['records']==20

def test_revision_ignores_reordering_new_periods_and_other_groups(tmp_path):
 initial=records()+records('B')
 publish(tmp_path,initial)
 publish(tmp_path,list(reversed(initial))+records('B',months=(3,)))
 dossier=build_dossier(CNPJ,'A','2026-02',data_dir=tmp_path/'data')
 assert not dossier['revision']['detected']
 # Same totals, changed record-level affected quantities must still be detected.
 changed=list(reversed(initial))+records('B',months=(3,))
 changed[0]=changed[0].replace(';200\n',';201\n')
 changed[1]=changed[1].replace(';200\n',';199\n')
 publish(tmp_path,changed)
 assert not build_dossier(CNPJ,'A','2026-02',data_dir=tmp_path/'data')['revision']['detected']
 changed=initial.copy(); changed[10]=changed[10].replace(';200\n',';201\n'); changed[11]=changed[11].replace(';200\n',';199\n')
 publish(tmp_path,changed)
 dossier=build_dossier(CNPJ,'A','2026-02',data_dir=tmp_path/'data')
 assert dossier['revision']['detected']
 assert dossier['revision']['changed_periods']==['2026-02']
 assert dossier['assessment']['situation']['label']=='possível alteração ou revisão da fonte'

def test_modified_export_fails_integrity_check(tmp_path):
 publish(tmp_path,records(),mode='sample')
 dossier=build_dossier(CNPJ,'A','2026-02',data_dir=tmp_path/'data')
 package=export_dossier(dossier,data_dir=tmp_path/'data',output_dir=tmp_path/'export')
 tampered=tmp_path/'tampered.zip'
 with zipfile.ZipFile(package) as src,zipfile.ZipFile(tampered,'w') as dst:
  for name in src.namelist(): dst.writestr(name,b'changed' if name=='dossie.md' else src.read(name))
 with pytest.raises(ValueError,match='Hash divergente'): verify_export(tampered)

def test_reported_categories_are_exposed_as_hypotheses_not_causality(tmp_path):
 source=tmp_path/'signals.csv'
 source.write_text(
  HEAD.rstrip()+ ';DscFatoGeradorOrigem;DscFatoGeradorCausa\n' +
  ''.join(line.rstrip()+(';Interna;Próprias do Sistema\n' if ';1;' in line else ';Externa;Terceiros\n') for line in records()),
  encoding='utf-8')
 ingest(file=source,mode='sample',data_dir=tmp_path/'data'); transform(tmp_path/'data')
 dossier=build_dossier(CNPJ,'A','2026-02',data_dir=tmp_path/'data')
 origin=dossier['reported_signals']['fields']['DscFatoGeradorOrigem']
 assert {item['category'] for item in origin}=={'Interna','Externa'}
 assert 'não provam causa raiz' in dossier['reported_signals']['notice']

def test_national_overview_includes_distributors_and_bounded_forecast(tmp_path):
 publish(tmp_path, records()+records('B',cnpj='99999999000199',quantity=200), mode='national')
 overview=national_overview('2026-02', data_dir=tmp_path/'data')
 assert overview['distributors_loaded']==2
 assert {row['cnpj'] for row in overview['all_rows']}=={CNPJ,'99999999000199'}
 assert all(row['forecast_affected'] >= 0 for row in overview['all_rows'])
 assert all(row['forecast_period']=='2026-03' for row in overview['all_rows'])
