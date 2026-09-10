"""Versioned operational rules; thresholds are neither causal nor regulatory."""
from __future__ import annotations

RULES_VERSION = '1.1.0'
PARAMETERS = {'minimum_records': 10, 'minimum_valid_dates_pct': 95.0, 'minimum_durations': 10, 'moderate_pct': 10.0, 'relevant_pct': 25.0, 'consistent_months': 6}
EPSILON = 1e-9
METRICS = {'records': 'registros', 'affected': 'afetações reportadas', 'p90_hours': 'P90 da duração (horas)'}


def previous_period(period):
    year, month = map(int, period.split('-'))
    return f'{year-1:04d}-12' if month == 1 else f'{year:04d}-{month-1:02d}'


def usable(m):
    if not m or (m.get('records') or 0) < PARAMETERS['minimum_records']:
        return False
    n = m['records']
    return (m.get('affected_valid', 0) == n
            and 100 * (m.get('dates_valid') or 0) / n >= PARAMETERS['minimum_valid_dates_pct']
            and (m.get('durations_valid', m.get('dates_valid')) or 0) >= PARAMETERS['minimum_durations']
            and m.get('affected') is not None and m.get('p90_hours') is not None)


def _change(current, previous, key):
    a, b = current.get(key), previous.get(key)
    if a is None or b is None:
        return {'current': a, 'previous': b, 'absolute': None, 'percent': None, 'eligible': False}
    return {'current': a, 'previous': b, 'absolute': a-b, 'percent': None if b == 0 else 100*(a/b-1), 'eligible': b != 0}


def _normal(m):
    return {**m, 'period': m.get('period', m.get('_eo_period'))} if m else None


def _quality(m):
    m = m or {}
    n = m.get('records') or 0
    valid = m.get('dates_valid') or 0
    return {'records': n, 'dates_numerator': valid, 'dates_denominator': n,
            'dates_valid_pct': 100*valid/n if n else None,
            'records_used': {'records': n, 'affected': m.get('affected_valid', 0),
                             'p90_hours': m.get('durations_valid', valid)},
            'missing_or_invalid': {'affected': n-(m.get('affected_valid') or 0),
                                   'dates_or_duration': n-valid},
            'missing_by_field': m.get('missing_by_field', {}),
            'invalid_by_field': m.get('invalid_by_field', {})}


