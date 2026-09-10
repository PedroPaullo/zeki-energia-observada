import pytest
from energia_observada.rules import evaluate, usable, previous_period


def month(period, **kw):
    return dict(period=period, records=100, affected=100, affected_valid=100,
                dates_valid=100, p90_hours=10) | kw


@pytest.mark.parametrize('value,label', [(89.99,'melhora'),(90,'melhora'),(90.01,'estabilidade'),(109.99,'estabilidade'),(110,'deterioração moderada'),(124.99,'deterioração moderada'),(125,'aumento relevante')])
def test_exact_operational_thresholds(value,label):
    result=evaluate(month('2026-02',affected=value),month('2026-01'),[])
    assert result['situation']['label']==label


@pytest.mark.parametrize('records,dates,durations,expected',[(9,9,9,False),(10,10,9,False),(10,10,10,True),(100,94,94,False),(100,95,95,True)])
def test_quality_denominators(records,dates,durations,expected):
    assert usable(month('2026-01',records=records,affected_valid=records,dates_valid=dates,durations_valid=durations)) is expected


def test_zero_is_observed_but_not_percentage_comparable():
    result=evaluate(month('2026-02'),month('2026-01',affected=0),[])
    assert result['changes']['affected']['absolute']==100
    assert result['changes']['affected']['percent'] is None
    assert result['confidence']['level']=='limitada'


def test_prior_unusable_and_revision_precedence_keep_all_reasons():
    result=evaluate(month('2026-02'),month('2026-01',affected_valid=99),[],revised=True)
    assert result['situation']['label']=='dados insuficientes'
    assert result['confidence']['level']=='insuficiente'
    assert any('Aquisições' in r for r in result['situation']['reasons'])
    result=evaluate(month('2026-02'),month('2026-01'),[],revised=True)
    assert result['confidence']['level']=='limitada'
    assert result['confidence']['components'][-1]['status']=='warning'


def test_wrong_prior_not_substituted_and_future_history_ignored():
    result=evaluate(month('2026-06'),month('2026-04'),[month(f'2026-{n:02}') for n in range(6,13)])
    assert result['confidence']['level']=='limitada'
    assert result['changes']=={}
    assert result['confidence']['components'][1]['available_periods']==['2026-06']


def test_six_consecutive_end_at_selection_and_order_independent():
    hist=[month(f'2026-{n:02}') for n in range(1,8)]
    assert evaluate(hist[4],hist[3],hist)['confidence']['level']=='adequada'
    assert evaluate(hist[5],hist[4],hist[::-1])['confidence']['level']=='consistente'
    hist[2]['dates_valid']=95
    assert evaluate(hist[5],hist[4],hist)['confidence']['level']=='adequada'
    hist.pop(2)
    assert evaluate(hist[4],hist[3],hist)['confidence']['level']=='adequada'


def test_components_narrative_and_divergent_metrics():
    result=evaluate(month('2026-02',affected=75,p90_hours=15),month('2026-01'),[])
    assert result['situation']['divergent']
    assert result['situation']['label']=='aumento relevante'
    assert len(result['narrative'])==8
    assert all(section['references'] for section in result['narrative'])
    assert len(result['confidence']['components'])==7
    dates=result['confidence']['components'][2]['current']
    assert (dates['dates_numerator'],dates['dates_denominator'],dates['dates_valid_pct'])==(100,100,100)
    assert previous_period('2026-01')=='2025-12'


def test_missing_metric_and_integrity_fail_closed():
    assert not usable(month('2026-02',p90_hours=None))
    for kw in [{'schema':False},{'integrity':False}]:
        result=evaluate(month('2026-02'),month('2026-01'),[],**kw)
        assert result['confidence']['level']=='insuficiente'
        assert result['situation']['label']=='dados insuficientes'
