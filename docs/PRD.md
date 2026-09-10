# PRD e critérios de aceite

- **AC-FILA-01:** dado que competência e filtros são selecionados, quando a fila é exibida, então mostra registros, afetações atual/anterior, variação e situação ordenados pela variação absoluta.
- **AC-DOS-01:** dado que um conjunto é selecionado, quando o Dossiê abre, então mostra motivo, variação, métricas, dimensões, histórico, qualidade, registros e limites.
- **AC-DOS-02:** dado que mês anterior utilizável existe, quando a situação é calculada, então usa registros, afetações e P90 com regras versionadas e exibe divergências.
- **AC-CON-01:** dado que existem seis meses anteriores utilizáveis, quando o contexto próprio aparece, então mostra a mediana sem alegar sazonalidade.
- **AC-CON-02:** dado que pares elegíveis existem, quando contexto de distribuidora ou nacional aparece, então mostra inclusão/exclusão e bloqueia nacional no modo amostra.
- **AC-CON-03:** dado que versões analíticas do mesmo recorte divergem, quando o Dossiê abre, então informa possível revisão; reordenação, período novo e outro conjunto não disparam a regra.
- **AC-EVID-01:** dado que o usuário exporta, quando baixa o ZIP, então recebe Markdown, CSV e manifesto com hashes, filtros, fórmulas, versões e escopo contextual.
- **AC-EVID-02:** dado que executa `verify`, quando o pacote é lido, então hashes e conclusões são recalculados sem dados da aplicação.
- **AC-PIPE-01:** dado que a aquisição é inválida, truncada ou tem schema divergente, quando falha, então a versão válida anterior continua ativa e o erro fica registrado.
- **AC-PIPE-02:** dado que a mesma aquisição roda duas vezes, quando o pipeline termina, então não duplica registros nem publica nova versão.
