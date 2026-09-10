"""Acquire only the public ANEEL resource; usable without installing the app."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import urllib.request
import time
import os

YEAR = int(os.getenv('ENERGIA_YEAR', '2026'))
catalog_url = 'https://dadosabertos.aneel.gov.br/api/3/action/package_show?id=interrupcoes-de-energia-eletrica-nas-redes-de-distribuicao'
with urllib.request.urlopen(catalog_url, timeout=60) as response:
    catalog = json.load(response)
resources = [r for r in catalog['result']['resources'] if str(YEAR) in r.get('name', '') and r.get('format', '').upper() == 'PARQUET']
if len(resources) != 1:
    raise RuntimeError(f'Esperado um recurso anual Parquet para {YEAR}; encontrados {len(resources)}')
resource = resources[0]
URL = resource['url']
if not URL.startswith('https://dadosabertos.aneel.gov.br/'):
    raise RuntimeError('Recurso fora do domínio oficial')
out = Path('acquired')
out.mkdir(exist_ok=True)
metadata = {'source_url': URL, 'resource_id': resource['id'], 'catalog_resource': resource, 'acquired_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'year': YEAR, 'acquisition_environment': 'GitHub Actions'}
try:
    headers={'User-Agent': 'EnergiaObservada/1.0 (public data research)', 'Accept-Encoding':'identity'}
    req = urllib.request.Request(URL, headers={**headers, 'Range':'bytes=0-0'})
    with urllib.request.urlopen(req, timeout=120) as response:
        content_range=response.headers.get('Content-Range','')
        total=int(content_range.rsplit('/',1)[-1]) if '/' in content_range else int(response.headers['Content-Length'])
        metadata['http_headers'] = {k: response.headers.get(k) for k in ['Content-Length', 'Last-Modified', 'ETag', 'Content-Range']}
    target=out/f'official{YEAR}.parquet'
    with target.open('wb') as dest:
        for start in range(0,total,16*1024*1024):
            end=min(total-1,start+16*1024*1024-1)
            expected=end-start+1
            chunk=out/f'range-{start:012d}.part'
            for attempt in range(1,4):
                chunk.unlink(missing_ok=True)
                try:
                    request=urllib.request.Request(URL, headers={**headers,'Range':f'bytes={start}-{end}'})
                    with urllib.request.urlopen(request,timeout=180) as response, chunk.open('wb') as piece:
                        if response.status != 206: raise RuntimeError(f'Servidor ignorou Range em {start}: HTTP {response.status}')
                        if response.headers.get('Content-Range') != f'bytes {start}-{end}/{total}':
                            raise RuntimeError('Content-Range recebido não corresponde à faixa solicitada')
                        if metadata['http_headers'].get('ETag') and response.headers.get('ETag') != metadata['http_headers']['ETag']:
                            raise RuntimeError('ETag mudou durante o download; aquisição inconsistente')
                        while data := response.read(1024*1024): piece.write(data)
                    if chunk.stat().st_size != expected: raise RuntimeError(f'Faixa incompleta {start}-{end}: {chunk.stat().st_size} bytes')
                    with chunk.open('rb') as piece: dest.write(piece.read())
                    chunk.unlink()
                    print(f'faixa concluída {end+1}/{total}', flush=True)
                    break
                except Exception:
                    chunk.unlink(missing_ok=True)
                    if attempt == 3: raise
                    print(f'retentando faixa {start}-{end}: tentativa {attempt+1}/3', flush=True)
                    time.sleep(attempt * 2)
    size=target.stat().st_size
    with target.open('rb') as stream:
        starts_parquet = stream.read(4) == b'PAR1'
    if size != total or not starts_parquet:
        raise RuntimeError('Arquivo não passou nas verificações físicas Parquet.')
    with target.open('rb') as stream:
        stream.seek(-4,2)
        if stream.read()!=b'PAR1': raise RuntimeError('Footer Parquet ausente; download incompleto.')
    digest = hashlib.sha256()
    with target.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    metadata.update(sha256=digest.hexdigest(), size_bytes=size, expected_size_bytes=total, status='acquired')
    print(json.dumps(metadata, ensure_ascii=False))
except Exception as exc:
    metadata.update(status='failed', error=str(exc))
    raise
finally:
    (out / 'acquisition.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
