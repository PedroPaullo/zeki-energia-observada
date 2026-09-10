"""Exercise the actual screen on authentic ANEEL data, including handled errors."""
import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from energia_observada import service
from energia_observada.pipeline import ingest, transform


def test_authentic_demo_filters_dossier_and_export(tmp_path, monkeypatch):
    project = Path(__file__).resolve().parents[1]
    metadata = json.loads((project / 'demo' / 'manifest.json').read_text(encoding='utf-8'))
    data = tmp_path / 'data'
    ingest(2026, file=project / 'demo' / 'aneel_2026_enel_ce_jurema_13317.parquet',
           metadata=metadata, mode='sample', data_dir=data)
    transform(data)
    monkeypatch.setenv('ENERGIA_DATA_DIR', str(data))
    original_export = service.export_dossier
    monkeypatch.setattr(service, 'export_dossier',
                        lambda dossier: original_export(dossier, data_dir=data, output_dir=tmp_path / 'exports'))
    app = AppTest.from_file(str(project / 'app.py')).run(timeout=60)
    assert not app.exception
    assert not app.error  # app catches errors itself; exception alone misses broken screens
    assert [tab.label for tab in app.tabs] == ['Por que investigar', 'Histórico e contexto', 'Sinais reportados',
                                             'Confiança', 'Registros-fonte', 'Exportar e reproduzir']
    assert len(app.metric) == 3
    assert app.metric[0].value == '729'
    assert app.metric[1].value == '279.285'
    selectors = {selector.label: selector for selector in app.selectbox}
    assert selectors['Competência'].value == '2026-07'
    assert 'JUREMA' in selectors['Selecionar conjunto da fila'].options[0]
    assert any('nacional bloqueada' in warning.value for warning in app.warning)
    assert any('Evidência consistente' in block.value for block in app.markdown)
    button = next(button for button in app.button if button.label == 'Gerar pacote de evidências')
    button.click().run(timeout=60)
    assert not app.exception and not app.error
    assert len(app.get('download_button')) == 1
    assert list((tmp_path / 'exports').glob('*.zip'))
    next(s for s in app.selectbox if s.label == 'Competência').set_value('2026-06').run(timeout=60)
    assert not app.exception and not app.error
    assert len(app.get('download_button')) == 0
    assert app.metric[0].value != '729'  # competência mudou e o Dossiê foi recalculado
