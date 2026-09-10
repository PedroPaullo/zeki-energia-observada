"""Immutable acquisitions, validation and atomic snapshot publication."""
from __future__ import annotations
import json
import os
import shutil
import zipfile
from pathlib import Path
from urllib.parse import urlparse
import requests
from .storage import root_dir, utc_now, sha256, write_json, read_json, literal, identifier, connect, rows

CATALOG = 'https://dadosabertos.aneel.gov.br/api/3/action/package_show'
DATASET = 'interrupcoes-de-energia-eletrica-nas-redes-de-distribuicao'
REQUIRED = ['NumCNPJDistribuidora', 'CodConjUnidadeConsumidora', 'AnoCompetencia', 'MesCompetencia', 'DatInicioInterrupcao', 'DatFimInterrupcao', 'QtdConsumidoresAfetados', 'CodInterrupcao', 'CodMunicipioIBGE']
TRANSFORM_VERSION = '1.0.0'

class SourceError(RuntimeError):
    pass

class QualityError(RuntimeError):
    pass

def discover(year=2026):
    response = requests.get(CATALOG, params={'id': DATASET}, timeout=(10, 30))
    response.raise_for_status()
    payload = response.json()
    if not payload.get('success'):
        raise SourceError('Catálogo CKAN não retornou success=true.')
    candidates = [r for r in payload['result']['resources'] if str(year) in r.get('name', '') and r.get('format', '').upper() == 'PARQUET']
    if len(candidates) != 1:
        raise SourceError(f'Esperado um recurso Parquet oficial para {year}; encontrados {len(candidates)}.')
    resource = candidates[0]
    if urlparse(resource['url']).hostname != 'dadosabertos.aneel.gov.br':
        raise SourceError('URL fora do domínio oficial configurado.')
    return {'source_url': resource['url'], 'resource_id': resource['id'], 'catalog_modified': resource.get('last_modified'), 'year': year, 'catalog_resource': resource}

def _input_relation(path):
    if path.suffix.lower() == '.parquet':
        return f'read_parquet({literal(path.as_posix())})'
    return f"read_csv({literal(path.as_posix())}, delim=';', header=true, all_varchar=true, nullstr='', strict_mode=true)"

def _validate_schema(path):
    with connect() as con:
        description = rows(con, 'DESCRIBE SELECT * FROM ' + _input_relation(path))
        columns = [d['column_name'] for d in description]
        normalized = [x.strip().lstrip('\ufeff') for x in columns]
        if len(set(normalized)) != len(normalized):
            raise QualityError('Colunas colidem após normalização do cabeçalho.')
        missing = sorted(set(REQUIRED) - set(normalized))
        if missing:
            raise QualityError('Schema divergente: campos obrigatórios ausentes: ' + ', '.join(missing))
        count = con.execute('SELECT count(*) FROM ' + _input_relation(path)).fetchone()[0]
        if not count:
            raise QualityError('Arquivo sem registros.')
    return {'columns': description, 'normalized_columns': normalized, 'row_count': count, 'missing_required': []}

