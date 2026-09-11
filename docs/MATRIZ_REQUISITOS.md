# Matriz requisito -> implementação -> teste -> demonstração

| Critério | Implementação | Evidência automatizada | Demonstração |
|---|---|---|---|
| Problema e usuário | `BRIEF_PRODUTO.md` e abertura da tela | revisão de documentação | explicar a decisão “qual conjunto investigar primeiro?” |
| Fonte oficial | URL, recurso, tamanho, SHA, schema e PAR1 | `test_pipeline_failures.py`; `VALIDACAO_NACIONAL.json` | abrir hash e URL ANEEL |
| Atualização mensal | `ingest`, `transform`, `update`, workflow agendado | idempotência, pendência antiga, falha segura | mostrar comando `update` e `last_attempt` |
| Fila | `service.queue`, ordenação por variação absoluta | serviço e teste de tela | selecionar JUREMA na fila |
| Dossiê completo | oito seções determinísticas | `test_rules_acceptance.py` | abrir “Por que investigar” |
| Regras | `rules.py` 1.1.0; -10%, +10%, +25% | limites, base zero, divergência, nove/dez registros | abrir parâmetros e regra acionada |
| Confiança | sete componentes com numeradores e denominadores | limites de qualidade e histórico | abrir checklist sem chamar de probabilidade |
| Contexto próprio | mediana dos seis meses anteriores utilizáveis | `test_service_evidence.py` | série e mediana |
| Contexto distribuidora | variações individuais elegíveis e inclusão/exclusão | `test_service_evidence.py` | pares ENEL CE na amostra |
| Contexto nacional | população fixa de grupos nos dois meses | validação nacional; teste sintético | executar só em modo nacional |
| Panorama completo | `service.national_overview` agrega todas as distribuidoras carregadas | `test_national_overview_includes_distributors_and_bounded_forecast` | tabela e gráfico no modo nacional |
| Previsão transparente | tendência linear limitada a zero, com janela e método declarados | mesmo teste de panorama | projeção da próxima competência |
| Comparação territorial | UF derivada dos dois primeiros dígitos IBGE, explicitamente identificada | mesmo teste de panorama | tabela agregada por UF |
| Revisão de fonte | comparação de multiconjunto de hashes no mesmo recorte | revisão, reordenação, novo período e outro conjunto | abrir revisão no Dossiê |
| Registros e exportação | CSV em fluxo, Markdown, manifesto, hashes | `verify_export`, exportação alterada | gerar, baixar e verificar ZIP |
| Filtros | competência, distribuidora e município do equipamento | `test_service_evidence.py`; teste de tela | trocar filtro e explicar limite geográfico |
| Estado vazio/erro | tela sem versão; ativo preservado após falha | `test_app.py`, testes de pipeline | mostrar erro documentado sem indicadores vazios |
| Instalação limpa | `abrir-demo.cmd` e `demo --launch` | AppTest e browser smoke | executar do zero |
| Vídeo | roteiro cronometrado e cola PDF | inspeção PDF e roteiro | gravação até cinco minutos |
