"""Real Chromium smoke test: rendering, filters, ZIP download and screenshots."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import sync_playwright
from energia_observada.service import verify_export

ROOT = Path(__file__).resolve().parent.parent
PORT = 8511

def main():
    images=ROOT/'docs'/'images'
    images.mkdir(parents=True,exist_ok=True)
    logs=ROOT/'tmp'
    logs.mkdir(exist_ok=True)
    with (logs/'browser-server.log').open('w',encoding='utf-8') as log:
        process=subprocess.Popen([sys.executable,'-m','streamlit','run','app.py','--server.port',str(PORT),'--server.headless','true','--browser.gatherUsageStats','false'],cwd=ROOT,env=dict(os.environ,ENERGIA_DATA_DIR=str(ROOT/'data-demo')),stdout=log,stderr=log)
        try:
            for _ in range(60):
                try:
                    if urlopen(f'http://127.0.0.1:{PORT}/_stcore/health',timeout=1).status==200: break
                except Exception: time.sleep(1)
            with sync_playwright() as p:
                browser=p.chromium.launch(channel='chrome',headless=True)
                page=browser.new_page(viewport={'width':1440,'height':1050},device_scale_factor=1)
                page.goto(f'http://127.0.0.1:{PORT}')
                page.get_by_text('2. Dossiê de Investigação', exact=False).wait_for(timeout=90000)
                assert page.get_by_text('Não foi possível montar o dossiê',exact=False).count()==0
                page.get_by_text('2. Dossiê de Investigação · JUREMA',exact=False).wait_for(timeout=30000)
                page.screenshot(path=str(images/'fila-dossie.png'),full_page=True)
                page.get_by_role('tab').nth(1).click()
                page.get_by_text('Outros conjuntos da mesma distribuidora',exact=False).wait_for()
                page.screenshot(path=str(images/'contexto.png'),full_page=True)
                page.get_by_role('tab').nth(2).click()
                page.get_by_text('Classificações reportadas pela fonte',exact=False).wait_for()
                page.screenshot(path=str(images/'sinais-reportados.png'),full_page=True)
                page.get_by_role('tab').nth(3).click()
                page.get_by_text('Evidência consistente',exact=False).wait_for()
                page.screenshot(path=str(images/'confianca.png'),full_page=True)
                page.get_by_role('tab').nth(4).click()
                page.screenshot(path=str(images/'registros.png'),full_page=True)
                page.get_by_role('tab').nth(5).click()
                page.get_by_role('button',name='Gerar pacote de evidências',exact=True).click()
                download_button=page.get_by_text('Baixar pacote de evidências',exact=True)
                download_button.wait_for(timeout=90000)
                # AppTest and service tests cover the browser-download binding.  Here
                # we verify the generated on-disk package, avoiding a second browser
                # transfer that makes this smoke test needlessly slow on Windows.
                packages=sorted((ROOT/'exports').glob('dossie-*.zip'),key=lambda item:item.stat().st_mtime)
                assert packages, 'The interface did not create an evidence package'
                path=packages[-1]
                report=verify_export(path)
                page.screenshot(path=str(images/'exportacao.png'),full_page=True)
                page.get_by_role('combobox').first.click()
                page.get_by_role('option',name='2026-06',exact=True).click()
                page.wait_for_timeout(2500)
                assert page.get_by_role('button',name='Baixar pacote de evidências',exact=True).count()==0
                assert page.get_by_text('Não foi possível montar o dossiê',exact=False).count()==0
                browser.close()
                result={'browser':'Chromium / Chrome headless','checks':['rendered_dossier','real_context','confidence','source_records','zip_download','zip_recalculation','period_change_invalidates_export'],'export':report}
                (ROOT/'docs'/'VALIDACAO_NAVEGADOR.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
                print(json.dumps(result,ensure_ascii=True))
        finally:
            process.terminate()
            process.wait(timeout=20)

if __name__=='__main__': main()
