# Relatório de validação final

## Escopo verificado

O produto foi validado com uma amostra autêntica ANEEL de quatro conjuntos ENEL CE e com o arquivo nacional oficial de 2026 já adquirido. A execução nacional verificou o arquivo bruto, o modelo e as métricas de JUREMA por consulta independente sobre os registros, sem confiar na tabela mensal publicada.

## Evidência nacional

- Fonte: recurso ANEEL de interrupções 2026.
- Arquivo: 204.708.716 bytes; SHA-256 `53064794800a0dcff29784c03ccfa84c24f7c290f80c14889d0e950a19f82823`.
- Estrutura: 26 colunas, 6.078.331 linhas; assinaturas `PAR1` inicial e final válidas.
- Modelo: 6.077.982 linhas aceitas, 349 duplicatas marcadas, 20.299 durações inválidas preservadas como nulas.
- Caso: JUREMA, ENEL CE, junho/julho de 2026; contagem, soma e P90 coincidem entre consulta independente e modelo.
- Contextos nacional e da distribuidora disponíveis no modo nacional.

O relatório bruto dos checks está em `VALIDACAO_NACIONAL.json`.

## Testes funcionais

`pytest` cobre regras, pipeline, falhas de arquivo, exportação, revisão, contexto, filtros, estado vazio e aplicação Streamlit com a amostra autêntica. O teste funcional abre a tela, verifica ausência de erro tratado, métricas de JUREMA, abas, exportação e invalidação do download quando a competência muda.

`scripts/validate_browser.py` usa Chrome automatizado para abrir a aplicação real, registrar screenshots, navegar pelas abas, exportar o ZIP e verificar o pacote baixado. As imagens ficam em `docs/images/`.

## Riscos conhecidos e limites

- O Actions valida a aquisição mensal em runner efêmero; detectar revisão entre aquisições exige que versões locais sejam preservadas.
- O modo demonstração não permite afirmação nacional nem equivalência estatística.
- A ANEEL pode revisar arquivos no futuro; “revisão não detectada” só se aplica às versões comparadas.
- O produto não identifica causa, evento único ou consumidor único.
