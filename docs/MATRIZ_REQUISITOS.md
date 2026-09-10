# Matriz de requisitos

| Requisito | Implementação verificável | Teste | Evidência na demonstração |
|---|---|---|---|
| Fonte oficial e versão | URL, recurso, UTC, tamanho e SHA-256 no manifesto | validação de schema | `demo/manifest.json` e `manifesto.json` do ZIP |
| Atualização mensal | `ingest`/`transform`/`update`; publicação só após reconciliação | idempotência e schema rejeitado | `python -m energia_observada status` |
| Dossiê investigável | `service.build_dossier` e `app.py` | pipeline e exportação | conjunto → métricas → junho/julho |
| Regras transparentes | `rules.py`, versão e parâmetros no manifesto | limites -10%, +10%, +25%, zero e divergência | situação “aumento relevante” e expander de regras |
| Confiança documental | sete componentes ordinais | componentes e revisão | checklist “consistente” |
| Registros-fonte | CSV completo de competência atual e comparada | contagem do ZIP | prévia e `registros.csv` com 1.364 linhas |
| Contexto | série própria e aviso de equivalência | regras | aviso permanente de comparação descritiva |
| Falha segura | `last_attempt.json`; ativo só muda ao publicar | estado vazio | erro não cria indicadores vazios |
| Reprodução local | amostra ANEEL autenticada no repositório | `demo` + pytest | quatro comandos do README |
| Limites de interpretação | avisos na interface, README e Markdown | conteúdo do dossiê | encerramento do vídeo |
