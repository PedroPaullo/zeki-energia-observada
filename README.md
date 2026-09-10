# Energia Observada

Produto local para analistas investigarem aumentos registrados em interrupções de distribuição. A fila leva ao Dossiê de Investigação: métricas, regras transparentes, confiança documental, registros-fonte e pacote reproduzível.

## Fonte, público e limites

Usa exclusivamente [Interrupções de Energia Elétrica nas Redes de Distribuição — ANEEL](https://dadosabertos.aneel.gov.br/dataset/interrupcoes-de-energia-eletrica-nas-redes-de-distribuicao), atualizada mensalmente. A fonte exclui permissionárias/cooperativas. Município identifica o equipamento; não representa necessariamente os consumidores afetados.

O produto apoia investigação: não prova causas, não calcula DEC/FEC, não substitui análise técnica ou regulatória e não usa IA generativa.

## Arquitetura

`fonte oficial → bruto imutável + hash → validação → Parquet normalizado → DuckDB → regras → Dossiê/ZIP/Streamlit`.

Cada aquisição registra URL, recurso, data UTC, tamanho, SHA-256, schema, contagens e falhas. A promoção só ocorre após reconciliação. Falha mantém a última versão válida.

## Instalação e execução

Requer Python 3.12 e Git. No Windows:

```powershell
git clone https://github.com/PedroPaullo/zeki-energia-observada.git
cd zeki-energia-observada
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
python -m energia_observada ingest --year 2026
python -m energia_observada transform
python -m streamlit run app.py
python -m pytest
```

No Linux/macOS, substituir os dois comandos de ambiente por `python3.12 -m venv .venv` e `source .venv/bin/activate`.

`update` executa ingestão e transformação. O pipeline usa uma thread e memória limitada a 256 MB; ajuste `ENERGIA_MEMORY_LIMIT` somente após medir o ambiente. Acesso local indisponível à fonte aparece como falha documentada, nunca como dados vazios.

## Indicadores e regras

Registros = linhas aceitas; afetações = soma de `QtdConsumidoresAfetados` válidos, sem afirmar consumidores únicos; P90 = percentil contínuo das durações válidas. A classificação compara o mês civil anterior: 10% é moderado, 25% relevante. Requer 10 registros, quantidade completa, 95% de datas válidas e 10 durações. Esses são critérios de triagem versionados, não limites ANEEL nem significância estatística.

Confiança é ordinal: insuficiente, limitada, adequada ou consistente. Expõe comparação, histórico, datas, schema, volume, ausências e integridade. Não é probabilidade nem medida de fornecimento.

O ZIP contém `dossie.md`, `registros.csv` e `manifesto.json` com filtros, fórmulas, métricas, regras, versões e hash.

## Testes e vídeo

Os testes cobrem limiares, dados insuficientes, lacunas, base zero, divergência e revisão. A matriz completa de requisito, implementação, teste e demonstração será mantida em `docs/MATRIZ_REQUISITOS.md` antes da entrega.

Roteiro: selecionar conjunto → motivo do destaque → Dossiê → registros → confiança → ZIP → atualização/rastreabilidade e limites. Não alegar resultados antes do perfil da fonte oficial.
