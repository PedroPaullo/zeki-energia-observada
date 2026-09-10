# Energia Observada

Um analista seleciona um conjunto elétrico destacado na fila e recebe um **Dossiê de Investigação rastreável**: por que entrou na fila, o que variou, registros originais, regras, confiança da evidência e um ZIP para reprodução. Ele apoia a decisão de investigar; não atribui causa.

## Demonstração pronta para o avaliador

O repositório inclui uma amostra autêntica, pequena e identificada da fonte ANEEL. Ela permite executar o fluxo sem baixar 195 MiB:

```powershell
git clone https://github.com/PedroPaullo/zeki-energia-observada.git
cd zeki-energia-observada
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
python -m energia_observada demo
python -m streamlit run app.py
```

No navegador, escolha **COMPANHIA ENERGETICA DO CEARA → JUREMA (13317) → 2026-07**, gere e baixe o pacote. A amostra contém 5.194 registros de janeiro a julho de 2026; seu manifesto registra o hash do recorte e o hash da fonte nacional de origem. O modo amostra desabilita a comparação nacional.

## Caso demonstrado com dados oficiais

O arquivo oficial de 2026 foi adquirido e validado em 10/09/2026: 204.708.716 bytes, SHA-256 `53064794800a0dcff29784c03ccfa84c24f7c290f80c14889d0e950a19f82823`, 6.078.331 linhas, 26 colunas, sete competências e 51 distribuidoras. Após tratamento auditado, 6.077.982 linhas foram aceitas, 349 duplicadas foram marcadas e 20.299 durações inválidas foram preservadas como ausência, nunca convertidas em zero.

No caso JUREMA, julho teve 729 registros e 279.285 afetações reportadas, contra 635 e 20.247 em junho. A situação é **aumento relevante** pela regra explícita de +25%; a confiança é **consistente** porque há sete competências, comparação disponível, campos exigidos, datas válidas no mês e integridade conciliada. “Afetações reportadas” não significa consumidores únicos.

## Fonte e limites

Fonte: [Interrupções de Energia Elétrica nas Redes de Distribuição — ANEEL](https://dadosabertos.aneel.gov.br/dataset/interrupcoes-de-energia-eletrica-nas-redes-de-distribuicao), atualizada mensalmente. A cobertura informada pela fonte exclui permissionárias e cooperativas.

- Aumento de interrupções não prova a causa.
- Município identifica o equipamento, não necessariamente os consumidores afetados.
- Ausência de dados não equivale à ausência de interrupções.
- Não calcula DEC/FEC e não substitui análise regulatória ou técnica.

## Arquitetura e rastreabilidade

`fonte oficial → bruto imutável + SHA-256 → validação de schema → Parquet normalizado → DuckDB → regras versionadas → Dossiê/ZIP/Streamlit`

Cada aquisição guarda URL, recurso, UTC, tamanho, hash, schema, contagens, rejeições e erros. A publicação é atômica: erro na aquisição ou transformação mantém a última versão válida. `manifesto.json` do ZIP contém filtros, fórmulas, métricas, parâmetros, versão e hashes; `registros.csv` inclui todos os registros aceitos do mês atual e do mês comparado.

## Dados nacionais e atualização

Para processar o arquivo completo, a máquina precisa de espaço livre para bruto, modelo e temporários. O pipeline usa uma thread e 256 MB de memória DuckDB por padrão.

```powershell
python -m energia_observada ingest --year 2026
python -m energia_observada transform
python -m energia_observada update --year 2026
python -m energia_observada status
python -m pytest
```

## Regras transparentes

Indicadores: registros aceitos, soma de `QtdConsumidoresAfetados` válida e P90 contínuo das durações válidas. Compara-se o mês civil anterior. Um mês é utilizável com ao menos 10 registros, quantidades completas, 95% de datas válidas e 10 durações válidas. +10% indica deterioração moderada; +25%, aumento relevante. São regras operacionais versionadas, sem alegação de significância estatística ou padrão regulatório.

O nível de confiança é ordinal — insuficiente, limitada, adequada ou consistente — e explica sete componentes: comparação, histórico, datas, schema, volume, ausências e integridade. Não é probabilidade nem avaliação da qualidade do fornecimento.

## Como auditar a entrega

```powershell
git log --reverse --oneline
git diff --check
python -m pytest
python -m energia_observada demo
python -m energia_observada dossier --cnpj 07047251000170 --conjunto 13317 --period 2026-07
```

Veja [docs/MATRIZ_REQUISITOS.md](docs/MATRIZ_REQUISITOS.md) e [docs/ROTEIRO_VIDEO.md](docs/ROTEIRO_VIDEO.md) para a correspondência requisito → implementação → teste → demonstração.
