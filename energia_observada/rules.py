"""Transparent, deterministic triage rules. They are not regulatory thresholds."""
from __future__ import annotations
from datetime import date

RULES_VERSION = '1.0.0'
PARAMETERS = {'minimum_records': 10, 'minimum_valid_dates_pct': 95.0, 'minimum_durations': 10, 'moderate_pct': 10.0, 'relevant_pct': 25.0, 'consistent_months': 6}

def previous_period(period):
    year, month = map(int, period.split('-'))
    return f'{year-1:04d}-12' if month == 1 else f'{year:04d}-{month-1:02d}'

def usable(m):
    if not m or m.get('records', 0) < PARAMETERS['minimum_records']:
        return False
    if m.get('affected_valid', 0) != m.get('records', 0):
        return False
    if 100 * m.get('dates_valid', 0) / max(m.get('records', 1), 1) < PARAMETERS['minimum_valid_dates_pct']:
        return False
    return m.get('dates_valid', 0) >= PARAMETERS['minimum_durations']

def _change(current, previous, key):
    a, b = current.get(key), previous.get(key)
    if a is None or b is None: return {'current': a, 'previous': b, 'absolute': None, 'percent': None, 'eligible': False}
    return {'current': a, 'previous': b, 'absolute': a-b, 'percent': None if b == 0 else 100*(a/b-1), 'eligible': b != 0}

def evaluate(current, previous, history, *, revised=False, integrity=True, schema=True):
    components = [
      {'name':'Comparação mensal','value':'competência anterior presente' if previous else 'competência anterior ausente','status':'ok' if previous else 'warning'},
      {'name':'Histórico','value':f'{len(history)} competências fornecidas','status':'ok' if len(history)>=6 else 'warning'},
      {'name':'Datas válidas','value':f"{current.get('dates_valid',0) if current else 0}/{current.get('records',0) if current else 0} no mês atual",'status':'ok' if current and current.get('records') and 100*current.get('dates_valid',0)/current['records']>=95 else 'warning'},
      {'name':'Schema','value':'campos necessários presentes' if schema else 'campos necessários ausentes','status':'ok' if schema else 'error'},
      {'name':'Volume','value':f"{current.get('records',0) if current else 0} registros no mês atual",'status':'ok' if current and current.get('records',0)>=10 else 'warning'},
      {'name':'Ausências','value':'quantidades completas' if current and current.get('affected_valid')==current.get('records') else 'quantidades ausentes ou inválidas','status':'ok' if current and current.get('affected_valid')==current.get('records') else 'warning'},
      {'name':'Origem e integridade','value':'arquivo conciliado' if integrity and not revised else ('revisão detectada' if revised else 'integridade não comprovada'),'status':'ok' if integrity and not revised else 'error'},
    ]
    changes = {k:_change(current, previous, k) for k in ('records','affected','p90_hours')} if current and previous else {}
    reasons=[]; rule=''; label=''
    if not integrity or not schema or not usable(current) or (previous is not None and not usable(previous)):
        label, rule = 'dados insuficientes','S01_INSUFFICIENT'; reasons.append('Os requisitos mínimos de qualidade ou volume não foram atendidos.')
    elif revised:
        label, rule = 'possível alteração ou revisão da fonte','S02_SOURCE_REVISION'; reasons.append('Versões oficiais divergiram nos registros analíticos deste recorte.')
    elif not previous or previous.get('period') != previous_period(current['period']) or any(v['percent'] is None for v in changes.values()):
        label, rule = 'sem comparação','S03_NO_COMPARISON'; reasons.append('Não há base percentual comparável no mês civil anterior.')
    else:
        values=[v['percent'] for v in changes.values()]
        ups=[(k,v) for k,v in changes.items() if v['percent'] >= PARAMETERS['moderate_pct']]
        downs=[(k,v) for k,v in changes.items() if v['percent'] <= -PARAMETERS['moderate_pct']]
        if any(v['percent'] >= PARAMETERS['relevant_pct'] for v in changes.values()): label,rule='aumento relevante','S04_RELEVANT_INCREASE'
        elif ups: label,rule='deterioração moderada','S05_MODERATE_DETERIORATION'
        elif downs: label,rule='melhora','S06_IMPROVEMENT'
        else: label,rule='estabilidade','S07_STABILITY'
        reasons.append('Critérios operacionais versionados; não representam causalidade nem padrão regulatório.')
    divergent=bool(changes) and any(v.get('percent',0)>=10 for v in changes.values()) and any(v.get('percent',0)<=-10 for v in changes.values())
    consecutive=0
    for m in sorted(history, key=lambda x:x['period'], reverse=True):
        if usable(m) and (not consecutive or m['period']==previous_period(last)):
            consecutive+=1; last=m['period']
        else: break
    confidence='insuficiente' if any(c['status']=='error' for c in components) or not usable(current) else ('limitada' if not previous or not usable(previous) or revised else ('consistente' if consecutive>=6 and all((m.get('dates_valid',0)==m.get('records',0)) for m in history[-6:]) else 'adequada'))
    narrative=[{'text':f'Situação: {label}.', 'references':['situation.rule_id']},{'text':'O dossiê apoia investigação e não prova causa.', 'references':['limitations']}]
    return {'rules_version':RULES_VERSION,'parameters':PARAMETERS,'situation':{'label':label,'rule_id':rule,'reasons':reasons,'divergent':divergent},'confidence':{'level':confidence,'components':components},'changes':changes,'narrative':narrative}
