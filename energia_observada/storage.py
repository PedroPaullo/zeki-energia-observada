"""Filesystem state and bounded DuckDB connections."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone
import duckdb

def root_dir(data_dir=None):
    return Path(data_dir or os.getenv('ENERGIA_DATA_DIR', 'data')).resolve()

def utc_now():
    return datetime.now(timezone.utc).isoformat()

def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    os.replace(temporary, path)

def read_json(path, default=None):
    path = Path(path)
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default

def literal(value):
    return "'" + str(value).replace("'", "''") + "'"

def identifier(value):
    return '"' + str(value).replace('"', '""') + '"'

def connect(path=':memory:', temp_dir=None):
    con = duckdb.connect(str(path))
    con.execute('SET threads=1')
    con.execute('SET memory_limit=' + literal(os.getenv('ENERGIA_MEMORY_LIMIT', '256MB')))
    if temp_dir:
        Path(temp_dir).mkdir(parents=True, exist_ok=True)
        con.execute('SET temp_directory=' + literal(Path(temp_dir).as_posix()))
    return con

def rows(con, sql, params=None):
    result = con.execute(sql, params or [])
    names = [c[0] for c in result.description]
    return [dict(zip(names, row)) for row in result.fetchall()]

def get_status(data_dir=None):
    root = root_dir(data_dir)
    return {name: read_json(root / (name + '.json')) for name in ('active', 'pending', 'last_attempt')}
