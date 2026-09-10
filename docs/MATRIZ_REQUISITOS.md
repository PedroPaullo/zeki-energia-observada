# Matriz de requisitos

| Requisito | Implementação | Teste | Demonstração |
|---|---|---|---|
| Atualização mensal | `ingest`/`update` + manifesto | pipeline | última tentativa e versão |
| Rastreabilidade | SHA-256, bruto, versão, ZIP | exportação | abrir `manifesto.json` |
| Dossiê | `service.build_dossier` + `app.py` | pipeline | conjunto → evidências |
| Regras transparentes | `rules.py` | limites e divergência | parâmetros no Dossiê |
| Confiança | sete componentes ordinais | regras | checklist visível |
| Fonte indisponível | `last_attempt.json` | estado vazio | versão válida preservada |
