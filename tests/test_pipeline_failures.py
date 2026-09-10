"""Failure paths must never replace a validated snapshot."""
import json
import pytest
from energia_observada import pipeline

HEADER = ';'.join(pipeline.REQUIRED) + '\n'

def source(tmp_path, name='source.csv', affected=10):
    path = tmp_path / name
    path.write_text(HEADER + f'12345678000199;C1;2026;1;2026-01-01 00:00:00;2026-01-01 01:00:00;{affected};I1;1234567\n', encoding='utf-8')
    return path

def published(tmp_path):
    root = tmp_path / 'data'
    pipeline.ingest(file=source(tmp_path), data_dir=root)
    pipeline.transform(root)
    return root, (root / 'active.json').read_bytes()

@pytest.mark.parametrize('content', [b'PAR1', b'PAR1wrongfooter', b'PAR1' + (1000).to_bytes(4, 'little') + b'PAR1'])
def test_truncated_parquet_preserves_active(tmp_path, content):
    root, before = published(tmp_path)
    bad = tmp_path / 'bad.parquet'; bad.write_bytes(content)
    with pytest.raises(pipeline.SourceError, match='Parquet'):
        pipeline.ingest(file=bad, data_dir=root)
    assert (root / 'active.json').read_bytes() == before
    assert json.loads((root / 'last_attempt.json').read_text())['status'] == 'failed'

def test_unavailable_source_preserves_active(tmp_path, monkeypatch):
    root, before = published(tmp_path)
    def unavailable(*args): raise ConnectionError('offline')
    monkeypatch.setattr(pipeline, 'discover', unavailable)
    with pytest.raises(pipeline.SourceError, match='offline'): pipeline.update(data_dir=root)
    assert (root / 'active.json').read_bytes() == before

def test_transform_failure_preserves_active_and_history(tmp_path):
    root, before = published(tmp_path)
    meta = pipeline.ingest(file=source(tmp_path, 'changed.csv', 20), data_dir=root)
    (root / meta['parse_path']).write_bytes(b'corrupted')
    with pytest.raises(pipeline.QualityError, match='Bruto alterado'): pipeline.transform(root)
    assert (root / 'active.json').read_bytes() == before
    assert not (root / 'models' / meta['version']).exists()

def test_unchanged_acquisition_cancels_stale_pending(tmp_path):
    root, before = published(tmp_path)
    pipeline.ingest(file=source(tmp_path, 'changed.csv', 20), data_dir=root)
    pipeline.ingest(file=tmp_path / 'source.csv', data_dir=root)
    pipeline.transform(root)
    assert (root / 'active.json').read_bytes() == before
    assert not (root / 'pending.json').exists()

def test_mode_separates_snapshot_identity(tmp_path):
    root, before = published(tmp_path)
    old = json.loads(before)
    sample = pipeline.ingest(file=tmp_path / 'source.csv', mode='sample', data_dir=root)
    current = pipeline.transform(root)
    assert current['version'] != old['version']
    assert current['previous_version'] == old['version']
    assert (root / 'models' / old['version'] / 'manifest.json').exists()

def test_schema_failure_preserves_active(tmp_path):
    root, before = published(tmp_path)
    path = tmp_path / 'schema.csv'; path.write_text('unexpected\nvalue\n')
    with pytest.raises(pipeline.SourceError, match='Schema divergente'): pipeline.ingest(file=path, data_dir=root)
    assert (root / 'active.json').read_bytes() == before
