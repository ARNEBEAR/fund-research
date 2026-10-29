"""Portable local/CI browser checks, including default latest and historic date switching."""
import argparse,json,hashlib,os,threading
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
PUBLIC=Path(os.environ.get("RESEARCH_PUBLIC_ROOT",ROOT/"publish/github-pages")).resolve()
parser=argparse.ArgumentParser();parser.add_argument("--url");args=parser.parse_args()
registry=json.loads((PUBLIC/"reports/index.json").read_text());latest=registry[0]["date"]
report=PUBLIC/registry[0]["path"]
for r in registry:
    d=PUBLIC/r["path"];manifest=json.loads((d/"manifest.json").read_text())
    for filename,h in manifest["files"].items():assert hashlib.sha256((d/filename).read_bytes()).hexdigest()==h
if not args.url:
    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(("127.0.0.1",0),partial(Quiet,directory=str(PUBLIC)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    url=f"http://127.0.0.1:{server.server_address[1]}/"
else:url=args.url.rstrip("/")+"/"
errors=[];screens=ROOT/"report/daily-check";screens.mkdir(parents=True,exist_ok=True)
with sync_playwright() as pw:
    launch={"headless":True}
    if os.environ.get("CHROMIUM_EXECUTABLE"):launch["executable_path"]=os.environ["CHROMIUM_EXECUTABLE"]
    browser=pw.chromium.launch(**launch)
    for width in [1440,390]:
        page=browser.new_page(viewport={"width":width,"height":950 if width==1440 else 844})
        page.on("pageerror",lambda e:errors.append(str(e)))
        page.goto(url,wait_until="networkidle")
        page.wait_for_function("window.PORTFOLIO_READY && window.DATE_PICKER_READY")
        assert "/reports/"+latest+"/" in page.url
        assert page.locator("#date-picker").input_value()==latest
        for value in ["bull","bear","rates","base"]:
            page.select_option("#forward-branch",value)
            assert "20日收益中位数" in page.locator("#forward-path-note").inner_text()
        assert page.locator("#robust-rows tr").count()==5
        assert page.locator("#tail-rows tr").count()==4
        assert not page.locator("#diagnostics").get_attribute("open")
        for selector in ["#overview","#forward","#daily-evidence"]:
            page.locator(selector).scroll_into_view_if_needed();page.screenshot(path=str(screens/f"{selector[1:]}-{width}.png"))
        page.locator("#diagnostics > summary").click()
        assert page.locator("#target-rows tr").count()==10
        for value in ["52","104","26"]:page.select_option("#gold-window",value)
        for value in ["no_gold","gold_6%","gold_20%","eight_role_merge","target"]:page.select_option("#scenario-plan",value)
        for value in ["mdd","return","vol"]:page.select_option("#plan-metric",value)
        assert page.evaluate("document.documentElement.scrollWidth<=innerWidth+1")
        with page.expect_download() as download:page.locator('[data-save="forward-chart"]').click()
        path=screens/f"export-{width}.png";download.value.save_as(str(path))
        assert path.read_bytes().startswith(b"\x89PNG")
        if len(registry)>1:
            previous=registry[1]["date"];page.select_option("#date-picker",previous)
            page.wait_for_url("**/reports/"+previous+"/")
            page.goto(url,wait_until="networkidle")
            page.wait_for_function("window.DATE_PICKER_READY")
        quarterly=page.locator("#quarter-review a")
        if quarterly.count():
            quarterly.click()
            page.wait_for_function("window.QUARTER_REVIEW_READY")
            assert page.locator(".fund-review").count()==10
            for code in ["021180","010390","011370","519697","021902"]:
                page.select_option("#behavior-fund",code)
                assert page.locator("#behavior-fund").input_value()==code
            page.locator("#fund-011370 summary").click()
            assert "张明昕" in page.locator("#fund-011370").inner_text()
            assert not page.locator("#fund-011370").evaluate("(e)=>e.innerText.includes('周海栋')")
            assert page.locator("canvas").count()==2
            assert page.evaluate("document.documentElement.scrollWidth<=innerWidth+1")
            page.screenshot(path=str(screens/f"quarterly-{width}.png"))
        page.goto(url+"?date=2026-10-20",wait_until="networkidle")
        assert "/reports/2026-10-20/" in page.url
        page.goto(url+"#fund-explorer",wait_until="domcontentloaded")
        page.wait_for_url("**/research-2026-09-20.html#fund-explorer")
        page.close()
    browser.close()
if not args.url:server.shutdown()
assert not errors,errors
print(json.dumps({"passed":True,"latest":latest,"checks":["默认最新","日期切换","前瞻分支/配置交互","手机桌面无溢出","PNG导出","旧报告哈希与旧锚点"],"errors":errors},ensure_ascii=False))
