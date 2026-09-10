"""Investigation workspace; calculations remain in the analytical service."""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from energia_observada import service

st.set_page_config(page_title="Energia Observada | Investigação", page_icon="⚡", layout="wide")
st.markdown("""<style>
.block-container {padding-top:4rem;max-width:1450px}
div[data-testid="stMetric"] {background:#142332;border:1px solid #2a4354;border-radius:12px;padding:18px}
div[data-testid="stMetric"] label, div[data-testid="stMetricValue"], div[data-testid="stMetricDelta"] {color:#eef5fa !important}
div[data-testid="stMetricDelta"] svg {fill:#38b8ad !important}
.eyebrow {color:#38b8ad;font-size:13px;font-weight:700;letter-spacing:2px}
</style>""", unsafe_allow_html=True)
LABELS = {"records": "Registros", "affected": "Afetações reportadas", "p90_hours": "P90 da duração (h)"}

def number(value, decimals=0):
    if value is None:
        return "—"
    return f"{value:,.{decimals}f}".replace(",", "_").replace(".", ",").replace("_", ".")

def render():
    st.markdown('<div class="eyebrow">ANEEL / EVIDÊNCIA ABERTA</div>', unsafe_allow_html=True)
    st.title("Energia Observada")
    st.write("**Qual conjunto merece investigação neste mês — e quais registros sustentam esse destaque?**")
    state = service.status()
    active = state["active"]
    if not active:
        st.warning("Nenhuma versão validada está publicada. Execute a demonstração para começar.")
        st.code("python -m energia_observada demo --launch", language="powershell")
        if state["last_attempt"]:
            st.json(state["last_attempt"])
        st.stop()
    if active["mode"] == "sample":
        st.warning("AMOSTRA AUTÊNTICA ANEEL · recorte de demonstração. Não representa cobertura nacional; comparação nacional bloqueada.")
    else:
        st.info("ARQUIVO NACIONAL CARREGADO · cobertura limitada às distribuidoras e competências presentes; permissionárias/cooperativas excluídas pela fonte.")
    if (state.get("last_attempt") or {}).get("status") == "failed":
        st.warning("A última atualização falhou. Você está consultando a última versão validada.")
    c = service.choices()
    st.sidebar.header("Recorte da investigação")
    period = st.sidebar.selectbox("Competência", c["periods"], index=len(c["periods"])-1)
    names = {x["cnpj"]: x["display_name"] for x in c["distributors"]}
    groups = {(x["cnpj"], x["conjunto"]): x["display_name"] for x in c["conjuntos"]}
    distributor = st.sidebar.selectbox("Distribuidora", [None, *names], format_func=lambda x: "Todas as distribuidoras" if x is None else names[x])
    municipality = st.sidebar.selectbox("Município do equipamento (IBGE)", [None, *c["municipalities"]], format_func=lambda x: "Todos os municípios" if x is None else str(x))
    st.sidebar.caption("O município localiza o equipamento. Não delimita necessariamente os consumidores afetados.")
    q = service.queue(period, cnpj=distributor, municipio=municipality)
    st.subheader("1. Fila de investigação")
    st.caption("Ordem por aumento absoluto de afetações reportadas. Volume orienta a triagem; não mede qualidade relativa do fornecimento.")
    if not q:
        st.info("Nenhum conjunto observado neste recorte. Ausência de dados não equivale à ausência de interrupções.")
        st.stop()
    view = [{"Conjunto": groups.get((r["cnpj"],r["conjunto"]),r["conjunto"]), "Distribuidora": names.get(r["cnpj"],r["cnpj"]),
             "Registros": r.get("records"), "Afetações atuais": r.get("affected"), "Afetações anteriores": r.get("previous_affected"),
             "Variação absoluta": r.get("change"), "Situação": r.get("situation","Consultar dossiê")} for r in q]
    st.dataframe(view[:20], width="stretch", hide_index=True)
    st.caption(f"Exibindo {min(20,len(q))} de {len(q)} conjuntos. Todos disponíveis na seleção abaixo.")
    queue_options = [(r["cnpj"],r["conjunto"]) for r in q]
    if st.session_state.get("selected_queue_item") not in queue_options:
        st.session_state["selected_queue_item"] = queue_options[0]
    selected = st.selectbox("Selecionar conjunto da fila", queue_options, key="selected_queue_item",
                            format_func=lambda x: f"{groups.get(x,x[1])} ({x[1]}) · {names.get(x[0],x[0])}")
    dossier = service.build_dossier(*selected, period, municipio=municipality)
    identity = json.dumps([active["version"], selected, period, municipality])
    if st.session_state.get("evidence_selection") != identity:
        st.session_state.pop("evidence_package",None)
    st.subheader(f"2. Dossiê de Investigação · {groups.get(selected,selected[1])}")
    assessment = dossier["assessment"]
    st.write(f"**{period} · {assessment['situation']['label'].capitalize()}**")
    if assessment["situation"].get("divergent"):
        st.warning("Indicadores divergentes: há aumentos e quedas. O aumento prevalece na triagem; confira ambos.")
    for col,(key,label) in zip(st.columns(3),LABELS.items()):
        pct=assessment.get("changes",{}).get(key,{}).get("percent")
        col.metric(label,number((dossier.get("current") or {}).get(key),2 if key=="p90_hours" else 0),
                   "sem comparação percentual" if pct is None else f"{number(pct,2)}% frente ao mês anterior",delta_color="off")
    tabs=st.tabs(["Por que investigar","Histórico e contexto","Sinais reportados","Confiança","Registros-fonte","Exportar e reproduzir"])
    with tabs[0]:
        for i,section in enumerate(assessment["narrative"],1):
            st.markdown(f"**{section.get('title',f'Ponto {i}')}**")
            st.write(section["text"])
            st.caption("Rastreabilidade: "+", ".join(section.get("references",[])))
        st.markdown("#### Atual e anterior, lado a lado")
        st.dataframe([{"Indicador":label,"Atual":(dossier.get("current") or {}).get(key),"Anterior":(dossier.get("previous") or {}).get(key),
                       "Variação (%)":assessment.get("changes",{}).get(key,{}).get("percent")} for key,label in LABELS.items()],hide_index=True,width="stretch")
    with tabs[1]:
        history=dossier.get("history",[])
        if history:
            metric=st.selectbox("Indicador da série",list(LABELS),format_func=LABELS.get)
            frame=pd.DataFrame(history)
            frame["Competência"]=[r.get("period",r.get("_eo_period")) for r in history]
            frame=frame.set_index("Competência")
            frame=frame.reindex(pd.period_range(frame.index.min(),period,freq="M").astype(str)).rename_axis("Competência").reset_index()
            fig=px.line(frame,x="Competência",y=metric,markers=True,labels={metric:LABELS[metric]},color_discrete_sequence=["#24b4a7"])
            fig.update_traces(connectgaps=False)
            fig.update_layout(height=310,margin=dict(l=10,r=10,t=15,b=10))
            st.plotly_chart(fig,width="stretch")
            st.caption("Lacunas preservadas; histórico até o mês selecionado. Não se infere sazonalidade.")
        context=dossier.get("context",{})
        st.caption(context.get("notice","Comparação descritiva; equivalência estatística não estabelecida."))
        for key,title in [("own_history","O conjunto diante da própria história"),("distributor","Outros conjuntos da mesma distribuidora"),("national","Distribuidora e demais distribuidoras carregadas")]:
            st.markdown(f"#### {title}")
            item=context.get(key,{})
            if item.get("reason"): st.info(item["reason"])
            if "included" in item: st.write(f"Incluídos: {item['included']} · Excluídos: {item.get('excluded',0)}")
            if item.get("median"): st.write("Mediana histórica:",item["median"])
            if item.get("distribution"): st.dataframe(item["distribution"],hide_index=True,width="stretch")
            with st.expander("População, critérios e valores"):
                st.json(item)
    with tabs[2]:
        signals=dossier.get("reported_signals",{})
        st.warning(signals.get("notice","Classificações da fonte não provam causa raiz."))
        st.write("Use esta aba para formular uma hipótese e escolher quais registros conferir. Não atribua causalidade ao conjunto com base apenas nestas categorias.")
        labels={"DscFatoGeradorOrigem":"Origem reportada","DscFatoGeradorTipo":"Tipo reportado","DscFatoGeradorCausa":"Causa reportada","DscFatoGeradorDetalhe":"Detalhe reportado"}
        field=st.selectbox("Classificação a conferir",list(labels),format_func=labels.get)
        rows=signals.get("fields",{}).get(field,[])
        if rows:
            st.dataframe(rows,hide_index=True,width="stretch")
            st.caption("Afetações reportadas são somas de linhas da categoria, não consumidores únicos.")
        else: st.info("A fonte não trouxe classificação para este recorte.")
    with tabs[3]:
        confidence=assessment["confidence"]
        st.markdown(f"### Evidência {confidence['level']}")
        st.write("Sustentação documental da comparação. Não é probabilidade estatística nem nota de qualidade do fornecimento.")
        for component in confidence["components"]:
            st.markdown(f"**{component['name']}** · {component['value']}")
            with st.expander(f"Como foi verificado: {component['name']}"): st.json(component)
        with st.expander("Comparação com aquisições anteriores"): st.json(dossier.get("revision",{}))
    with tabs[4]:
        preview=dossier.get("records_preview",[])
        st.caption(f"Prévia de {len(preview)} registros. O pacote exporta toda a evidência utilizada, sem truncamento silencioso.")
        fields=["_eo_period","CodInterrupcao","DatInicioInterrupcao","DatFimInterrupcao","QtdConsumidoresAfetados","CodMunicipioIBGE","_eo_row"]
        st.dataframe([{k:r.get(k) for k in fields} for r in preview],hide_index=True,width="stretch")
        with st.expander("Todos os campos da prévia"): st.dataframe(preview,hide_index=True,width="stretch")
        st.write("Versão do dado:",active["version"])
        st.write("Aquisição (UTC):",active.get("acquired_at"))
        st.code(active["sha256"],language=None)
        st.link_button("Abrir arquivo oficial ANEEL",active["source_url"])
        if active.get("source_sha256"):
            st.caption("Hash do arquivo nacional de origem da amostra:")
            st.code(active["source_sha256"],language=None)
    with tabs[5]:
        st.write("Leitura humana, registros usados e manifesto para recalcular as conclusões fora desta sessão.")
        if st.button("Gerar pacote de evidências",type="primary"):
            with st.spinner("Reunindo registros e calculando hashes…"): output=service.export_dossier(dossier)
            st.session_state["evidence_package"]=str(output)
            st.session_state["evidence_selection"]=identity
        if package:=st.session_state.get("evidence_package"):
            output=Path(package)
            st.success(f"Pacote gerado · {number(output.stat().st_size/1024,1)} KiB")
            if output.stat().st_size<=20*1024*1024: st.download_button("Baixar pacote de evidências",output.read_bytes(),file_name=output.name,mime="application/zip")
            else: st.info(f"Pacote acima de 20 MiB disponível em: {output.resolve()}")
            st.code(f'python -m energia_observada verify "{output}"',language="powershell")
        with st.expander("Fórmulas, parâmetros e regra acionada"):
            st.json({"formulas":dossier["formulas"],"parameters":assessment["parameters"],"situation":assessment["situation"],"rules_version":assessment["rules_version"]})
        with st.expander("Operação mensal e última tentativa"):
            st.code("python -m energia_observada update --year 2026",language="powershell")
            st.json(state.get("last_attempt"))
    st.divider()
    for limitation in dossier["limitations"]: st.caption(limitation)
    st.caption(f"Versão {active['version']} · Regras {assessment['rules_version']} · Atualização mensal da fonte")

try:
    render()
except Exception as exc:
    st.error(f"Não foi possível montar o dossiê: {type(exc).__name__}: {exc}")
    st.caption("A consulta falhou. Não interprete indicadores de uma tela incompleta.")
