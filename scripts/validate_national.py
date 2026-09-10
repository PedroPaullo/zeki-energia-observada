"""Audit an already processed official snapshot; no download or reprocessing.

Run from the project root with its virtualenv. Runtime absolute paths stay ignored;
the public JSON report contains only provenance, checks and analytical results.
"""
from pathlib import Path
import json
import math
from energia_observada.storage import read_json, write_json, sha256, connect, rows, utc_now
from energia_observada.service import build_dossier, export_dossier, verify_export


def main():
    project = Path(__file__).resolve().parent.parent
    existing = project / 'data'
    manifest = existing / 'models' / '53064794800a0dcf-t1' / 'manifest.json'
    active = read_json(manifest)
    if not active:
        raise SystemExit('Archived national snapshot missing: acquire and transform official data first.')
    runtime = project / 'data-national'
    for key in ('model_path', 'monthly_path', 'raw_path', 'parse_path'):
        active[key] = str((existing / active[key]).resolve())
    active['status'] = 'published'
    raw_path = Path(active['raw_path'])
    with raw_path.open('rb') as handle:
        header = handle.read(4)
        handle.seek(-4, 2)
        footer = handle.read(4)
    checks = {'source_header_PAR1': header == b'PAR1', 'source_footer_PAR1': footer == b'PAR1',
              'source_size': raw_path.stat().st_size == active['size_bytes'],
              'source_sha256': sha256(raw_path) == active['sha256'],
              'model_sha256': sha256(active['model_path']) == active['model_sha256']}
    assert all(checks.values()), checks
    write_json(runtime / 'active.json', active)
    dossier = build_dossier('07047251000170', '13317', '2026-07', data_dir=runtime)
    # Independent query bypasses monthly materialization and the shared monthly_sql.
    with connect(temp_dir=runtime / 'tmp') as con:
        independent = rows(con, '''SELECT _eo_period AS period, count(*) AS records,
            sum(try_cast(QtdConsumidoresAfetados AS DOUBLE)) AS affected,
            quantile_cont(epoch(try_cast(DatFimInterrupcao AS TIMESTAMP)-try_cast(DatInicioInterrupcao AS TIMESTAMP))/3600,0.9) AS p90_hours
            FROM read_parquet(?) WHERE _eo_cnpj=? AND _eo_conjunto=?
            AND _eo_period IN ('2026-06','2026-07') AND _eo_key_valid AND NOT _eo_duplicate
            GROUP BY 1 ORDER BY 1''', [active['model_path'], '07047251000170', '13317'])
    for record, calculated in zip(independent, (dossier['previous'], dossier['current'])):
        for key in ('records', 'affected', 'p90_hours'):
            checks[record['period'] + '_' + key] = math.isclose(record[key], calculated[key], rel_tol=1e-10)
    checks['national_context_available'] = dossier['context']['national']['status'] == 'disponível'
    checks['distributor_context_available'] = dossier['context']['distributor']['status'] == 'disponível'
    assert all(checks.values()), checks
    # Full national context covers many source records; validate the selected real
    # history export here and explicitly report its narrower scope.
    compact = build_dossier('07047251000170', '13317', '2026-07', context=False, data_dir=runtime)
    bundle = export_dossier(compact, data_dir=runtime, output_dir=project / 'exports' / 'national-validation')
    reproduction = verify_export(bundle)
    context = dossier['context'].copy()
    context['distributor'] = {key: value for key, value in context['distributor'].items() if key != 'distribution'}
    report = {'validated_at': utc_now(), 'source_url': active['source_url'], 'source_acquired_at': active['acquired_at'],
              'source_sha256': active['sha256'], 'source_size_bytes': active['size_bytes'],
              'version': active['version'], 'profile': active['profile'], 'checks': checks,
              'independent_current_previous': independent, 'situation': dossier['assessment']['situation'],
              'confidence': dossier['assessment']['confidence'], 'context': context,
              'export_verification': reproduction,
              'export_scope': 'Selected JUREMA historical records; national context calculated and checked separately, not included in this compact ZIP.'}
    write_json(project / 'docs' / 'VALIDACAO_NACIONAL.json', report)
    print(json.dumps({'checks': checks, 'export': reproduction, 'report': 'docs/VALIDACAO_NACIONAL.json'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
