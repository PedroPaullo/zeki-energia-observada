"""Read-only analytical service shared by Streamlit, CLI and exports."""
from __future__ import annotations
import csv, io, json, zipfile, tempfile, shutil
from statistics import median
from pathlib import Path
from .storage import root_dir, read_json, connect, rows, literal, sha256, utc_now
from .rules import evaluate, usable, previous_period

KEYS = ('records', 'affected', 'p90_hours')
NOTICE = 'Comparação descritiva; equivalência estatística não estabelecida.'
UF_IBGE = {'11':'RO','12':'AC','13':'AM','14':'RR','15':'PA','16':'AP','17':'TO','21':'MA','22':'PI','23':'CE','24':'RN','25':'PB','26':'PE','27':'AL','28':'SE','29':'BA','31':'MG','32':'ES','33':'RJ','35':'SP','41':'PR','42':'SC','43':'RS','50':'MS','51':'MT','52':'GO','53':'DF'}

def _delta(a,b):
 return {k:{'current':a.get(k),'previous':b.get(k),'absolute':None if a.get(k) is None or b.get(k) is None else a[k]-b[k], 'percent':None if a.get(k) is None or b.get(k) in (None,0) else 100*(a[k]/b[k]-1)} for k in KEYS}

def _contexts(c, all_months, history, current, selection, mode, enabled, relation):
 result={'notice':NOTICE,'own_history':{'status':'indisponível'},'distributor':{'status':'desativado'},'national':{'status':'desativado','reason':'Comparação contextual desativada.'}}
 scope={(selection['cnpj'],selection['conjunto'],m['_eo_period']) for m in history}
 if not enabled: return result,scope
 p=selection['period']; prev=previous_period(p); six=[]; cursor=p
 for _ in range(6): cursor=previous_period(cursor); six.append(cursor)
 by_period={m['_eo_period']:m for m in history}
 if current and all(x in by_period and usable(by_period[x]) for x in six):
  baseline={k:median(by_period[x][k] for x in six) for k in KEYS}
  result['own_history']={'status':'disponível','periods':sorted(six),'median':baseline,'changes':_delta(current,baseline),'note':'Mediana de seis indicadores mensais; não estima sazonalidade nem P90 agregado.'}
 else: result['own_history']['reason']='São necessárias seis competências anteriores consecutivas utilizáveis.'
 paired={}
 for m in all_months:
  if m['_eo_period'] in (p,prev): paired.setdefault((m['_eo_cnpj'],m['_eo_conjunto']),{})[m['_eo_period']]=m
 eligible={k:v for k,v in paired.items() if p in v and prev in v and usable(v[p]) and usable(v[prev])}
 peers={k:v for k,v in eligible.items() if k[0]==selection['cnpj'] and k[1]!=selection['conjunto']}
 distributions=[{'cnpj':k[0],'conjunto':k[1],'changes':_delta(v[p],v[prev])} for k,v in sorted(peers.items()) if all(v[prev][metric] not in (None,0) for metric in KEYS)]
 total_peers=sum(k[0]==selection['cnpj'] and k[1]!=selection['conjunto'] for k in paired)
 result['distributor']={'status':'disponível' if distributions else 'indisponível','included':len(distributions),'excluded':total_peers-len(distributions),'distribution':distributions,'median_changes':{k:median(d['changes'][k]['percent'] for d in distributions) if distributions else None for k in KEYS},'note':'Outros conjuntos da mesma distribuidora; exclui o conjunto selecionado. Volumes não representam qualidade relativa.'}
 for d in distributions:
  scope.update((d['cnpj'],d['conjunto'],month) for month in (prev,p))
 scope.update((a,b,month) for a,b in paired if a==selection['cnpj'] for month in (prev,p))
 if mode!='national': result['national']={'status':'desativado','reason':'Modo amostra: recorte nacional não autorizado.'}; return result,scope
 scope.update((a,b,month) for a,b in paired for month in (prev,p))
 own=[k for k in eligible if k[0]==selection['cnpj']]; other=[k for k in eligible if k[0]!=selection['cnpj']]
 if not own or not other:
  result['national']={'status':'indisponível','reason':'Não há população fixa utilizável nos dois meses para ambos os recortes.'}; return result,scope
 c.execute('CREATE OR REPLACE TEMP TABLE context_population(cnpj VARCHAR, conjunto VARCHAR, cohort VARCHAR)')
 c.executemany('INSERT INTO context_population VALUES (?,?,?)',[(a,b,'distributor') for a,b in own]+[(a,b,'others') for a,b in other])
 metrics=rows(c,f'''SELECT pop.cohort, r._eo_period, count(*) records, sum(r._eo_affected) affected, quantile_cont(r._eo_duration,.9) p90_hours FROM {relation} r JOIN context_population pop ON r._eo_cnpj=pop.cnpj AND r._eo_conjunto=pop.conjunto WHERE r._eo_key_valid AND NOT r._eo_duplicate AND r._eo_period IN (?,?) GROUP BY 1,2''',[prev,p])
 cohorts={name:{m['_eo_period']:{k:m[k] for k in KEYS} for m in metrics if m['cohort']==name} for name in ('distributor','others')}
 result['national']={'status':'disponível','included':len(eligible),'excluded':len(paired)-len(eligible),'population': [{'cnpj':a,'conjunto':b} for a,b in sorted(eligible)],'distributor_groups':len(own),'other_groups':len(other),'distributor_metrics':cohorts['distributor'],'other_metrics':cohorts['others'],'changes':{name:_delta(ms[p],ms[prev]) for name,ms in cohorts.items()},'note':'População fixa de conjuntos utilizáveis em ambos os meses; demais distribuidoras carregadas, sem alegação de cobertura nacional completa.'}
 scope.update((a,b,month) for a,b in eligible for month in (prev,p))
 return result,scope

