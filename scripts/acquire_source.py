"""Acquire only the public ANEEL resource; usable without installing the app."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import urllib.request

URL = 'https://dadosabertos.aneel.gov.br/dataset/ccb25653-f07b-4f28-84c2-62a89d1f5a56/resource/cf722d0b-aa04-4681-bcd9-8a737e857182/download/interrupcoes-energia-eletrica-2026.parquet'
out = Path('acquired')
out.mkdir(exist_ok=True)
metadata = {'source_url': URL, 'resource_id': 'cf722d0b-aa04-4681-bcd9-8a737e857182', 'acquired_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'year': 2026, 'acquisition_environment': 'GitHub Actions'}
try:
    headers={'User-Agent': 'EnergiaObservada/1.0 (public data research)', 'Accept-Encoding':'identity'}
    req = urllib.request.Request(URL, headers={**headers, 'Range':'bytes=0-0'})
    with urllib.request.urlopen(req, timeout=120) as response:
        content_range=response.headers.get('Content-Range','')
        total=int(content_range.rsplit('/',1)[-1]) if '/' in content_range else int(response.headers['Content-Length'])
        metadata['http_headers'] = {k: response.headers.get(k) for k in ['Content-Length', 'Last-Modified', 'ETag', 'Content-Range']}
    target=out/'official2026.parquet'
    with target.open('wb') as dest:
        for start in range(0,total,16*1024*1024):
            end=min(total-1,start+16*1024*1024-1)
            request=urllib.request.Request(URL, headers={**headers,'Range':f'bytes={start}-{end}'})
            with urllib.request.urlopen(request,timeout=180) as response:
                if response.status != 206: raise RuntimeError(f'Servidor ignorou Range em {start}: HTTP {response.status}')
                block=response.read()
                if len(block)!=end-start+1: raise RuntimeError(f'Faixa incompleta {start}-{end}: {len(block)} bytes')
                dest.write(block)
    size=target.stat().st_size
    if size!=total or target.read_bytes()[:4]!=b'PAR1' or target.open('rb').read() is None:
        raise RuntimeError('Arquivo não passou nas verificações físicas Parquet.')
    with target.open('rb') as stream:
        stream.seek(-4,2)
        if stream.read()!=b'PAR1': raise RuntimeError('Footer Parquet ausente; download incompleto.')
    metadata.update(sha256=hashlib.sha256(target.read_bytes()).hexdigest(), size_bytes=size, expected_size_bytes=total, status='acquired')
    print(json.dumps(metadata, ensure_ascii=False))
except Exception as exc:
    metadata.update(status='failed', error=str(exc))
    raise
finally:
    (out / 'acquisition.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
