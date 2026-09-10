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
    req = urllib.request.Request(URL, headers={'User-Agent': 'EnergiaObservada/1.0 (public data research)'})
    digest = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(req, timeout=120) as response, (out / 'official2026.parquet').open('wb') as dest:
        metadata['http_headers'] = {k: response.headers.get(k) for k in ['Content-Length', 'Last-Modified', 'ETag']}
        while block := response.read(1024 * 1024):
            dest.write(block)
            digest.update(block)
            size += len(block)
    metadata.update(sha256=digest.hexdigest(), size_bytes=size, status='acquired')
    print(json.dumps(metadata, ensure_ascii=False))
except Exception as exc:
    metadata.update(status='failed', error=str(exc))
    raise
finally:
    (out / 'acquisition.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