def _revision(c,a,data_dir,selection,periods):
 old_version=a.get('previous_version'); result={'detected':False,'status':'sem aquisição anterior comparável','previous_version':old_version,'compared_periods':[],'changed_periods':[]}
 if not old_version: return result
 old=read_json(root_dir(data_dir)/'models'/old_version/'manifest.json')
 if not old or old.get('mode')!=a.get('mode'): return result
 old_path=root_dir(data_dir)/old['model_path']
 if not old_path.exists(): result['status']='versão anterior indisponível'; return result
 new_path=root_dir(data_dir)/a['model_path']; result['status']='conteúdo comparado'
 for period in periods:
  signatures=[]
  for path in (old_path,new_path):
   sql='SELECT _eo_hash, count(*) n FROM read_parquet(?) WHERE _eo_cnpj=? AND _eo_conjunto=? AND _eo_period=? AND _eo_key_valid AND NOT _eo_duplicate'; params=[str(path),selection['cnpj'],selection['conjunto'],period]
   if selection.get('municipio') is not None: sql+=' AND _eo_municipio=?'; params.append(selection['municipio'])
   signatures.append(rows(c,sql+' GROUP BY 1 ORDER BY 1',params))
  if not signatures[0]: continue
  result['compared_periods'].append(period)
  if signatures[0]!=signatures[1]: result['changed_periods'].append(period)
 result['detected']=bool(result['changed_periods']); return result

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
      return {'mode':a['mode'],'periods':[x['p'] for x in rows(c,f'SELECT DISTINCT _eo_period AS p FROM {rel} WHERE _eo_key_valid ORDER BY 1')], 'distributors':rows(c,f'SELECT DISTINCT _eo_cnpj AS cnpj, NomAgente AS display_name FROM {rel} WHERE _eo_key_valid ORDER BY 2'), 'conjuntos':rows(c,f'SELECT DISTINCT _eo_cnpj AS cnpj, _eo_conjunto AS conjunto, DscConjuntoUnidadeConsumidora AS display_name FROM {rel} WHERE _eo_key_valid ORDER BY 3'), 'municipalities':[x['municipio'] for x in rows(c,f'SELECT DISTINCT _eo_municipio AS municipio FROM {rel} WHERE _eo_municipio IS NOT NULL ORDER BY 1')]}
def _monthly(c,a,data_dir,cnpj,conjunto,period):
 rel='read_parquet('+literal((root_dir(data_dir)/a['monthly_path']).as_posix())+')'
 r=rows(c,f"SELECT * FROM {rel} WHERE _eo_cnpj=? AND _eo_conjunto=? AND _eo_period=?",[cnpj,conjunto,period]); return r[0] if r else None
