"""Public-source daily evidence. Headlines flag branches; they never establish earnings or calibrated odds."""
import io,json,hashlib,re,calendar
from datetime import datetime,timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlencode,urljoin
from urllib.request import Request,urlopen
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo
import pandas as pd
from bs4 import BeautifulSoup
from archive_deep_sources import archive,ROOT

date=datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat();now=pd.Timestamp(date)
base=ROOT/f"data/ideal_review/{date}";folder=base/"intelligence";folder.mkdir(parents=True,exist_ok=True)
config=json.loads((ROOT/"research/daily_config.json").read_text())
policy=json.loads((ROOT/f"research/ideal_policy_{date}.json").read_text())
sources=[];items=[];texts={};events=[];rates=None;availability=None

def get(url,name):
    req=Request(url,headers={"User-Agent":"Mozilla/5.0 (FundResearch public analysis)","Referer":"https://fund.eastmoney.com/"})
    with urlopen(req,timeout=25) as response:raw=response.read()
    (folder/name).write_bytes(raw)
    return raw,hashlib.sha256(raw).hexdigest()

def pubdate(value):
    try:return parsedate_to_datetime(value).astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()
    except Exception:
        try:return str(pd.Timestamp(value).date())
        except Exception:return None

def append_item(title,url,published,topic,rank,source_id,excerpt="",status="待正文核验",metrics=None):
    if not published or published>date or (now-pd.Timestamp(published)).days>21:return
    if not url.startswith(("http://","https://")):return
    items.append({"title":str(title)[:220],"url":url,"published_on":published,"topic":topic,
                  "rank":rank,"source_id":source_id,"excerpt":excerpt[:800],"status":status,"metrics":metrics or {}})

