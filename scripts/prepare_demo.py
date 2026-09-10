"""Extract a deterministic, authentic demonstration from an acquired official file."""
import argparse
from pathlib import Path

from energia_observada.storage import connect, literal, read_json, sha256, write_json

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--data-dir', type=Path, default=Path('data'))
    args = parser.parse_args()
    source = read_json(args.manifest)
    raw = args.data_dir / source['raw_path']
    if sha256(raw) != source['sha256']:
        raise ValueError('Arquivo original difere do hash adquirido.')
    output = Path('demo/aneel_2026_enel_ce_jurema_13317.parquet')
    group_codes = [13317, 13263, 13255, 13249]
    with connect() as con:
        query = ('SELECT * FROM read_parquet(' + literal(raw.resolve().as_posix())
                 + ') WHERE NumCNPJDistribuidora=7047251000170 AND CodConjUnidadeConsumidora IN ('
                 + ','.join(map(str,group_codes)) + ') ORDER BY CodConjUnidadeConsumidora, AnoCompetencia, MesCompetencia, CodInterrupcao, DatInicioInterrupcao')
        con.execute('COPY ('+query+') TO '+literal(output.resolve().as_posix())+' (FORMAT PARQUET, COMPRESSION ZSTD)')
        count=con.execute('SELECT count(*) FROM read_parquet(?)',[str(output)]).fetchone()[0]
        groups=con.execute('SELECT DISTINCT CodConjUnidadeConsumidora,DscConjuntoUnidadeConsumidora FROM read_parquet(?) ORDER BY 1',[str(output)]).fetchall()
    write_json('demo/manifest.json', {
        'mode':'sample','source_url':source['source_url'],'resource_id':source['resource_id'],
        'source_sha256':source['sha256'],'source_acquired_at':source['acquired_at'],
        'sample_sha256':sha256(output),'extracted_rows':count,
        'periods':[f'2026-{m:02d}' for m in range(1,8)],
        'selection':{'cnpj':'07047251000170','conjunto':'13317','name':'JUREMA'},
        'groups':[{'code':str(code),'name':name} for code,name in groups],
        'selection_policy':'JUREMA + três conjuntos com maior quantidade de registros e sete competências na ENEL CE. Recorte deliberado para demonstração; não é amostragem estatística.',
        'extraction_query':query.replace(literal(raw.resolve().as_posix()),"'SOURCE_PARQUET'"),
        'license_notice':'Dados ANEEL, atribuição e licença do catálogo em demo/README.md.'})
    print(f'Amostra: {count} registros, {len(groups)} conjuntos; SHA-256 {sha256(output)}')

if __name__=='__main__': main()