def queue(period, cnpj=None, municipio=None, data_dir=None):
 a=_active(data_dir); previous=f'{int(period[:4])-1:04d}-12' if period.endswith('-01') else period[:5]+f'{int(period[5:])-1:02d}'
 with _con(a,data_dir) as c:
  rel=_monthly_relation(c,a,data_dir,municipio); q=f'''SELECT cur._eo_cnpj cnpj,cur._eo_conjunto conjunto,cur.records,cur.affected,prev.affected previous_affected,cur.affected-prev.affected change FROM {rel} cur LEFT JOIN {rel} prev ON cur._eo_cnpj=prev._eo_cnpj AND cur._eo_conjunto=prev._eo_conjunto AND prev._eo_period=? WHERE cur._eo_period=?'''; pars=[previous,period]
  if cnpj: q+=' AND cur._eo_cnpj=?'; pars.append(cnpj)
  result=rows(c,q+' ORDER BY change DESC NULLS LAST, affected DESC',[*pars])
  monthly=rows(c,f'SELECT * FROM {rel} WHERE _eo_period IN (?,?)',[period,previous]); lookup={(m['_eo_cnpj'],m['_eo_conjunto'],m['_eo_period']):m for m in monthly}
  names=rows(c,'SELECT _eo_cnpj, _eo_conjunto, min(NomAgente) distributor, min(DscConjuntoUnidadeConsumidora) display_name FROM read_parquet(?) GROUP BY 1,2',[str(root_dir(data_dir)/a['model_path'])]); names={(n['_eo_cnpj'],n['_eo_conjunto']):n for n in names}
  for item in result:
   key=(item['cnpj'],item['conjunto']); cur=lookup.get((*key,period)); prior=lookup.get((*key,previous)); assessment=evaluate(cur,prior,[cur],integrity=a.get('integrity_verified',False)); item.update(distributor=names.get(key,{}).get('distributor',key[0]),display_name=names.get(key,{}).get('display_name',key[1]),situation=assessment['situation']['label'],rule_id=assessment['situation']['rule_id'],reason='Ordenação por variação absoluta de afetações reportadas; a situação usa os três indicadores.')
  return result

def national_overview(period, data_dir=None, limit=12):
    """Aggregate every loaded distributor and derive an auditable short forecast.

    The forecast is a descriptive linear trend over the last three available
    monthly aggregates. It is deliberately bounded at zero and must not be
    read as a probability or causal prediction.
    """
    a=_active(data_dir)
    with _con(a,data_dir) as c:
        rel='read_parquet('+literal((root_dir(data_dir)/a['model_path']).as_posix())+')'
        aggregates=rows(c, f'''SELECT _eo_cnpj cnpj, min(NomAgente) distributor, _eo_period period,
            count(*) records, sum(_eo_affected) affected,
            quantile_cont(_eo_duration,.9) p90_hours
            FROM {rel} WHERE _eo_key_valid AND NOT _eo_duplicate
            GROUP BY 1,3 ORDER BY 1,3''')
        uf_rows=rows(c, f'''SELECT _eo_cnpj cnpj, left(nullif(_eo_municipio,''),2) uf_code, count(*) records
            FROM {rel} WHERE _eo_key_valid AND NOT _eo_duplicate GROUP BY 1,2''')
        dominant={}
        for row in uf_rows:
            if row['uf_code'] is not None and (row['cnpj'] not in dominant or row['records']>dominant[row['cnpj']][1]): dominant[row['cnpj']]=(row['uf_code'],row['records'])
    # A distributor may span multiple UFs; retain a stable dominant UF label.
    by_dist={}
    for item in aggregates:
        key=(item['cnpj'],item['period'])
        target=by_dist.setdefault(key,dict(item))
    series={}
    for (cnpj,p),item in by_dist.items():
        code=dominant.get(cnpj,(None,0))[0]
        item['uf']=UF_IBGE.get(code,'recorte IBGE '+str(code or 'não informado')); series.setdefault(cnpj,[]).append(item)
    def next_period(value):
        y,m=map(int,value.split('-')); return f'{y+1:04d}-01' if m==12 else f'{y:04d}-{m+1:02d}'
    output=[]
    for cnpj,items in series.items():
        items.sort(key=lambda x:x['period']); observed=[x for x in items if x['period']<=period]
        if not observed: continue
        tail=observed[-3:]; values=[float(x['affected'] or 0) for x in tail]
        slope=(values[-1]-values[0])/(len(values)-1) if len(values)>1 else None
        last=observed[-1]; forecast=None if slope is None else max(0.0,values[-1]+slope)
        output.append({'cnpj':cnpj,'distributor':last['distributor'],'uf':last['uf'],'period':last['period'],'records':last['records'],'affected':last['affected'],'p90_hours':last['p90_hours'],'history_periods':[x['period'] for x in tail],'forecast_period':next_period(last['period']),'forecast_affected':forecast,'forecast_method':'tendência linear dos últimos até 3 agregados; mínimo 0','forecast_disclaimer':'Projeção descritiva; não é probabilidade, previsão causal ou garantia operacional.'})
    output.sort(key=lambda x:x['affected'],reverse=True)
    return {'mode':a['mode'],'period':period,'distributors_loaded':len(output),'rows':output[:limit],'all_rows':output,'notice':'Recorte nacional das distribuidoras carregadas. UF é derivada dos dois primeiros dígitos do código IBGE dominante por registros; não é uma coluna original da fonte. '+output[0]['forecast_disclaimer'] if output else 'Sem dados.'}