for source in config["source_feeds"]:
    source={**source,"url":source["url"].replace("{year}",date[:4])}
    row={**source,"retrieved_on":date}
    try:
        raw,h=get(source["url"],source["id"]+".raw")
        row.update(status="ok",sha256=h)
        if source["type"]=="rss":
            feed=ET.fromstring(raw)
            for entry in feed.findall(".//item")[:25]:
                if not re.search(r"monetary|FOMC|economic|inflation|rate|projection",entry.findtext("title",""),re.I):continue
                append_item(entry.findtext("title",""),entry.findtext("link",""),pubdate(entry.findtext("pubDate","")),
                            source["topic"],source["rank"],source["id"],
                            BeautifulSoup(entry.findtext("description",""),"html.parser").get_text(" ",strip=True),"官方发布摘要")
        elif source["type"]=="xml_rates":
            feed=ET.fromstring(raw);points=[]
            for properties in feed.iter():
                if properties.tag.rsplit("}",1)[-1]!="properties":continue
                fields={v.tag.rsplit("}",1)[-1]:v.text for v in properties}
                dt=fields.get("NEW_DATE");value=fields.get("TC_10YEAR")
                if dt and value and pd.Timestamp(dt).tz_localize(None)<=now:
                    points.append((pd.Timestamp(dt).tz_localize(None),float(value)))
            points.sort()
            assert len(points)>=21 and (now-points[-1][0]).days<=10
            if rates is None:rates={"date":str(points[-1][0].date()),"value_pct":points[-1][1],
                                   "change20_bp":(points[-1][1]-points[-21][1])*100,"url":source["url"]}
        elif source["type"]=="csv":
            frame=pd.read_csv(io.BytesIO(raw))
            assert "DFII10" in frame.columns
            frame.iloc[:,0]=pd.to_datetime(frame.iloc[:,0])
            frame["DFII10"]=pd.to_numeric(frame["DFII10"],errors="coerce")
            frame=frame.loc[frame.iloc[:,0]<=now].dropna()
            last=frame.iloc[-1]
            assert (now-last.iloc[0]).days<=10
            rates={"date":str(last.iloc[0].date()),"value_pct":float(last.DFII10),
                   "change20_bp":float((last.DFII10-frame.iloc[-21].DFII10)*100),
                   "url":source["url"]}
        else:
            soup=BeautifulSoup(raw,"html.parser")
            for tag in soup(["script","style","nav","footer"]):tag.decompose()
            text=soup.get_text(" ",strip=True);texts[source["id"]]=text
            (folder/(source["id"]+".txt")).write_text(text)
            if source["id"]=="sp500_availability":
                compact=re.sub(r"\s+","",text)
                availability={"code":"006075","checked_on":date,
                              "state":"paused" if "申购状态暂停申购" in compact else "needs_channel_check",
                              "source":source["url"],"note":"代销公开状态，不代表蚂蚁具体额度。"}
            # Dynamically parse future FOMC meeting endpoints by official year panels.
            if source["id"]=="fed_calendar":
                for heading in soup.find_all(re.compile("^h[234]$")):
                    match=re.search(r"(\d{4}) FOMC Meetings",heading.get_text())
                    if not match:continue
                    panel=heading.find_parent(class_="panel")
                    if not panel:continue
                    for meeting in panel.select(".fomc-meeting"):
                        month=meeting.select_one(".fomc-meeting__month");days=meeting.select_one(".fomc-meeting__date")
                        if not month or not days:continue
                        mon=month.get_text(" ",strip=True);day_nums=re.findall(r"\d+",days.get_text())
                        if mon not in list(calendar.month_name) or not day_nums:continue
                        try:
                            day=pd.Timestamp(int(match.group(1)),list(calendar.month_name).index(mon),int(day_nums[-1]))+pd.Timedelta(days=1)
                        except Exception:continue
                        if now<day<=now+pd.Timedelta(days=35):
                            events.append({"id":"fomc_"+str(day.date()),"date":str(day.date()),"name":"FOMC决议（北京时间）","topic":"rates","source":source["url"],"verified":True,
                                           "positive":"实际利率预期回落，成长与黄金压力缓解","negative":"利率预期再上行，股金可能同跌"})
            if source["id"]=="msft_ir":
                found=re.search(r"next earnings release will be on ([A-Za-z]+ \d{1,2}, \d{4})",text,re.I)
                if found:
                    day=pd.Timestamp(found.group(1))+pd.Timedelta(days=1)
                    if now<day<=now+pd.Timedelta(days=35):
                        events.append({"id":"msft_"+str(day.date()),"date":str(day.date()),"name":"微软财报（北京时间）","topic":"earnings","source":source["url"],"verified":True,
                                       "positive":"云收入、AI投入及订单兑现相互支持","negative":"投入、利润回报或指引弱于预期"})
                for a in soup.find_all("a",href=True):
                    title=a.get_text(" ",strip=True);url=urljoin(source["url"],a["href"])
                    match=re.search(r"/(20\d{2})/(\d{2})/(\d{2})/",url)
                    if match and re.search(r"earnings|results|cloud|capital",title,re.I):
                        append_item(title,url,"-".join(match.groups()),"earnings","issuer",source["id"],status="发行人标题")
        row["bytes"]=len(raw)
    except Exception as exc:row.update(status="unavailable",error=type(exc).__name__)
    sources.append(row)
    print(source["id"],row["status"],flush=True)

