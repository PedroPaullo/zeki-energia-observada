# Contratos internos (v1)

Código usa dicionários JSON; textos da aplicação em português. Não utilizar números inventados na demonstração. Fixtures de teste são explicitamente sintéticas.

## Monthly
`period` YYYY-MM, `records` int (linhas após deduplicação exata, antes de excluir campos inválidos), `affected` number|null (soma das quantidades válidas, parcial se necessário), `affected_valid` int, `dates_valid` int, `p90_hours` number|null, `fingerprint` str. `records` é o denominador de qualidade. Datas válidas requerem início e fim parseáveis e fim >= início. Quantidades válidas requerem inteiro >=0.

## rules.evaluate
`evaluate(current: dict|None, previous: dict|None, history: list[dict], *, revised=False, integrity=True, schema=True) -> dict`.
Resultado: `situation` (dict: `label`, `rule_id`, `reasons` list[str], `divergent` bool), `confidence` (dict: `level`, `components` list[dict com name/value/status]), `changes` (dict por records/affected/p90_hours: current/previous/absolute/percent), `narrative` list[dict com text/references list[str]], `rules_version` str, `parameters` dict. Exportar também `usable(month)` e `previous_period(period)`.

## service (root implementa)
`status(data_dir=None) -> dict` com active, last_attempt e pending.
`choices(data_dir=None) -> dict` com distributors list[{cnpj,name}], periods list[str], conjuntos list[{cnpj,conjunto,name}], municipalities list[str], mode.
`queue(period, cnpj=None, municipio=None, data_dir=None) -> list[dict]` com cnpj/conjunto/name/current/previous/change/usable (fila por aumento absoluto de afetações; casos sem base continuam visíveis).
`build_dossier(cnpj, conjunto, period, municipio=None, context=True, data_dir=None) -> dict` com selection, current, previous, history, assessment (resultado evaluate), context, source (active manifest), formulas, limitations, records_preview (list[dict]), participation.
`export_dossier(dossier, data_dir=None, output_dir='exports') -> pathlib.Path`.

## CLI
`ingest --year 2026` descobre fonte oficial, baixa bruto, valida legibilidade/schema e registra pending; `transform` promove modelo válido; `update` executa ambos; `demo` instala recorte autêntico versionado; `profile`, `dossier --cnpj ... --conjunto ... --period ...`, `verify-export ZIP`.

UI e documentos devem refletir falhas da fonte sem anunciar dados atuais. Nenhuma atualização ou download automático ao renderizar a interface.