def _monthly_relation(c,a,data_dir,municipio=None):
 if municipio is None: return 'read_parquet('+literal((root_dir(data_dir)/a['monthly_path']).as_posix())+')'
 from .pipeline import monthly_sql
 relation='read_parquet('+literal((root_dir(data_dir)/a['model_path']).as_posix())+')'
 return '('+monthly_sql(where='_eo_key_valid AND NOT _eo_duplicate AND _eo_municipio='+literal(municipio),relation=relation)+')'
def _quality(c,relation,selection,assessment):
 from .pipeline import REQUIRED
 present=[r['column_name'] for r in rows(c,'DESCRIBE SELECT * FROM '+relation)]; by_period={}
 expressions=[]
 for field in ('QtdConsumidoresAfetados','DatInicioInterrupcao','DatFimInterrupcao'):
  expressions.append(f"count(*) FILTER(WHERE nullif(trim({field}),'') IS NULL) {field}_missing")
  valid='_eo_affected' if field=='QtdConsumidoresAfetados' else f"coalesce(try_cast({field} AS TIMESTAMP),try_strptime({field},'%d/%m/%Y %H:%M:%S'),try_strptime({field},'%d/%m/%Y %H:%M'))"
  expressions.append(f"count(*) FILTER(WHERE nullif(trim({field}),'') IS NOT NULL AND {valid} IS NULL) {field}_invalid")
 query=f"SELECT _eo_period,count(*) records,count(*) FILTER(WHERE _eo_duration IS NULL) duration_unusable,{','.join(expressions)} FROM {relation} WHERE _eo_cnpj=? AND _eo_conjunto=? AND _eo_period<=? AND _eo_key_valid AND NOT _eo_duplicate GROUP BY 1 ORDER BY 1"
 for r in rows(c,query,[selection['cnpj'],selection['conjunto'],selection['period']]):
  by_period[r['_eo_period']]={'records':r['records'],'missing_by_field':{f:r[f+'_missing'] for f in ('QtdConsumidoresAfetados','DatInicioInterrupcao','DatFimInterrupcao')},'invalid_by_field':{f:r[f+'_invalid'] for f in ('QtdConsumidoresAfetados','DatInicioInterrupcao','DatFimInterrupcao')},'duration_unusable':r['duration_unusable']}
 quality={'schema':{'present':sorted(set(REQUIRED)&set(present)),'missing':sorted(set(REQUIRED)-set(present))},'by_period':by_period}
 for component in assessment['confidence']['components']:
  if component['name'] in ('Schema','Campos necessários'): component['details']=quality['schema']
  if component['name'] in ('Ausências','Ausências e inválidos'): component['details']=by_period
 return quality

def _participation(all_months,current,period):
 values=[m['affected'] for m in all_months if m['_eo_period']==period and m['affected'] is not None]; denominator=sum(values) if values else None
 return {'affected':current['affected'],'denominator_affected':denominator,'percent':100*current['affected']/denominator if current['affected'] is not None and denominator else None,'note':'Participação nas afetações válidas reportadas no mês e filtros carregados; não é participação em consumidores únicos.'}

