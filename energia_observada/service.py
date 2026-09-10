"""Read-only analytical service shared by Streamlit, CLI and exports."""
from __future__ import annotations
import csv, io, json, zipfile
from pathlib import Path
from .storage import root_dir, read_json, connect, rows, literal, sha256, utc_now
from .rules import evaluate

def status(data_dir=None): return {'active':read_json(root_dir(data_dir)/'active.json'), 'last_attempt':read_json(root_dir(data_dir)/'last_attempt.json'), 'pending':read_json(root_dir(data_dir)/'pending.json')}
def _active(data_dir):
    active=status(data_dir)['active']
    if not active: raise FileNotFoundError('Não há versão válida publicada. Execute ingest e transform.')
    return active
def _con(active, data_dir): return connect(':memory:', root_dir(data_dir)/'tmp')
def choices(data_dir=None):
    a=_active(data_dir)
    with _con(a,data_dir) as c:
      rel='read_parquet('+literal((root_dir(data_dir)/a['model_path']).as_posix())+')'
      return {'mode':a['mode'],'periods':[x['p'] for x in rows(c,f'SELECT DISTINCT _eo_period p FROM {rel} WHERE _eo_key_valid ORDER BY 1')], 'distributors':rows(c,f'SELECT DISTINCT _eo_cnpj cnpj, NomAgente name FROM {rel} WHERE _eo_key_valid ORDER BY 2'), 'conjuntos':rows(c,f'SELECT DISTINCT _eo_cnpj cnpj,_eo_conjunto conjunto,DscConjuntoUnidadeConsumidora name FROM {rel} WHERE _eo_key_valid ORDER BY 3'), 'municipalities':[x['municipio'] for x in rows(c,f'SELECT DISTINCT _eo_municipio municipio FROM {rel} WHERE _eo_municipio IS NOT NULL ORDER BY 1')]}
def _monthly(c,a,data_dir,cnpj,conjunto,period):
 rel='read_parquet('+literal((root_dir(data_dir)/a['monthly_path']).as_posix())+')'
 r=rows(c,f"SELECT * FROM {rel} WHERE _eo_cnpj=? AND _eo_conjunto=? AND _eo_period=?",[cnpj,conjunto,period]); return r[0] if r else None
def queue(period, cnpj=None, municipio=None, data_dir=None):
 a=_active(data_dir); previous=f'{int(period[:4])-1:04d}-12' if period.endswith('-01') else period[:5]+f'{int(period[5:])-1:02d}'
 with _con(a,data_dir) as c:
  rel='read_parquet('+literal((root_dir(data_dir)/a['monthly_path']).as_posix())+')'; q=f'''SELECT cur._eo_cnpj cnpj,cur._eo_conjunto conjunto,cur.records,cur.affected,prev.affected previous_affected,cur.affected-prev.affected change FROM {rel} cur LEFT JOIN {rel} prev ON cur._eo_cnpj=prev._eo_cnpj AND cur._eo_conjunto=prev._eo_conjunto AND prev._eo_period=? WHERE cur._eo_period=?'''; pars=[previous,period]
  if cnpj: q+=' AND cur._eo_cnpj=?'; pars.append(cnpj)
  return rows(c,q+' ORDER BY change DESC NULLS LAST, affected DESC',[*pars])
def build_dossier(cnpj,conjunto,period,municipio=None,context=True,data_dir=None):
 a=_active(data_dir); previous=f'{int(period[:4])-1:04d}-12' if period.endswith('-01') else period[:5]+f'{int(period[5:])-1:02d}'
 with _con(a,data_dir) as c:
  current=_monthly(c,a,data_dir,cnpj,conjunto,period); prior=_monthly(c,a,data_dir,cnpj,conjunto,previous)
  rel='read_parquet('+literal((root_dir(data_dir)/a['monthly_path']).as_posix())+')'; history=rows(c,f'SELECT * FROM {rel} WHERE _eo_cnpj=? AND _eo_conjunto=? ORDER BY _eo_period',[cnpj,conjunto]); assessment=evaluate(current,prior,history,integrity=a.get('integrity_verified',False))
  rrel='read_parquet('+literal((root_dir(data_dir)/a['model_path']).as_posix())+')'; raw=rows(c,f'SELECT * EXCLUDE (_eo_hash,_eo_key_valid,_eo_duplicate) FROM {rrel} WHERE _eo_cnpj=? AND _eo_conjunto=? AND _eo_period=? AND NOT _eo_duplicate LIMIT 100',[cnpj,conjunto,period])
  return {'selection':{'cnpj':cnpj,'conjunto':conjunto,'period':period,'municipio':municipio},'current':current,'previous':prior,'history':history,'assessment':assessment,'source':a,'records_preview':raw,'records_preview_limit':100,'formulas':{'Afetações reportadas':'SUM(QtdConsumidoresAfetados válidos)','P90 duração':'quantile_cont((fim-início)/hora, 0.9)'},'limitations':['Aumento de interrupções não prova causa.','Município identifica o equipamento, não necessariamente consumidores afetados.','Ausência de dados não equivale a ausência de interrupções.','Não substitui análise regulatória ou técnica.'],'context':{'status':'descritivo' if context else 'desativado','notice':'Comparação descritiva; equivalência estatística não estabelecida.'}}
def export_dossier(dossier,data_dir=None,output_dir='exports'):
 out=Path(output_dir); out.mkdir(parents=True,exist_ok=True); base=f"dossie_{dossier['selection']['cnpj']}_{dossier['selection']['conjunto']}_{dossier['selection']['period']}"; path=out/(base+'.zip')
 manifest={'exported_at':utc_now(),'dossier':dossier}
 md='# Dossiê de Investigação\n\n'+'\n'.join(f"- {x['text']}" for x in dossier['assessment']['narrative'])+'\n\n## Limitações\n'+'\n'.join('- '+x for x in dossier['limitations'])
 with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
  z.writestr('dossie.md',md); z.writestr('manifesto.json',json.dumps(manifest,ensure_ascii=False,indent=2,default=str)); buf=io.StringIO(); data=dossier['records_preview']; w=csv.DictWriter(buf,fieldnames=list(data[0]) if data else ['no_records']); w.writeheader(); w.writerows(data); z.writestr('registros.csv',buf.getvalue())
 return path
