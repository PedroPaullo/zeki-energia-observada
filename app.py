import os
import streamlit as st
import plotly.express as px
from energia_observada import service

st.set_page_config(page_title='Energia Observada',layout='wide')
st.title('Energia Observada')
st.caption('Dossiê de Investigação de interrupções nas redes de distribuição')
try:
    state=service.status(); active=state['active']
    if not active:
        st.warning('Nenhuma versão validada está publicada. A aplicação não exibe indicadores sem uma fonte validada.')
        if state['last_attempt']: st.json(state['last_attempt'])
        st.stop()
    if active['mode']=='sample': st.warning('MODO AMOSTRA: comparações nacionais estão desabilitadas.')
    st.caption(f"Versão {active['version']} · aquisição {active.get('acquired_at','não informado')} · SHA-256 {active['sha256'][:16]}…")
    c=service.choices(); byname={f"{x['display_name']} ({x['cnpj']})":x for x in c['distributors']}; dn=st.sidebar.selectbox('Distribuidora',list(byname)); d=byname[dn]
    groups=[x for x in c['conjuntos'] if x['cnpj']==d['cnpj']]; gm={f"{x['display_name']} ({x['conjunto']})":x for x in groups}; gn=st.sidebar.selectbox('Conjunto elétrico',list(gm)); g=gm[gn]; period=st.sidebar.selectbox('Competência',c['periods'],index=len(c['periods'])-1)
    dossier=service.build_dossier(d['cnpj'],g['conjunto'],period)
    st.subheader('Dossiê de Investigação')
    st.info(' · '.join(x['text'] for x in dossier['assessment']['narrative']))
    cols=st.columns(3)
    for col,(name,key) in zip(cols,[('Registros','records'),('Afetações reportadas','affected'),('P90 duração (h)','p90_hours')]): col.metric(name,dossier['current'].get(key) if dossier['current'] else '—')
    st.subheader('Situação e confiança da evidência')
    st.write(f"**Situação:** {dossier['assessment']['situation']['label']}  |  **Confiança:** {dossier['assessment']['confidence']['level']}")
    st.dataframe(dossier['assessment']['confidence']['components'],use_container_width=True)
    st.caption(dossier['context']['notice'])
    if dossier['history']:
        st.plotly_chart(px.line(dossier['history'],x='_eo_period',y='affected',markers=True,title='Série histórica de afetações reportadas'),use_container_width=True)
    st.subheader('Registros-fonte')
    st.dataframe(dossier['records_preview'],use_container_width=True)
    st.caption(f"Prévia limitada a 100 registros das competências {', '.join(dossier['evidence_periods'])}; a exportação preserva todos os registros aceitos dos dois meses.")
    if st.button('Gerar pacote de evidências'):
        st.session_state['evidence_package']=str(service.export_dossier(dossier))
    if package:=st.session_state.get('evidence_package'):
        output=__import__('pathlib').Path(package)
        if output.stat().st_size<=20*1024*1024: st.download_button('Baixar pacote de evidências',output.read_bytes(),file_name=output.name,mime='application/zip')
        else: st.info(f'Pacote maior que 20 MiB disponível em: {output.resolve()}')
    with st.expander('Fórmulas e limites'): st.json({'formulas':dossier['formulas'],'limitations':dossier['limitations'],'regras':dossier['assessment']['parameters']})
except Exception as exc:
    st.error(f'Não foi possível montar o dossiê: {type(exc).__name__}: {exc}')
