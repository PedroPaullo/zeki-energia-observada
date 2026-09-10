from energia_observada.rules import evaluate, usable
def month(p, records=10, affected=100, dates=10, p90=2): return {'period':p,'records':records,'affected':affected,'affected_valid':records,'dates_valid':dates,'p90_hours':p90}
def test_boundaries_and_usable():
 assert usable(month('2026-01'))
 assert not usable(month('2026-01', records=9, dates=9))
 assert evaluate(month('2026-02',affected=125),month('2026-01'),[] )['situation']['label']=='aumento relevante'
 assert evaluate(month('2026-02',affected=110),month('2026-01'),[] )['situation']['label']=='deterioração moderada'
 assert evaluate(month('2026-02',affected=90),month('2026-01'),[] )['situation']['label']=='melhora'
def test_missing_zero_and_divergence():
 assert evaluate(month('2026-02'),None,[])['situation']['label']=='sem comparação'
 assert evaluate(month('2026-02',affected=100),month('2026-01',affected=0),[])['situation']['label']=='sem comparação'
 r=evaluate(month('2026-02',affected=75,p90=3),month('2026-01',affected=100,p90=2),[])
 assert r['situation']['label']=='aumento relevante' and r['situation']['divergent']
def test_revision_and_components():
 r=evaluate(month('2026-02'),month('2026-01'),[],revised=True)
 assert r['situation']['label']=='possível alteração ou revisão da fonte'
 assert len(r['confidence']['components'])==7