def evaluate(current, previous, history, *, revised=False, integrity=True, schema=True):
    current, supplied_previous = _normal(current), _normal(previous)
    period = current.get('period') if current else None
    expected = previous_period(period) if period else None
    previous = supplied_previous if supplied_previous and supplied_previous.get('period') == expected else None
    by_period = {m['period']: m for m in map(_normal, history) if m and m.get('period') and period and m['period'] <= period}
    if current: by_period[period] = current
    if previous: by_period[expected] = previous
    sequence = []
    cursor = period
    while cursor in by_period and usable(by_period[cursor]):
        sequence.append(by_period[cursor])
        cursor = previous_period(cursor)
    quality = {'current': _quality(current), 'previous': _quality(previous)}
    changes = {k: _change(current, previous, k) for k in METRICS} if current and previous else {}
    comparable = bool(changes) and all(v['eligible'] for v in changes.values())
    essential_failure = not integrity or not schema or not usable(current) or (previous is not None and not usable(previous))
    reasons = []
    if essential_failure: reasons.append('Os requisitos mínimos de qualidade, integridade ou volume não foram atendidos nos meses presentes.')
    if revised: reasons.append('Aquisições diferentes alteraram registros analíticos deste recorte; os totais, sozinhos, não determinam a revisão.')
    if not previous: reasons.append('O mês civil imediatamente anterior está ausente; outro mês não o substitui.')
    elif not comparable: reasons.append('Há base zero ou valor ausente; a variação percentual não é calculável para todos os indicadores.')
    ups = [k for k,v in changes.items() if v['percent'] is not None and v['percent'] >= 10-EPSILON]
    downs = [k for k,v in changes.items() if v['percent'] is not None and v['percent'] <= -10+EPSILON]
    relevant = [k for k,v in changes.items() if v['percent'] is not None and v['percent'] >= 25-EPSILON]
    if essential_failure: label, rule = 'dados insuficientes', 'S01_INSUFFICIENT'
    elif revised: label, rule = 'possível alteração ou revisão da fonte', 'S02_SOURCE_REVISION'
    elif not comparable: label, rule = 'sem comparação', 'S03_NO_COMPARISON'
    elif relevant: label, rule = 'aumento relevante', 'S04_RELEVANT_INCREASE'
    elif ups: label, rule = 'deterioração moderada', 'S05_MODERATE_DETERIORATION'
    elif downs: label, rule = 'melhora', 'S06_IMPROVEMENT'
    else: label, rule = 'estabilidade', 'S07_STABILITY'
    for key in relevant or ups or downs:
        reasons.append(f"{METRICS[key]}: variação de {changes[key]['percent']:+.2f}%.")
    divergent = bool(ups and downs)
    if divergent: reasons.append('Indicadores divergentes: aumentos prevalecem na triagem, e as quedas permanecem visíveis.')
    six = sequence[:PARAMETERS['consistent_months']]
    consistent = len(six) == 6 and all(m['dates_valid'] == m['records'] for m in six)
    confidence = ('insuficiente' if essential_failure else 'limitada' if not comparable or revised
                  else 'consistente' if consistent else 'adequada')
    components = [
        {'name': 'Comparação mensal', 'value': 'mês anterior presente' if previous else 'mês anterior ausente', 'status': 'ok' if comparable else 'warning', 'expected_period': expected, 'present': previous is not None, 'percentage_comparable': comparable},
        {'name': 'Histórico', 'value': f'{len(by_period)} competências até a seleção; {len(sequence)} consecutivas utilizáveis terminando nela', 'status': 'ok' if len(sequence)>=6 else 'warning', 'available_periods': sorted(by_period), 'consecutive_usable': len(sequence), 'sequence': [m['period'] for m in sequence]},
        {'name': 'Datas válidas', 'value': f"{quality['current']['dates_numerator']}/{quality['current']['dates_denominator']} no mês atual", 'status': 'ok' if usable(current) and (previous is None or usable(previous)) else 'warning', **quality},
        {'name': 'Campos necessários', 'value': 'schema validado' if schema else 'campos necessários ausentes', 'status': 'ok' if schema else 'error', 'present': bool(schema), 'required': ['identificadores', 'competência', 'quantidade afetada', 'início', 'fim']},
        {'name': 'Registros por indicador', 'value': f"{quality['current']['records']} registros no mês atual", 'status': 'ok' if usable(current) else 'warning', 'current': quality['current']['records_used'], 'previous': quality['previous']['records_used']},
        {'name': 'Ausências e inválidos', 'value': 'Contagens por campo; valores ausentes não viram zero.', 'status': 'warning' if any(quality[x]['missing_or_invalid'][k] for x in quality for k in quality[x]['missing_or_invalid']) else 'ok', **quality},
        {'name': 'Origem e integridade', 'value': 'integridade não comprovada' if not integrity else 'revisão detectada no recorte' if revised else 'arquivo conciliado; revisão não detectada no recorte', 'status': 'error' if not integrity else 'warning' if revised else 'ok', 'integrity_verified': bool(integrity), 'revision_detected': bool(revised)},
    ]
    variation = '; '.join(f"{METRICS[k]}: {v['current']} versus {v['previous']}, diferença {v['absolute']}, " + (f"{v['percent']:+.2f}%" if v['percent'] is not None else 'percentual indisponível') for k,v in changes.items()) or 'Não há comparação mensal calculável.'
    sections = [
        ('motivo', 'Por que investigar', f"Situação: {label}. " + (' '.join(reasons) or 'Nenhum limite operacional foi cruzado; estabilidade não significa ausência de interrupções.'), ['assessment.situation', 'assessment.parameters']),
        ('variacao', 'Variação observada', variation, ['assessment.changes']),
        ('metricas', 'Métricas que contribuíram', ('Limite de aumento cruzado por: ' + ', '.join(METRICS[k] for k in ups)) if ups else 'Nenhum aumento calculável cruzou 10%; conferir a regra e a qualidade antes de interpretar.', ['assessment.changes', 'assessment.situation.rule_id']),
        ('dimensoes', 'Registros, afetações e duração', 'Aumentos: ' + (', '.join(METRICS[k] for k,v in changes.items() if v['absolute'] is not None and v['absolute']>0) or 'nenhum calculável') + '. Quedas: ' + (', '.join(METRICS[k] for k,v in changes.items() if v['absolute'] is not None and v['absolute']<0) or 'nenhuma calculável') + '. Registros não são eventos únicos; afetações não são consumidores únicos.', ['assessment.changes', 'formulas']),
        ('historico', 'Suficiência do histórico', f"{len(by_period)} competências disponíveis até {period}; {len(sequence)} consecutivas utilizáveis terminando na seleção. Mês anterior {'presente' if previous else 'ausente'}. Não inferir sazonalidade.", ['assessment.confidence.components']),
        ('qualidade', 'Qualidade e cobertura', f"Confiança documental {confidence}. Datas válidas no mês atual: {quality['current']['dates_numerator']}/{quality['current']['dates_denominator']}; quantidades ausentes ou inválidas: {quality['current']['missing_or_invalid']['affected']}. Conferir os sete componentes e a cobertura da fonte; confiança não é probabilidade nem qualidade do fornecimento.", ['assessment.confidence', 'source']),
        ('evidencias', 'Registros que sustentam a leitura', 'Conferir os registros-fonte do mês selecionado e do mês anterior, quando presente. A exportação identifica linhas, filtros, versões e hashes, incluindo o histórico e contextos habilitados.', ['selection', 'evidence_periods', 'records_preview', 'source', 'formulas']),
        ('limites', 'O que os dados não permitem concluir', 'Aumento de interrupções não prova causa. Município do equipamento não representa necessariamente consumidores afetados. Ausência de dados não equivale à ausência de interrupções. O produto apoia investigação e não substitui análise regulatória ou técnica. Deterioração refere-se aos indicadores observados; equivalência estatística entre conjuntos não foi estabelecida.', ['limitations', 'context']),
    ]
    narrative = [{'id': sid, 'title': title, 'text': text, 'references': refs} for sid,title,text,refs in sections]
    return {'rules_version': RULES_VERSION, 'parameters': dict(PARAMETERS), 'situation': {'label': label, 'rule_id': rule, 'reasons': reasons, 'divergent': divergent, 'increasing_metrics': ups, 'decreasing_metrics': downs}, 'confidence': {'level': confidence, 'components': components}, 'changes': changes, 'narrative': narrative}
