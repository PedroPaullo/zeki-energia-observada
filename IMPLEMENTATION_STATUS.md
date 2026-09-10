# Retomada da implementação — 10/09/2026

Execução pausada a pedido de Pedro para trocar para Luna e preservar limites. O plano completo aprovado está na conversa. Não considerar o produto implementado ou validado.

## Estado confirmado
- Pasta independente criada; Git inicializado na branch `feat/energia-observada`, ainda sem commits/remoto.
- Criados `pyproject.toml`, `.gitignore`, `.env.example`, `CONTRACTS.md` e `energia_observada/__init__.py`.
- `.venv` própria criada com Python 3.12.13 do runtime local; `pip install -e '.[test]'` iniciado. Na última checagem `pip show energia-observada` ainda não encontrava o pacote: verificar conclusão antes de repetir instalação.
- Nenhum dado oficial adquirido; o último curl terminou em timeout. PyPI e GitHub responderam. O repositório `PedroPaullo/zeki-energia-observada` ainda não existe.
- Agentes de regras e interface foram interrompidos; ainda não haviam gravado seus arquivos na última inspeção. Não depender de trabalho em memória desses agentes e não reativar agentes do modelo anterior se isso contrariar a redução de custo solicitada.

## Próximos passos exatos
1. Ler o plano aprovado e `CONTRACTS.md`. Confirmar Git, arquivos e importações na `.venv`.
2. Implementar aquisição/profile/pipeline, motor de regras com testes, serviço de consultas/dossiê/exportação, CLI e interface, respeitando a condição de validar dados reais antes de exibir indicadores reais.
3. Para fonte inacessível localmente, testar download oficial em GitHub Actions após preparar workflow revisável; usuário autorizou repositório público. Não substituir fonte por espelho nem desativar certificados. Recuperar artifact com bruto e manifesto para preservar proveniência.
4. Executar todas as validações do plano e instalação limpa; criar recorte autêntico de demonstração só após validar a origem.
5. Documentar resultados reais, publicar código revisado, confirmar CI e preparar roteiro de vídeo. Não enviar e-mail à Zeki sem pedido explícito.

## Decisões de integração já comunicadas
- `confidence.components`: sete objetos `{name, value, status}`; `value` texto e status `ok/warning/error`.
- Manifesto ativo terá `mode` (`national`/`sample`), `acquired_at`, `sha256`, `source_url`, `resource_id`, `year`, `profile`, `version`, `previous_version`, `integrity_verified`.
- Dossiê terá `records_preview_limit=100`; adicionar `service.records_page(dossier, offset=0, limit=100, data_dir=None)` para paginação. Exportação completa sem truncamento silencioso.
- Contexto estruturado em `self_history`, `peers`, `national`, com status e motivo de indisponibilidade; fórmulas como dicionário e limitações como lista de textos.
- Preferir memória DuckDB limitada (256MB), uma thread e arquivos em disco; máquina com RAM restrita. Não carregar fonte inteira em pandas.