# Public announcement index; use exact codes, dates, document IDs. No page scripts executed.
watch=[(p["code"],p["name"],"fund") for p in policy["positions"]]+[(c,c,"company") for c in config["company_watch"]]
for code,name,kind in watch:
    source_id="announcement_"+code
    url=("https://api.fund.eastmoney.com/f10/JJGG?"+urlencode({"fundcode":code,"pageIndex":1,"pageSize":20,"type":0})) if kind=="fund" else (
        "https://np-anotice-stock.eastmoney.com/api/security/ann?"+urlencode({"sr":-1,"page_size":8,"page_index":1,"ann_type":"A","client_source":"web","stock_list":code}))
    row={"id":source_id,"name":name+"公告目录","url":url,"rank":"disclosure_index","topic":"manager" if kind=="fund" else "earnings","retrieved_on":date}
    try:
        raw,h=get(url,source_id+".json");data=json.loads(raw)
        records=data.get("Data") if kind=="fund" else data.get("data",{}).get("list")
        assert isinstance(records,list)
        row.update(status="ok",sha256=h,count=len(records))
        accepted=0
        for rec in records:
            if kind=="fund" and rec.get("FUNDCODE")!=code:continue
            title=rec.get("TITLE" if kind=="fund" else "title","")
            published=str(rec.get("PUBLISHDATE" if kind=="fund" else "notice_date",""))[:10]
            if kind=="fund" and ("提示性公告" in title or "报告提示" in title):continue
            if not re.search(r"季.*报告|中期报告|年度报告|基金经理|限.*申购|暂停.*申购|生产经营|业绩|回购|调研",title):continue
            if not published or published>date or (now-pd.Timestamp(published)).days>21:continue
            article=rec.get("ID" if kind=="fund" else "art_code","")
            if not re.fullmatch(r"AN\d+",article):continue
            pdf_url=f"https://pdf.dfcfw.com/pdf/H2_{article}_1.pdf"
            excerpt="";status="公告目录，正文未解析";metrics={}
            # Bound work: at most one relevant primary document per product per day.
            if accepted==0 or ("生产经营" in title and accepted<4):
                try:
                    archived=archive({"id":article,"url":pdf_url},folder,True)
                    pages=json.loads((folder/(article+".text.json")).read_text())
                    joined="\n".join(p["text"] or "" for p in pages)
                    if kind=="company":
                        compact=re.sub(r"\s+","",joined)
                        cash=re.search(r"经营活动产生的现金流量净额[（(]元[）)]--?--?(-?[\d,]+\.\d+)(-?[\d.]+)%",compact)
                        if cash:
                            metrics["operating_cashflow_ytd_cny"]=float(cash.group(1).replace(",",""))
                            metrics["operating_cashflow_ytd_change_pct"]=float(cash.group(2))
                    needles="4.4|投资策略|运作分析|生产经营|在手订单|订单需求|营业收入|净利润|基金经理变更"
                    excerpts=[]
                    for m in re.finditer(needles,joined):
                        excerpts.append(joined[max(0,m.start()-40):m.start()+400])
                        if len(excerpts)>=3:break
                    excerpt="\n".join(excerpts)
                    status="法定披露原文已归档；摘要不作全文判断"
                except Exception:pass
            append_item(title,pdf_url,published,row["topic"],"issuer",source_id,excerpt,status,metrics)
            accepted+=1
    except Exception as exc:row.update(status="unavailable",error=type(exc).__name__)
    sources.append(row);print(source_id,row["status"],flush=True)
for cur in config["curated_evidence"]:
    if cur["date"]<=date<=cur["expires"]:
        try:
            raw,h=get(cur["url"],cur["id"]+".html")
            body=BeautifulSoup(raw,"html.parser").get_text(" ",strip=True)
            assert len(body)>400
            sources.append({**cur,"status":"ok","sha256":h,"retrieved_on":date})
            append_item(cur["title"],cur["url"],cur["date"],cur["topic"],cur["rank"],cur["id"],cur["reading"],"人工核验解读，原文日期固定")
        except Exception as exc:
            sources.append({**cur,"status":"unavailable","error":type(exc).__name__})
# Known dates are valid only when the live official page still confirms the marker.
for event in config["events"]:
    if now<pd.Timestamp(event["date"])<=now+pd.Timedelta(days=35) and event["verify_text"] in texts.get(event["source_id"],""):
        if not any(e["topic"]==event["topic"] and e["date"]==event["date"] for e in events):
            events.append({**event,"verified":True})
unique={}
for item in items:unique.setdefault(item["url"],item)
items=sorted(unique.values(),key=lambda r:(r["published_on"],r["rank"]),reverse=True)
success=sum(r["status"]=="ok" for r in sources)
if success<3:raise RuntimeError("Insufficient live intelligence coverage; preserve previous published report.")
result={"date":date,"collected_at":datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),"items":items,"availability":availability,
        "events":sorted(events,key=lambda e:e["date"]),"rates":rates,"sources":sources,
        "coverage":{"ok":success,"total":len(sources),"status":"complete" if success==len(sources) else "partial"},
        "rules":"官方日历与披露正文优先；媒体回应和公告标题不自动构成盈利已验证，不由情绪关键词生成概率。已过期事件自动移出前瞻日历，未核实的新日期不编造。"}
(base/"intelligence.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
print("Evidence",len(items),"events",len(events),"coverage",success,len(sources))