def ingest(year=2026, *, file=None, metadata=None, mode='national', data_dir=None):
    root = root_dir(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    attempt = {'started_at': utc_now(), 'operation': 'ingest', 'year': year}
    staging = root / 'staging'
    staging.mkdir(exist_ok=True)
    try:
        meta = dict(metadata or {})
        if file is None:
            meta.update(discover(year))
            target = staging / 'download.parquet.part'
            with requests.get(meta['source_url'], stream=True, timeout=(10, 120)) as response:
                response.raise_for_status()
                expected = response.headers.get('Content-Length')
                if expected and shutil.disk_usage(root).free < int(expected) * 4 + 256 * 1024**2:
                    raise SourceError('Espaço insuficiente para bruto, modelo e temporários.')
                with target.open('wb') as dest:
                    for block in response.iter_content(1024 * 1024):
                        if block:
                            dest.write(block)
                if expected and target.stat().st_size != int(expected):
                    raise SourceError('Download incompleto: tamanho difere do Content-Length.')
            path = staging / 'download.parquet'
            os.replace(target, path)
            meta['acquired_at'] = utc_now()
        else:
            path = Path(file).resolve()
            meta.setdefault('acquired_at', utc_now())
            meta.setdefault('source_url', 'local://explicit-import')
        checksum = sha256(path)
        if meta.get('sha256') and meta['sha256'] != checksum:
            raise QualityError('SHA-256 do arquivo difere do manifesto de aquisição.')
        raw_dir = root / 'raw' / checksum
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_path = raw_dir / ('source' + path.suffix.lower())
        if not raw_path.exists():
            shutil.copyfile(path, raw_path)
        if sha256(raw_path) != checksum:
            raise QualityError('Falha de integridade na cópia do bruto.')
        parse_path = raw_path
        if path.suffix.lower() == '.zip':
            with zipfile.ZipFile(raw_path) as archive:
                csv_files = [n for n in archive.namelist() if n.lower().endswith('.csv')]
                if len(csv_files) != 1:
                    raise QualityError('ZIP deve conter exatamente um CSV.')
                parse_path = raw_dir / 'extracted.csv'
                with archive.open(csv_files[0]) as src, parse_path.open('wb') as dest:
                    shutil.copyfileobj(src, dest)
        profile = _validate_schema(parse_path)
        meta.update(sha256=checksum, size_bytes=path.stat().st_size, year=year, mode=mode,
                    raw_path=str(raw_path.relative_to(root)), parse_path=str(parse_path.relative_to(root)),
                    parse_sha256=sha256(parse_path), version=checksum[:16] + '-t1', transform_version=TRANSFORM_VERSION,
                    source_profile=profile, integrity_verified=True)
        write_json(raw_dir / 'manifest.json', meta)
        active = read_json(root / 'active.json')
        if active and active['version'] == meta['version'] and active['mode'] == mode:
            attempt.update(status='unchanged', version=meta['version'])
            return active
        write_json(root / 'pending.json', meta)
        attempt.update(status='acquired', version=meta['version'])
        return meta
    except Exception as exc:
        attempt.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        raise SourceError(attempt['error']) from exc
    finally:
        attempt['finished_at'] = utc_now()
        write_json(root / 'last_attempt.json', attempt)

def monthly_sql(where='_eo_key_valid AND NOT _eo_duplicate', group='_eo_cnpj, _eo_conjunto, _eo_period', relation='records'):
    return f'''SELECT {group}, count(*)::BIGINT AS records,
      sum(_eo_affected) AS affected, count(_eo_affected)::BIGINT AS affected_valid,
      count(_eo_duration)::BIGINT AS dates_valid,
      quantile_cont(_eo_duration, 0.9) AS p90_hours
      FROM {relation} WHERE {where} GROUP BY {group}'''

def transform(data_dir=None):
    root = root_dir(data_dir)
    meta = read_json(root / 'pending.json')
    if not meta:
        active = read_json(root / 'active.json')
        if active:
            return active
        raise QualityError('Nenhuma aquisição pendente. Execute ingest ou demo.')
    attempt = {'started_at': utc_now(), 'operation': 'transform', 'version': meta['version']}
    destination = root / 'models' / meta['version']
    destination.mkdir(parents=True, exist_ok=True)
    work = destination / 'work.duckdb'
    try:
        path = root / meta['parse_path']
        if sha256(path) != meta['parse_sha256']:
            raise QualityError('Bruto alterado após aquisição.')
        columns = meta['source_profile']['columns']
        normalized = meta['source_profile']['normalized_columns']
        raw_select = ', '.join(f'trim(CAST({identifier(c["column_name"])} AS VARCHAR)) AS {identifier(n)}' for c, n in zip(columns, normalized))
        business = [n for n in normalized if n != 'DatGeracaoConjuntoDados']
        pack = ', '.join(f'{identifier(n)} := {identifier(n)}' for n in business)
        def date_expr(name):
            c = identifier(name)
            return f"coalesce(try_cast({c} AS TIMESTAMP), try_strptime({c}, '%d/%m/%Y %H:%M:%S'), try_strptime({c}, '%d/%m/%Y %H:%M'))"
        cn = "regexp_replace(NumCNPJDistribuidora, '[^0-9]', '', 'g')"
        start, end = date_expr('DatInicioInterrupcao'), date_expr('DatFimInterrupcao')
        quantity = 'try_cast(QtdConsumidoresAfetados AS DOUBLE)'
        with connect(work, destination / 'temp') as con:
            con.execute('CREATE OR REPLACE TABLE original AS SELECT row_number() OVER () AS _eo_row, ' + raw_select + ' FROM ' + _input_relation(path))
            con.execute(f'''CREATE OR REPLACE TABLE normalized AS SELECT *,
              sha256(to_json(struct_pack({pack}))) AS _eo_hash,
              CASE WHEN length({cn}) BETWEEN 1 AND 14 THEN lpad({cn},14,'0') END AS _eo_cnpj,
              nullif(CodConjUnidadeConsumidora,'') AS _eo_conjunto,
              nullif(CodMunicipioIBGE,'') AS _eo_municipio,
              CASE WHEN try_cast(AnoCompetencia AS INTEGER) = {int(meta['year'])}
                AND try_cast(MesCompetencia AS INTEGER) BETWEEN 1 AND 12
                THEN printf('%04d-%02d',try_cast(AnoCompetencia AS INTEGER),try_cast(MesCompetencia AS INTEGER)) END AS _eo_period,
              CASE WHEN {quantity} >= 0 AND isfinite({quantity}) AND floor({quantity})={quantity} THEN {quantity} END AS _eo_affected,
              CASE WHEN {start} IS NOT NULL AND {end} >= {start}
                THEN epoch({end}-{start})/3600.0 END AS _eo_duration
              FROM original''')
            con.execute('''CREATE OR REPLACE TABLE records AS SELECT *,
              _eo_cnpj IS NOT NULL AND _eo_conjunto IS NOT NULL AND _eo_period IS NOT NULL AS _eo_key_valid,
              row_number() OVER (PARTITION BY _eo_hash ORDER BY _eo_row)>1 AS _eo_duplicate
              FROM normalized''')
            profile = rows(con, '''SELECT count(*) AS raw_rows,
              count(*) FILTER(WHERE _eo_duplicate) AS duplicate_rows,
              count(*) FILTER(WHERE NOT _eo_duplicate AND NOT _eo_key_valid) AS rejected_key_rows,
              count(*) FILTER(WHERE NOT _eo_duplicate AND _eo_key_valid) AS accepted_rows,
              count(*) FILTER(WHERE _eo_key_valid AND NOT _eo_duplicate AND _eo_affected IS NULL) AS invalid_quantities,
              count(*) FILTER(WHERE _eo_key_valid AND NOT _eo_duplicate AND _eo_duration IS NULL) AS invalid_dates
              FROM records''')[0]
            if profile['raw_rows'] != sum(profile[k] for k in ['duplicate_rows','rejected_key_rows','accepted_rows']):
                raise QualityError('Reconciliação de linhas falhou.')
            if profile['accepted_rows'] == 0:
                raise QualityError('Nenhum registro com identidade e competência válidas.')
            if profile['rejected_key_rows']:
                raise QualityError(f"{profile['rejected_key_rows']} registros sem identidade/competência válida; publicação bloqueada para não ocultar cobertura.")
            profile['periods'] = [r[0] for r in con.execute('SELECT DISTINCT _eo_period FROM records WHERE _eo_key_valid ORDER BY 1').fetchall()]
            profile['distributors'] = con.execute('SELECT count(DISTINCT _eo_cnpj) FROM records WHERE _eo_key_valid').fetchone()[0]
            profile['groups'] = con.execute('SELECT count(*) FROM (SELECT DISTINCT _eo_cnpj,_eo_conjunto FROM records WHERE _eo_key_valid)').fetchone()[0]
            profile['interruption_code_multiplicity'] = con.execute('''SELECT count(*) FROM (SELECT _eo_cnpj,CodInterrupcao,count(*) n FROM records WHERE _eo_key_valid AND NOT _eo_duplicate GROUP BY 1,2 HAVING count(*)>1)''').fetchone()[0]
            con.execute('COPY records TO ' + literal((destination / 'records.parquet').as_posix()) + " (FORMAT PARQUET, COMPRESSION ZSTD)")
            con.execute('COPY (' + monthly_sql() + ') TO ' + literal((destination / 'monthly.parquet').as_posix()) + ' (FORMAT PARQUET)')
        active = read_json(root / 'active.json')
        meta.update(profile=profile, model_path=str((destination / 'records.parquet').relative_to(root)),
                    monthly_path=str((destination / 'monthly.parquet').relative_to(root)),
                    model_sha256=sha256(destination / 'records.parquet'), transformed_at=utc_now(),
                    previous_version=active['version'] if active and active['version'] != meta['version'] else None)
        write_json(destination / 'manifest.json', meta)
        write_json(root / 'active.json', meta)
        (root / 'pending.json').unlink(missing_ok=True)
        attempt.update(status='published', profile=profile)
        return meta
    except Exception as exc:
        attempt.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        attempt['finished_at'] = utc_now()
        write_json(root / 'last_attempt.json', attempt)
        if work.exists():
            work.unlink()

def update(year=2026, data_dir=None):
    ingest(year, data_dir=data_dir)
    return transform(data_dir)