def _reported_signals(c, relation, selection):
 """Describe source-reported classifications without treating them as causal proof."""
 periods=[selection['comparison_period'],selection['period']]
 result={'status':'descritivo','periods':periods,'fields':{},'notice':'Campos de origem, tipo, causa e detalhe são classificações reportadas no registro. Eles orientam hipótese e conferência; não provam causa raiz, responsabilidade ou nexo causal.'}
 present={r['column_name'] for r in rows(c,'DESCRIBE SELECT * FROM '+relation)}
 for field in ('DscFatoGeradorOrigem','DscFatoGeradorTipo','DscFatoGeradorCausa','DscFatoGeradorDetalhe'):
  if field not in present:
   result['fields'][field]=[]
   continue
  grouped=rows(c,f'''SELECT _eo_period, coalesce(nullif(trim({field}),''),'Não informado') category,
    count(*) records, sum(_eo_affected) affected_reported
    FROM {relation} WHERE _eo_cnpj=? AND _eo_conjunto=? AND _eo_period IN (?,?) AND _eo_key_valid AND NOT _eo_duplicate
    GROUP BY 1,2 ORDER BY 1, affected_reported DESC NULLS LAST, records DESC''',[selection['cnpj'],selection['conjunto'],*periods])
  result['fields'][field]=grouped
 return result

def build_dossier(cnpj,conjunto,period,municipio=None,context=True,data_dir=None):
 a=_active(data_dir); previous=f'{int(period[:4])-1:04d}-12' if period.endswith('-01') else period[:5]+f'{int(period[5:])-1:02d}'
 with _con(a,data_dir) as c:
  selection={'cnpj':cnpj,'conjunto':conjunto,'period':period,'comparison_period':previous,'municipio':municipio}
  rel=_monthly_relation(c,a,data_dir,municipio)
  all_months=rows(c,f'SELECT * FROM {rel} WHERE _eo_period<=? ORDER BY _eo_period',[period])
  history=[m for m in all_months if m['_eo_cnpj']==cnpj and m['_eo_conjunto']==conjunto]
  current=next((m for m in history if m['_eo_period']==period),None); prior=next((m for m in history if m['_eo_period']==previous),None)
  if current is None: raise ValueError('O recorte selecionado não possui registros na competência atual.')
  revision=_revision(c,a,data_dir,selection,sorted({previous,*[m['_eo_period'] for m in history]})); assessment=evaluate(current,prior,history,revised=revision['detected'],integrity=a.get('integrity_verified',False))
  rrel='read_parquet('+literal((root_dir(data_dir)/a['model_path']).as_posix())+')'
  if municipio is not None: rrel='(SELECT * FROM '+rrel+' WHERE _eo_municipio='+literal(municipio)+')'
  contextual,scope=_contexts(c,all_months,history,current,selection,a['mode'],context,rrel)
  scope.update((m['_eo_cnpj'],m['_eo_conjunto'],period) for m in all_months if m['_eo_period']==period)
  quality=_quality(c,rrel,selection,assessment); participation=_participation(all_months,current,period); reported_signals=_reported_signals(c,rrel,selection)
  raw=rows(c,f'SELECT * FROM {rrel} WHERE _eo_cnpj=? AND _eo_conjunto=? AND _eo_period IN (?, ?) AND NOT _eo_duplicate ORDER BY _eo_period DESC, _eo_row LIMIT 100',[cnpj,conjunto,period,previous])
  return {'selection':selection,'current':current,'previous':prior,'history':history,'assessment':assessment,'source':a,'revision':revision,'quality':quality,'participation':participation,'reported_signals':reported_signals,'records_preview':raw,'records_preview_limit':100,'evidence_periods':sorted({x[2] for x in scope}),'evidence_scope':[{'cnpj':x,'conjunto':y,'period':z} for x,y,z in sorted(scope)],'formulas':{'Registros':'count(*) após exclusão auditada de duplicatas e chaves inválidas','Afetações reportadas':'SUM(QtdConsumidoresAfetados válidos); nulos não viram zero','P90 duração':'quantile_cont((fim-início)/hora, 0.9) sobre registros válidos','Variação absoluta':'atual - anterior','Variação percentual':'100 * (atual / anterior - 1), indisponível se anterior = 0','Mediana contextual':'mediana das variações individuais elegíveis','P90 agregado contextual':'quantile_cont das durações dos registros da população fixa; nunca média de P90'},'limitations':['Aumento de interrupções não prova causa.','Classificações de origem, tipo, causa e detalhe são reportadas na fonte; não provam causa raiz.','Município identifica o equipamento, não necessariamente consumidores afetados.','Ausência de dados não equivale a ausência de interrupções.','Não substitui análise regulatória ou técnica.','Afetações reportadas não representam consumidores únicos.','A base não inclui permissionárias e cooperativas.'],'context':contextual}
