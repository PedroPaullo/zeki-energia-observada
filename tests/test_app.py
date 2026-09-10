from streamlit.testing.v1 import AppTest

def test_empty_state_is_honest(monkeypatch, tmp_path):
    monkeypatch.setenv('ENERGIA_DATA_DIR', str(tmp_path/'empty'))
    app = AppTest.from_file('app.py').run(timeout=15)
    assert any('Nenhuma versão validada' in w.value for w in app.warning)
