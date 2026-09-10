"""Generate the concise five-minute recording guide and keep it in the repository."""
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output'/'pdf'/'cola-video-energia-observada.pdf'

def text(value):
    return value.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

def main():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    styles=getSampleStyleSheet()
    title=ParagraphStyle('title',parent=styles['Title'],fontName='Helvetica-Bold',fontSize=23,leading=28,textColor=colors.HexColor('#102c43'),spaceAfter=10)
    subtitle=ParagraphStyle('subtitle',parent=styles['Normal'],fontSize=10.5,leading=15,textColor=colors.HexColor('#416173'),spaceAfter=14)
    heading=ParagraphStyle('heading',parent=styles['Heading2'],fontName='Helvetica-Bold',fontSize=14,leading=18,textColor=colors.HexColor('#006d77'),spaceBefore=12,spaceAfter=6)
    body=ParagraphStyle('body',parent=styles['BodyText'],fontSize=9.4,leading=13.5,spaceAfter=5)
    cue=ParagraphStyle('cue',parent=body,backColor=colors.HexColor('#edf7f6'),borderColor=colors.HexColor('#72b7b2'),borderWidth=.5,borderPadding=7,spaceBefore=4,spaceAfter=8)
    warn=ParagraphStyle('warn',parent=body,backColor=colors.HexColor('#fff3d6'),borderColor=colors.HexColor('#d69e2e'),borderWidth=.5,borderPadding=7,spaceBefore=4,spaceAfter=8)
    doc=SimpleDocTemplate(str(OUT),pagesize=A4,rightMargin=1.55*cm,leftMargin=1.55*cm,topMargin=1.35*cm,bottomMargin=1.25*cm)
    story=[Paragraph('Cola de vídeo - Energia Observada',title),Paragraph('Duração total: até 5 minutos. Abra antes <b>abrir-demo.cmd</b>; no navegador, use <b>http://localhost:8502</b>. Caso: ENEL CE, JUREMA (13317), 2026-07.',subtitle)]
    rows=[['Tempo','Clique / mostre','Fale'],
      ['0:00-0:25','Rosto + tela inicial','“Energia Observada ajuda um analista a decidir qual conjunto elétrico investigar primeiro, usando os dados mensais públicos da ANEEL. O produto não diz a causa da interrupção; ele entrega evidência rastreável para iniciar a investigação.”'],
      ['0:25-0:55','Fila de investigação','“Aqui está a fila de julho de 2026. Ela é ordenada pelo aumento absoluto de afetações reportadas. JUREMA aparece primeiro: 279.285 em julho contra 20.247 em junho. Isso é uma prioridade de leitura, não uma conclusão sobre qualidade ou causa.”'],
      ['0:55-1:30','Seleção JUREMA + cards','“Seleciono JUREMA, da Companhia Energética do Ceará. O Dossiê compara registros, afetações reportadas e P90 da duração. A situação é aumento relevante porque a variação de afetações cruzou a regra operacional de 25%. As regras são transparentes e versionadas.”'],
      ['1:30-2:10','Aba Por que investigar','“O Dossiê explica por que o conjunto entrou na fila, as métricas que mudaram, o histórico disponível, os problemas de qualidade e o que os dados não permitem afirmar. Registros não são eventos únicos e afetações reportadas não são consumidores únicos.”'],
      ['2:10-2:35','Histórico e contexto','“A série preserva lacunas. A comparação própria usa a mediana das seis competências anteriores quando elas são utilizáveis. A comparação com pares mostra quantos conjuntos entraram e ficaram fora. No modo de amostra, a comparação nacional fica bloqueada porque esse recorte não representa o país.”'],
      ['2:35-2:55','Sinais reportados','“A fonte também traz origem, tipo, causa e detalhe reportados. Eu os uso como hipótese de investigação e confiro as linhas que os registraram. Eles não provam causa raiz, responsabilidade ou nexo causal; para isso seriam necessárias evidências externas e análise técnica.”'],
      ['2:55-3:25','Confiança','“A confiança é documental, não é probabilidade. Ela expõe mês anterior, histórico, datas válidas, schema, registros usados, nulos e integridade. Aqui ela é consistente porque há comparação utilizável, sete competências e integridade conciliada.”'],
      ['3:25-4:00','Registros-fonte','“Agora eu confiro os registros originais que sustentam a leitura. Cada linha mantém o identificador de origem, a competência e os campos usados. O município é localização do equipamento; não representa necessariamente os consumidores afetados.”'],
      ['4:00-4:35','Exportar e reproduzir','“Gero o pacote de evidências. Ele entrega Markdown legível, CSV dos registros e manifesto com filtros, regras, versões e hashes. Este comando verifica o ZIP sem depender da sessão da aplicação.”'],
      ['4:35-5:00','README ou terminal','“O pipeline guarda o bruto, valida PAR1 e schema, publica somente após reconciliação e preserva a última versão válida se a atualização falhar. A decisão técnica foi privilegiar rastreabilidade e limites honestos, não uma explicação decorativa.”']]
    table=Table([[Paragraph(text(cell),body) for cell in row] for row in rows],colWidths=[2.05*cm,4.0*cm,10.0*cm],repeatRows=1)
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#102c43')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.35,colors.HexColor('#b8c7d0')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f4f8fa')]),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    story += [table,Spacer(1,8),Paragraph('<b>Antes de gravar</b>: selecione JUREMA e 2026-07; gere o ZIP uma vez; deixe o README aberto em outra aba; confirme que a webcam está visível no Loom.',cue),Paragraph('<b>Não diga</b>: “a causa foi…”, “consumidores únicos”, “cobertura nacional” no modo amostra, “a confiança é uma probabilidade” ou “o município foi afetado”. Diga somente o que os dados e regras mostrados permitem.',warn),Paragraph('Plano de recuperação',heading),Paragraph('Se a tela não abrir, execute <font name="Courier">abrir-demo.cmd</font>. Se o navegador mantiver uma versão antiga, pare o Streamlit com Ctrl+C e rode <font name="Courier">python -m energia_observada demo --launch --port 8502</font>. Se o ZIP não aparecer, clique em “Gerar pacote de evidências” e espere a confirmação verde.',body),Paragraph('Três frases para decorar',heading),Paragraph('1. “A fila prioriza investigação; ela não prova causalidade.”<br/>2. “A causa reportada pela fonte é uma hipótese verificável, não uma prova de causa raiz.”<br/>3. “O pacote permite conferir a conclusão nos registros e no manifesto.”',cue)]
    def page(canvas,doc):
        canvas.saveState(); canvas.setStrokeColor(colors.HexColor('#72b7b2')); canvas.line(1.55*cm,1.0*cm,A4[0]-1.55*cm,1.0*cm); canvas.setFont('Helvetica',8); canvas.setFillColor(colors.HexColor('#416173')); canvas.drawString(1.55*cm,.65*cm,'Energia Observada | cola de gravação'); canvas.drawRightString(A4[0]-1.55*cm,.65*cm,f'Página {doc.page}'); canvas.restoreState()
    doc.build(story,onFirstPage=page,onLaterPages=page)
    print(OUT)

if __name__=='__main__': main()