def export_dossier(dossier,data_dir=None,output_dir='exports'):
 out=Path(output_dir); out.mkdir(parents=True,exist_ok=True); selection=dossier['selection']; base=f"dossie_{selection['cnpj']}_{selection['conjunto']}_{selection['period']}"; path=out/(base+'.zip')
 active=dossier['source']; model=root_dir(data_dir)/active['model_path']
 with tempfile.TemporaryDirectory(prefix='evidencias_',dir=out) as temporary:
  folder=Path(temporary); csv_path=folder/'registros.csv'
  with _con(active,data_dir) as con:
   con.execute('CREATE TEMP TABLE evidence_scope(cnpj VARCHAR, conjunto VARCHAR, period VARCHAR)')
   con.executemany('INSERT INTO evidence_scope VALUES (?,?,?)',[(x['cnpj'],x['conjunto'],x['period']) for x in dossier['evidence_scope']])
   query='SELECT r.*, CASE WHEN r._eo_duplicate THEN \'duplicata excluída\' WHEN NOT r._eo_key_valid THEN \'chave inválida excluída\' ELSE \'aceito; valores inválidos excluídos por indicador\' END AS evidence_status FROM read_parquet(?) r JOIN evidence_scope s ON r._eo_cnpj=s.cnpj AND r._eo_conjunto=s.conjunto AND r._eo_period=s.period'
   params=[str(model)]
   if selection.get('municipio') is not None: query+=' WHERE r._eo_municipio=?'; params.append(selection['municipio'])
   cursor=con.execute(query+' ORDER BY r._eo_cnpj,r._eo_conjunto,r._eo_period,r._eo_row',params)
   with csv_path.open('w',encoding='utf-8',newline='') as handle:
    writer=csv.writer(handle); writer.writerow(x[0] for x in cursor.description); count=0
    while batch:=cursor.fetchmany(1000): writer.writerows(batch); count+=len(batch)
  md_path=folder/'dossie.md'; md_path.write_text(_markdown(dossier),encoding='utf-8')
  manifest={'format_version':'2.0','exported_at':utc_now(),'dossier':dossier,'records_exported':count,'files':{name:{'sha256':sha256(folder/name),'size_bytes':(folder/name).stat().st_size} for name in ('registros.csv','dossie.md')},'reproduction':{'command':'python -m energia_observada verify CAMINHO_DO_ZIP','null_policy':'Campos CSV vazios são nulos; _eo_* preserva valores normalizados usados no cálculo.','exclusions':'_eo_duplicate=true e _eo_key_valid=false não entram nos indicadores; durações/afetações inválidas permanecem nulas.','source_hash':active['sha256'],'rules_version':dossier['assessment']['rules_version'],'manifest_hash_note':'O manifesto contém hashes dos demais membros; não contém hash de si mesmo para evitar autorreferência.'}}
  (folder/'manifesto.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,default=str,allow_nan=False),encoding='utf-8')
  staging=out/(base+'.zip.part')
  with zipfile.ZipFile(staging,'w',zipfile.ZIP_DEFLATED) as archive:
   for name in ('dossie.md','registros.csv','manifesto.json'): archive.write(folder/name,name)
  staging.replace(path)
 return path

def _markdown(dossier):
 s=dossier['selection']; a=dossier['assessment']
 sections=['# Dossiê de Investigação',f"Distribuidora {s['cnpj']} · conjunto {s['conjunto']} · {s['period']} versus {s['comparison_period']}",'## Resumo executivo']
 sections += [f"### {n.get('title',str(i))}\n\n{n['text']}\n\nReferências: {', '.join(n.get('references',[]))}" for i,n in enumerate(a['narrative'],1)]
 for title,payload in [('Indicadores atuais',dossier['current']),('Comparação anterior',dossier['previous']),('Participação no recorte',dossier.get('participation')),('Série histórica',dossier['history']),('Situação e regras',a['situation']),('Confiança da evidência',a['confidence']),('Qualidade por campo',dossier.get('quality')),('Sinais e classificações reportadas',dossier.get('reported_signals')),('Comparações contextuais',dossier['context']),('Revisão da fonte',dossier['revision']),('Fórmulas',dossier['formulas']),('Parâmetros operacionais',a['parameters']),('Versão e aquisição',{k:dossier['source'].get(k) for k in ('version','sha256','model_sha256','source_url','acquired_at','mode')})]:
  sections.append('## '+title+'\n\n```json\n'+json.dumps(payload,ensure_ascii=False,indent=2,default=str)+'\n```')
 sections.extend(['## Registros-fonte','Todos os registros do escopo analítico estão em registros.csv, com linha de origem, hash de conteúdo e motivo de exclusão. Os hashes dos arquivos estão em manifesto.json.','## Limitações','\n'.join('- '+x for x in dossier['limitations']),NOTICE])
 return '\n\n'.join(sections)+'\n'

def verify_export(path):
 """Recalculate from exported records without access to the application data directory."""
 from .pipeline import monthly_sql
 with tempfile.TemporaryDirectory(prefix='verificar_dossie_') as tmp:
  folder=Path(tmp)
  with zipfile.ZipFile(path) as archive:
   if set(archive.namelist())!={'registros.csv','dossie.md','manifesto.json'}: raise ValueError('Membros inesperados no pacote.')
   for name in archive.namelist():
    with archive.open(name) as src,(folder/name).open('wb') as dst: shutil.copyfileobj(src,dst,1024*1024)
  manifest=read_json(folder/'manifesto.json'); dossier=manifest['dossier']; selection=dossier['selection']
  for name,info in manifest['files'].items():
   if name not in ('registros.csv','dossie.md') or sha256(folder/name)!=info['sha256']: raise ValueError('Hash divergente: '+name)
  with connect(temp_dir=folder/'tmp') as c:
   # Force string identifiers: inference would remove leading zeros from CNPJ.
   c.execute("CREATE VIEW evidence AS SELECT * EXCLUDE (_eo_affected,_eo_duration,_eo_key_valid,_eo_duplicate), try_cast(_eo_affected AS DOUBLE) _eo_affected, try_cast(_eo_duration AS DOUBLE) _eo_duration, cast(_eo_key_valid AS BOOLEAN) _eo_key_valid, cast(_eo_duplicate AS BOOLEAN) _eo_duplicate FROM read_csv("+literal(str(folder/'registros.csv'))+",header=true,all_varchar=true)")
   all_months=rows(c,monthly_sql(relation='evidence')+' ORDER BY _eo_period')
   history=[m for m in all_months if m['_eo_cnpj']==selection['cnpj'] and m['_eo_conjunto']==selection['conjunto']]
   current=next((m for m in history if m['_eo_period']==selection['period']),None); previous=next((m for m in history if m['_eo_period']==selection['comparison_period']),None)
   assessment=evaluate(current,previous,history,revised=dossier['revision']['detected'],integrity=dossier['source'].get('integrity_verified',False))
   _quality(c,'evidence',selection,assessment)
   context,_=_contexts(c,all_months,history,current,selection,dossier['source']['mode'],dossier['context']['distributor']['status']!='desativado','evidence')
   checks={'current':_same(current,dossier['current']),'previous':_same(previous,dossier['previous']),'history':_same(history,dossier['history']),'assessment':_same(assessment,dossier['assessment']),'context':_same(context,dossier['context']),'markdown':(folder/'dossie.md').read_text(encoding='utf-8')==_markdown(dossier),'record_count':c.execute('SELECT count(*) FROM evidence').fetchone()[0]==manifest['records_exported']}
   if not all(checks.values()): raise ValueError('Reprodução divergente: '+str(checks))
  return {'status':'verified','checks':checks,'records':manifest['records_exported'],'source_sha256':dossier['source']['sha256'],'note':'Hashes verificam integridade do pacote; autenticidade da fonte requer confrontar o SHA-256 com a aquisição oficial. Revisão depende das aquisições preservadas e é declarada no manifesto.'}

def _same(a,b):
 if isinstance(a,dict) and isinstance(b,dict): return a.keys()==b.keys() and all(_same(a[k],b[k]) for k in a)
 if isinstance(a,list) and isinstance(b,list): return len(a)==len(b) and all(_same(x,y) for x,y in zip(a,b))
 if isinstance(a,(int,float)) and isinstance(b,(int,float)): return abs(a-b)<=1e-8*max(1,abs(a),abs(b))
 return a==b
