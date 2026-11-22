"""Collect daily public evidence, never regenerate the frozen investment judgment.

CLI: --public-root CHECKOUT [--date YYYY-MM-DD] [--report-root DIRECTORY].
Reports: REPORT_ROOT/daily/{latest.json,dates/DATE/audit.{json,html},evidence}.
Only a fully successful, validated same-day collection is reusable. A partial run
exits 2 after publishing its evidence, so the 09:20 retry can run the full query.
Importable helpers do no network or filesystem work at import time.
"""

import argparse
import csv
import hashlib
import html
import io
import json
import math
import os
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup


BEIJING = ZoneInfo("Asia/Shanghai")
SITE_PATH = Path("proposals/2026-11-21/asymmetry")
REVIEW_MODE = "scheduled evidence collection and rule checks; no fresh AI or human review"
LAST_REVIEW = "2026-11-21"
SECTION_IDS = (
    "verdict", "doc100", "audit", "market", "blind", "managers", "portfolio",
    "scenarios", "replay", "execution", "sources",
)
SCHEMA_VERSION = "asymmetry-daily-evidence/1"
MAX_BYTES = 4 * 1024 * 1024
DATE_PATTERN = re.compile(r"(20\d{2})[-./年](\d{1,2})[-./月](\d{1,2})日?")
COMPACT_DATE = re.compile(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)")
ENGLISH_DATE = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+\d{1,2},?\s+20\d{2}\b", re.I
)


def today():
    return datetime.now(BEIJING).date().isoformat()


def timestamp():
    return datetime.now(BEIJING).isoformat()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def strict_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Expected YYYY-MM-DD")
    date.fromisoformat(value)
    return value


def observed_dates(text):
    result = set()
    for pattern in (DATE_PATTERN, COMPACT_DATE):
        for match in pattern.finditer(text):
            try:
                result.add(date(*map(int, match.groups())).isoformat())
            except ValueError:
                pass
    for match in ENGLISH_DATE.finditer(text):
        try:
            result.add(datetime.strptime(
                match.group().replace(",", ""), "%B %d %Y"
            ).date().isoformat())
        except ValueError:
            pass
    return sorted(result)


def public_url(url):
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("Not a public HTTP source")
    if parts.username or parts.password:
        raise ValueError("Credentials are not accepted in source URLs")
    if parts.hostname in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("Local source URLs are not accepted")
    if any(re.search(r"token|secret|password|authorization|api.?key", key, re.I)
           for key in parse_qs(parts.query)):
        raise ValueError("Credential-like URL query is not publishable")
    return urlunsplit(parts._replace(fragment=""))


def json_load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_bytes(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=str(path.parent), prefix=".audit-", delete=False) as f:
        name = f.name
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    os.replace(name, str(path))


def atomic_json(path, value):
    atomic_bytes(path, json.dumps(
        value, ensure_ascii=False, indent=2, allow_nan=False
    ).encode("utf-8"))


def positive_number(value):
    if isinstance(value, bool):
        raise ValueError("Boolean is not a NAV")
    try:
        number = float(value)
    except (ValueError, TypeError):
        raise ValueError("Missing or invalid NAV")
    if not math.isfinite(number) or number <= 0:
        raise ValueError("Nonpositive or nonfinite NAV")
    return number


def api_records(raw, kind):
    body = json.loads(raw)
    if body.get("ErrCode") not in (0, "0"):
        raise ValueError("Eastmoney API did not report success")
    data = body.get("Data")
    rows = data.get("LSJZList") if kind == "nav" and isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError("Observed API schema missing record list")
    return body, rows


def parse_nav(raw, code, asof):
    body, rows = api_records(raw, "nav")
    if not rows:
        raise ValueError("Empty NAV list")
    dates = set()
    points = []
    for row in rows:
        day = strict_date(row.get("FSRQ"))
        if day > asof:
            raise ValueError("Future NAV observation")
        if day in dates:
            raise ValueError("Duplicate NAV observation")
        dates.add(day)
        unit = positive_number(row.get("DWJZ"))
        cumulative = row.get("LJJZ")
        cumulative = None if cumulative in (None, "", "--") else positive_number(cumulative)
        points.append({
            "date": day, "unit_nav": unit, "cumulative_nav": cumulative,
            "subscription_status": row.get("SGZT") or None,
            "redemption_status": row.get("SHZT") or None,
            "distribution_note": row.get("FHSP") or row.get("FHFCZ") or None,
        })
    points.sort(key=lambda p: p["date"], reverse=True)
    return {
        "code": code, **points[0], "observations": len(points),
        "api_total_count": body.get("TotalCount"),
        "return_method": "none; unit NAV observation only, no dividend fill or forecast",
        "identity_basis": "exact fundCode request; response schema has no code field",
        "fact_reverified": False,
    }


def parse_manager(raw, code, asof):
    soup = BeautifulSoup(raw, "html.parser")
    if not re.search(r"\b" + re.escape(code) + r"\b", soup.get_text(" ", strip=True)):
        raise ValueError("Appointment page does not identify requested code")
    table = None
    for candidate in soup.find_all("table"):
        text = candidate.get_text(" ", strip=True)
        if all(marker in text for marker in ("起始期", "截止期", "基金经理")):
            table = candidate
            break
    if table is None:
        raise ValueError("Observed appointment table not found")
    appointments = []
    future_count = 0
    for tr in table.find_all("tr"):
        cells = tr.find_all("td", recursive=False)
        if len(cells) < 3:
            continue
        start = cells[0].get_text(" ", strip=True)
        end = cells[1].get_text(" ", strip=True)
        start = strict_date(start)
        end_date = None if end == "至今" else strict_date(end)
        if end_date and end_date < start:
            raise ValueError("Invalid appointment interval")
        if start > asof:
            future_count += 1
            continue
        names = [a.get_text(" ", strip=True) for a in cells[2].find_all("a")
                 if a.get_text(" ", strip=True)]
        if not names:
            raise ValueError("Missing manager identity links")
        appointments.append({
            "start_date": start, "end_date": end_date if end_date and end_date <= asof else None,
            "managers": sorted(set(names)), "end_marker": end,
        })
    current = [r for r in appointments if r["end_marker"] == "至今"]
    if not current:
        raise ValueError("No explicitly current appointment row")
    signature = digest(json.dumps(current, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    return {
        "appointments": appointments, "current_appointments": current,
        "current_managers": sorted({name for row in current for name in row["managers"]}),
        "appointment_signature": signature, "excluded_future_count": future_count,
        "fact_reverified": False,
    }


def parse_announcements(raw, code, asof):
    body, rows = api_records(raw, "announcements")
    if not rows:
        raise ValueError("Empty disclosure query, not evidence of no new disclosures")
    items = []
    future_count = 0
    ids = set()
    for row in rows:
        if row.get("FUNDCODE") != code:
            raise ValueError("Disclosure query product code mismatch")
        title = row.get("TITLE")
        article = row.get("ID")
        if not isinstance(title, str) or not re.fullmatch(r"AN\d+", article or ""):
            raise ValueError("Disclosure identity schema mismatch")
        day = strict_date(str(row.get("PUBLISHDATE", ""))[:10])
        if day > asof:
            future_count += 1
            continue
        if article in ids:
            raise ValueError("Duplicate disclosure ID")
        ids.add(article)
        if not re.search(r"季.*报告|年度报告|中期报告|基金经理", title):
            continue
        kind = "manager" if "基金经理" in title else "periodic_report"
        items.append({
            "id": article, "title": title[:300], "publication_date": day, "kind": kind,
            "url": "https://fund.eastmoney.com/gonggao/" + code + "," + article + ".html",
            "body_reviewed": False, "requires_independent_review": True,
            "new_since_independent_review": day > LAST_REVIEW,
        })
    return {
        "items": items, "records_returned": len(rows), "api_total_count": body.get("TotalCount"),
        "window": "first 20 announcements only; older or omitted pages are not reviewed",
        "excluded_future_count": future_count, "fact_reverified": False,
    }


def parse_index(raw, url, asof, kind="html"):
    if kind == "rss":
        tree = ET.fromstring(raw)
        candidates = []
        future_count = 0
        for item in tree.findall(".//item"):
            value = item.findtext("pubDate")
            try:
                day = parsedate_to_datetime(value).date().isoformat()
            except (ValueError, TypeError, AttributeError):
                continue
            if day > asof:
                future_count += 1
                continue
            candidates.append({
                "title": (item.findtext("title") or "")[:300],
                "url": public_url(urljoin(url, item.findtext("link") or "")),
                "publication_date": day, "date_basis": "RSS pubDate",
            })
        candidates.sort(key=lambda p: p["publication_date"], reverse=True)
        return {
            "date_candidates": candidates[:30],
            "publication_date": candidates[0]["publication_date"] if candidates else None,
            "excerpt": " | ".join(p["title"] for p in candidates[:6])[:1200],
            "excerpt_scope": "fresh official feed titles, not full linked articles",
            "excluded_future_count": future_count,
        }
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    candidates = []
    undated = []
    seen = set()
    future_count = 0
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        title = anchor.get_text(" ", strip=True)
        if not title or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        try:
            target = public_url(urljoin(url, href))
        except ValueError:
            continue
        if target in seen:
            continue
        seen.add(target)
        dates = observed_dates(title + " " + href)
        basis = "link title or URL"
        if not dates:
            container = anchor.find_parent(["li", "tr", "p"])
            nearby = container.get_text(" ", strip=True) if container else ""
            if nearby and len(nearby) <= 700:
                dates = observed_dates(nearby)
                basis = "bounded link row text"
        if not dates:
            if len(undated) < 15:
                undated.append({"title": title[:200], "url": target, "publication_date": None})
            continue
        valid = [d for d in dates if d <= asof]
        future_count += sum(d > asof for d in dates)
        if valid:
            candidates.append({
                "title": title[:300], "url": target,
                "publication_date": max(valid), "date_basis": basis,
            })
    candidates.sort(key=lambda p: p["publication_date"], reverse=True)
    visible = soup.get_text(" ", strip=True)
    if len(visible) < 150 or re.search(
            r"访问验证|安全验证|请完成验证|Access Denied|Just a moment|captcha", visible, re.I):
        raise ValueError("Short, empty, or access-challenge index")
    return {
        "date_candidates": candidates[:30], "undated_links": undated,
        "publication_date": candidates[0]["publication_date"] if candidates else None,
        "excerpt": visible[:1200],
        "excerpt_scope": "freshly retrieved index visible text only; linked bodies not reviewed",
        "excluded_future_count": future_count,
    }


def parse_release(raw, url, asof):
    result = parse_index(raw, url, asof)
    soup = BeautifulSoup(raw, "html.parser")
    dates = []
    for meta in soup.find_all("meta"):
        key = meta.get("name", meta.get("property", "")).lower()
        if key in ("pubdate", "publishdate", "articlecreationdate", "date",
                   "article:published_time", "dc.date"):
            dates.extend(observed_dates(meta.get("content", "")))
    if not dates:
        visible = soup.get_text(" ", strip=True)
        for match in re.finditer(r"(?:发布日期|发布时间|发布时间|日期|时间)\s*[:：]?\s*(.{0,35})", visible):
            dates.extend(observed_dates(match.group(1)))
    result["publication_date"] = max((d for d in dates if d <= asof), default=None)
    result["excerpt_scope"] = "current release visible text; publication date only if observed"
    return result


def parse_rate(raw, asof, kind):
    points = []
    if kind == "csv":
        for row in csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))):
            day = row.get("observation_date") or row.get("DATE")
            value = row.get("DFII10")
            if day and day <= asof and value not in (None, "", "."):
                number = float(value)
                if math.isfinite(number):
                    points.append((strict_date(day), number))
    else:
        tree = ET.fromstring(raw)
        for node in tree.iter():
            if node.tag.rsplit("}", 1)[-1] != "properties":
                continue
            fields = {child.tag.rsplit("}", 1)[-1]: child.text for child in node}
            day, value = fields.get("NEW_DATE"), fields.get("TC_10YEAR")
            if day and day[:10] <= asof and value not in (None, ""):
                number = float(value)
                if math.isfinite(number):
                    points.append((strict_date(day[:10]), number))
    if not points:
        raise ValueError("No observed real-yield records")
    day, value = max(points)
    if (date.fromisoformat(asof) - date.fromisoformat(day)).days > 10:
        raise ValueError("Real-yield series is stale beyond 10 calendar days")
    return {
        "publication_date": day, "date_candidates": [],
        "observation": {"date": day, "value_pct": value},
        "excerpt": "Observed 10-year real yield: %s, %s%%. No forecast." % (day, value),
        "excerpt_scope": "latest structured observation; not an article",
    }


def snapshot(check):
    keys = (
        "id", "checked_at", "publication_date", "content_sha256", "status",
        "nav", "manager", "announcements", "observation", "date_candidates", "excerpt",
    )
    return {k: check[k] for k in keys if k in check}


def fetch_check(job, asof, timeout=18, opener=urlopen):
    result = {
        **job, "status": "failed", "checked_at": timestamp(), "publication_date": None,
        "date_candidates": [], "content_sha256": None, "excerpt": "",
        "http_status": None, "error": None, "fact_reverified": False,
        "requires_independent_review": True, "last_success": None, "stale": True,
    }
    try:
        url = public_url(job["url"])
        req = Request(url, headers={
            "User-Agent": "Mozilla/5.0 (PublicEvidenceAudit/1.0)",
            "Referer": "https://fundf10.eastmoney.com/" if "eastmoney.com" in url else url,
            "Cache-Control": "no-cache",
        })
        with opener(req, timeout=timeout) as response:
            result["http_status"] = response.status
            raw = response.read(MAX_BYTES + 1)
            final_url = public_url(response.url)
            encoding = response.headers.get_content_charset()
        result.update(content_sha256=digest(raw), bytes=len(raw), final_url=final_url)
        if len(raw) > MAX_BYTES:
            raise ValueError("Response exceeded bounded evidence size")
        if result["http_status"] != 200:
            raise ValueError("Non-200 source response")
        kind = job["kind"]
        if kind == "nav":
            result["nav"] = parse_nav(raw, job["code"], asof)
            result["publication_date"] = result["nav"]["date"]
            result["excerpt"] = "%s unit NAV %s on %s" % (
                job["code"], result["nav"]["unit_nav"], result["publication_date"])
        elif kind == "manager":
            result["manager"] = parse_manager(raw, job["code"], asof)
            result["publication_date"] = max(
                row["start_date"] for row in result["manager"]["current_appointments"])
        elif kind == "announcements":
            result["announcements"] = parse_announcements(raw, job["code"], asof)
            items = result["announcements"]["items"]
            result["date_candidates"] = [
                {k: item[k] for k in ("title", "url", "publication_date")} for item in items]
            result["publication_date"] = max(
                (p["publication_date"] for p in items), default=None)
        elif kind in ("csv", "xml_rates"):
            result.update(parse_rate(raw, asof, kind))
        else:
            if kind in ("html", "current_release"):
                charset = re.search(rb"charset\s*=\s*[\"']?([\w-]+)", raw[:6000], re.I)
                encoding = encoding or (charset.group(1).decode() if charset else "utf-8")
                raw = raw.decode(encoding, errors="replace")
            result.update(parse_release(raw, final_url, asof) if kind == "current_release"
                          else parse_index(raw, final_url, asof, kind))
        result.update(status="collected", stale=False)
        result["last_success"] = snapshot(result)
    except Exception as exc:
        # Exceptions can contain request credentials. Publish only controlled messages.
        if isinstance(exc, HTTPError):
            result["http_status"] = exc.code
        result["error"] = (
            str(exc)[:200] if isinstance(exc, ValueError) else type(exc).__name__)
    return result


def official_jobs(data, intel, asof, priority=None):
    sources = data["sources"]

    def source(source_id):
        return next(s for s in sources if s["id"] == source_id)["url"]

    def index_from(source_id):
        parts = urlsplit(source(source_id))
        # Registry URL ancestors, not invented current article endpoints.
        if source_id == "S10":
            path = parts.path.split("/2026")[0] + "/"
        elif source_id == "S11":
            path = parts.path.split("/2026")[0] + "/"
        elif source_id == "D104":
            path = parts.path.rsplit("/", 2)[0] + "/index.html"
        elif source_id == "S08":
            path = parts.path.split("/c/")[0] + "/"
        else:
            path = "/"
        return urlunsplit((parts.scheme, parts.netloc, path, "", ""))

    jobs = [
        ("mof_latest", "MOF latest treasury statistics", "https://gks.mof.gov.cn/tongjishuju/",
         "html", "mof"),
        ("mof_current", "MOF current fiscal release",
         "https://gks.mof.gov.cn/tongjishuju/202611/t20261119_4004986.htm",
         "current_release", "mof"),
        ("nbs_latest", "NBS latest releases", index_from("S10"), "html", "nbs"),
        ("nbs_interpretation", "NBS latest interpretations", index_from("S11"), "html", "nbs"),
        ("nbs_calendar", "NBS official publication calendar", source("S13"), "html", "nbs"),
        ("pboc_latest", "PBOC latest news and statistics", index_from("D104"), "html", "pboc"),
        ("sse_latest", "SSE latest market conference index", index_from("S08"), "html", "sse"),
        ("fed_calendar", "FOMC official calendar", source("S22"), "html", "fed"),
    ]
    allowed = {"fed_press", "msft_ir", "real_yield", "treasury_real"}
    for row in intel.get("sources", []):
        if row.get("id") in allowed:
            jobs.append((row["id"], row.get("name", row["id"]),
                         row["url"].replace("{year}", asof[:4]),
                         row.get("type", "html"), "fed" if row["id"] == "fed_press" else
                         "rates" if row["id"] in ("real_yield", "treasury_real") else "msft"))
            allowed.remove(row["id"])
    jobs.extend([
        ("nvidia_ir", "NVIDIA official IR root discovery", index_from("S06"), "html", "nvidia"),
        ("wuxi_ir", "WuXi official investor relations", "https://www.wuxiapptec.cn/investors",
         "html", "wuxi"),
    ])
    result = [{
        "id": ident, "name": name, "url": public_url(url), "kind": kind,
        "family": family, "group": "macro_market",
        "scope": "current index or series; linked release bodies are not collected",
    } for ident, name, url, kind, family in jobs]
    priority = priority or []
    if isinstance(priority, dict):
        priority = [dict(row, id=ident) if isinstance(row, dict) else {"id": ident, "url": row}
                    for ident, row in priority.items()]
    configured = []
    by_id = {row["id"]: row for row in result}
    for row in priority:
        if isinstance(row, str):
            if row in by_id:
                configured.append(by_id.pop(row))
                continue
            matched = next((r for r in by_id.values() if r["url"] == row), None)
            if matched:
                configured.append(by_id.pop(matched["id"]))
                continue
            row = {"url": row}
        if not isinstance(row, dict) or not row.get("url"):
            continue
        ident = row.get("id", "priority_" + digest(row["url"].encode("utf-8"))[:12])
        if not re.fullmatch(r"[A-Za-z0-9_-]+", ident):
            raise ValueError("Unsafe priority source ID")
        old = by_id.pop(ident, {})
        configured.append({
            **old, "id": ident, "name": row.get("name", row.get("title", ident)),
            "url": public_url(row["url"]), "kind": row.get("type", row.get("kind", "html")),
            "family": row.get("family", old.get("family", "priority")),
            "group": "macro_market", "scope": "configured current public source",
        })
    urls = set()
    unique = []
    for row in configured + list(by_id.values()):
        if row["url"] not in urls:
            unique.append(row)
            urls.add(row["url"])
    return unique


def build_jobs(data, intel, asof, priority=None):
    official = official_jobs(data, intel, asof, priority)
    # Reserve the full fund/manager query set before lower-priority extra indexes.
    jobs = official[:15]
    funds = sorted(data["names"])
    etfs = sorted({c for c in data["benchmark_codes"] if c not in funds})
    extras={r["code"]:r for r in data.get("extra_watch_codes",[]) if re.fullmatch(r"\d{6}",str(r.get("code","")))}
    etfs=sorted(set(etfs)|{c for c in extras if c not in funds})
    if len(etfs) < 6:
        raise ValueError("Six observed benchmark ETF codes required")
    for code in funds + etfs:
        jobs.append({
            "id": "nav_" + code, "name": data["names"].get(code, extras.get(code,{}).get("name","ETF " + code)),
            "url": "https://api.fund.eastmoney.com/f10/lsjz?" + urlencode({
                "fundCode": code, "pageIndex": 1, "pageSize": 5, "endDate": asof,
            }), "kind": "nav", "group": "nav", "family": "eastmoney_nav",
            "code": code, "product_kind": "fund" if code in funds else extras.get(code,{}).get("product_kind","etf"),
        })
    for card in data["managerCards"]:
        code = card["code"]
        jobs.extend([
            {"id": "manager_" + code, "name": card["manager"] + " appointment",
             "url": "https://fundf10.eastmoney.com/jjjl_" + code + ".html",
             "kind": "manager", "group": "manager", "family": "manager_" + code, "code": code},
            {"id": "announcements_" + code, "name": card["name"] + " disclosures",
             "url": "https://api.fund.eastmoney.com/f10/JJGG?" + urlencode({
                 "fundcode": code, "pageIndex": 1, "pageSize": 20, "type": 0,
             }), "kind": "announcements", "group": "announcements",
             "family": "manager_" + code, "code": code},
        ])
    return jobs + official[15:]


def source_family(source, data):
    url = source["url"]
    for card in data["managerCards"]:
        if url == card["source"]:
            return "manager_" + card["code"]
    host = urlsplit(url).hostname or ""
    for token, family in (
        ("stats.gov.cn", "nbs"), ("scio.gov.cn", "nbs"),
        ("pbc.gov.cn", "pboc"), ("sse.com.cn", "sse"), ("federalreserve.gov", "fed"),
        ("nvidia.com", "nvidia"), ("wuxiapptec.cn", "wuxi"),
        ("mof.gov.cn", "mof"),
    ):
        if host == token or host.endswith("." + token):
            return family
    if source["id"] == "S23":
        return "eastmoney_nav"
    if source["id"] in ("S04", "S05"):
        return "manager_" + ("010390" if source["id"] == "S04" else "027170")
    return None


def build_ledgers(data, site, checks, previous, asof, baseline, changed):
    by_id = {c["id"]: c for c in checks}
    families = {}
    for check in checks:
        if check["status"] == "collected":
            families.setdefault(check["family"], []).append(check["id"])
    history = []
    for source in data["sources"]:
        family = source_family(source, data)
        related = families.get(family, [])
        history.append({
            "id": source["id"], "title": source["title"], "url": source["url"],
            "source_date_label": source.get("date"), "family": family,
            "status": "historical; related family collected" if related else "needs_research",
            "related_fresh_check_ids": related, "historical": True,
            "original_source_fetched_today": False, "fact_reverified": False,
            "requires_independent_review": True,
            "limitation": "Family evidence is not a recheck of this original source or its claim.",
        })
    hist = {row["id"]: row for row in history}
    claims = []
    for claim in data["doc100"]["claims"]:
        related = sorted({item for source_id in claim["source_ids"]
                          for item in hist.get(source_id, {}).get("related_fresh_check_ids", [])})
        claims.append({
            "id": claim["id"], "title": claim["title"], "source_ids": claim["source_ids"],
            "historical_status": claim["status"], "status": "needs independent review",
            "evidence_status": "related evidence collected" if related else "needs_research",
            "related_fresh_check_ids": related, "last_independent_review": baseline,
            "verified_on": None, "historical": True, "fact_reverified": False,
            "requires_independent_review": True,
        })
    prior_managers = {r["code"]: r for r in (previous or {}).get("managerLedger", [])}
    managers = []
    for card in data["managerCards"]:
        code = card["code"]
        appointment = by_id["manager_" + code]
        disclosure = by_id["announcements_" + code]
        live = appointment.get("manager", {})
        prior = prior_managers.get(code, {})
        changed_appointment = (
            live.get("appointment_signature") != prior.get("appointment_signature")
            if prior.get("appointment_signature") and live else None)
        names_changed = live.get("current_managers") != [card["manager"]] if live else None
        recent = [
            r for r in live.get("current_appointments", [])
            if (date.fromisoformat(asof) - date.fromisoformat(r["start_date"])).days < 365
        ]
        items = disclosure.get("announcements", {}).get("items", [])
        for item in items:
            item["new_since_independent_review"] = (
                item["publication_date"] > baseline if baseline else None)
        prior_ids = set(prior.get("disclosure_ids", []))
        new_items = [r for r in items if r["id"] not in prior_ids]
        managers.append({
            "code": code, "name": card["manager"], "fund_name": card["name"],
            "status": "needs independent review", "last_independent_review": baseline,
            "independent_review_complete": False, "is_new_manager": bool(recent) if live else None,
            "new_manager_or_appointment": names_changed,
            "appointment_changed_since_previous_collection": changed_appointment,
            "appointment_signature": live.get("appointment_signature"),
            "current_managers": live.get("current_managers"),
            "current_appointments": live.get("current_appointments", []),
            "source_checks": [appointment["id"], disclosure["id"]],
            "evidence_status": "collected" if all(
                c["status"] == "collected" for c in (appointment, disclosure)) else "partial",
            "disclosure_ids": [r["id"] for r in items], "disclosures": items,
            "new_disclosure_ids": [r["id"] for r in new_items],
            "new_disclosure_basis": "previous collection" if prior else "first observation; not proven new",
            "requires_independent_review": True, "fact_reverified": False,
            "limitation": "Short tenure (<365 days) is a rule flag, not a skill rating. "
                          "Appointment and disclosure titles do not complete a manager review.",
        })
    soup = BeautifulSoup(site, "html.parser")
    section_map = {s.get("id"): s for s in soup.find_all("section", id=True)}
    sections = []
    for ident in list(section_map) + [s for s in SECTION_IDS if s not in section_map]:
        section = section_map.get(ident)
        heading = section.find("h2") if section else None
        related = [c["id"] for c in checks if
                   (ident in ("market", "current", "verdict", "doc100") and c["group"] == "macro_market") or
                   (ident in ("managers", "blind") and c["group"] in ("nav", "manager", "announcements"))]
        sections.append({
            "id": ident, "title": heading.get_text(" ", strip=True) if heading else ident,
            "present": section is not None, "status": "needs independent review",
            "content_sha256": digest(str(section).encode("utf-8")) if section else None,
            "last_independent_review": baseline, "verified_on": None,
            "related_fresh_check_ids": related, "requires_independent_review": True,
            "fact_reverified": False,
            "limitation": (
                "Historical scenarios/OLS are not forecasts; no odds or cash recommendation generated."
                if ident in ("scenarios", "replay", "portfolio") else
                "Content preserved in ledger, not semantically reverified by HTTP or rules."),
        })
    return sections, claims, managers, history


def assemble(data, site, checks, previous, asof, fingerprints, intel_date, manual_date=LAST_REVIEW):
    baseline = manual_date if asof >= manual_date else None
    old_checks = {c["id"]: c for c in (previous or {}).get("sourceChecks", [])}
    changes = []
    old_fingerprints = (previous or {}).get("input_fingerprints", {})
    for key, value in fingerprints.items():
        if old_fingerprints.get(key) != value:
            changes.append({
                "kind": key, "status": "needs independent review",
                "change": "changed" if key in old_fingerprints else "first observation",
                "requires_independent_review": True,
            })
    for check in checks:
        prior = old_checks.get(check["id"], {})
        if check["status"] != "collected":
            check["last_success"] = prior.get("last_success") or (
                snapshot(prior) if prior.get("status") == "collected" else None)
        changed = bool(prior.get("content_sha256") and check["content_sha256"]
                       and prior["content_sha256"] != check["content_sha256"])
        check["change_status"] = "changed" if changed else (
            "unchanged bytes; not reverified" if prior.get("content_sha256")
            and check["status"] == "collected" else "first observation or unavailable")
        if changed:
            changes.append({"kind": "source", "id": check["id"],
                            "status": "needs independent review", "requires_independent_review": True})
    sections, claims, managers, history = build_ledgers(
        data, site, checks, previous, asof, baseline, changes)
    nav = []
    for check in checks:
        if check["kind"] != "nav":
            continue
        observation = check.get("nav")
        age = (date.fromisoformat(asof) - date.fromisoformat(
            observation["date"])).days if observation else None
        stale = observation is None or age > 7
        if observation and age > 7:
            check["status"] = "failed"
            check["error"] = "NAV observation stale beyond 7 calendar days"
            check["stale"] = True
            prior = old_checks.get(check["id"], {})
            check["last_success"] = prior.get("last_success")
        nav.append({
            "code": check["code"], "name": check["name"], "product_kind": check["product_kind"],
            "status": "collected" if check["status"] == "collected" else "failed",
            "date": observation["date"] if observation else None,
            "unit_nav": observation["unit_nav"] if observation else None,
            "cumulative_nav": observation["cumulative_nav"] if observation else None,
            "age_calendar_days": age, "stale": stale, "error": check["error"],
            "checked_at": check["checked_at"],
            "verified_on": check["checked_at"][:10] if check["status"] == "collected" else None,
            "source_url": check["url"], "source_check_id": check["id"],
            "last_success": check["last_success"], "fact_reverified": False,
            "return_method": "none; latest unit NAV only",
        })
    groups = {}
    for group in ("macro_market", "nav", "manager", "announcements"):
        rows = [c for c in checks if c["group"] == group]
        success = sum(c["status"] == "collected" for c in rows)
        groups[group] = {"attempted": len(rows), "success": success, "failed": len(rows) - success}
    success = sum(c["status"] == "collected" for c in checks)
    failures = [{"id": c["id"], "status": c["status"], "error": c["error"],
                 "http_status": c["http_status"]} for c in checks if c["status"] != "collected"]
    complete = not failures
    prior_success = (previous or {}).get("last_success")
    if (previous or {}).get("status") == "success":
        prior_success = {"asof": previous["asof"], "checked_at": previous["checked_at"],
                         "dated_report": "dates/" + previous["asof"] + "/audit.json"}
    now = timestamp()
    return {
        "schema_version": SCHEMA_VERSION, "asof": asof, "checked_at": now,
        "verified_on": now[:10], "source_dates": sorted({
            c["publication_date"] for c in checks if c["publication_date"]}),
        "status": "success" if complete else "partial", "stale": not complete,
        "last_success": {"asof": asof, "checked_at": now,
                         "dated_report": "dates/" + asof + "/audit.json"} if complete else prior_success,
        "review_mode": REVIEW_MODE, "last_independent_review": baseline,
        "last_independent_review_basis": "manual policy date (fallback 2026-11-21); "
                                         "never advanced by scheduled collection",
        "requires_independent_review": True, "independent_review_complete": False,
        "input_fingerprints": fingerprints, "intel_schema_reference_date": intel_date,
        "original_report": "../../../index.html",
        "navLatest": nav, "sourceChecks": checks, "sectionLedger": sections,
        "claimLedger": claims, "managerLedger": managers, "historicSourceLedger": history,
        "coverage": {
            "attempted": len(checks), "success": success, "failed": len(failures),
            "groups": groups, "sections": len(sections), "claims": len(claims),
            "managers": len(managers), "funds": len(data["names"]),
            "etfs": sum(r["product_kind"] == "etf" for r in nav),
            "registered_sources": len(history), "semantic_reviews_today": 0,
        },
        "changes": changes, "failures": failures, "errors": failures,
        "limitations": [
            "Scheduled evidence collection is not a fresh AI or human independent judgment.",
            "HTTP 200, content hashes, API records and titles do not reverify investment facts.",
            "All 65 registry sources remain in the ledger; related-family collection is not "
            "a current fetch or semantic review of historic originals.",
            "Current index excerpts are bounded to 1200 characters. Linked disclosure bodies, "
            "full pagination, market prices, private accounts and channel availability are unknown.",
            "No scenario probabilities, forward OLS, returns, dividend fills, fixed cash advice "
            "or automated portfolio recommendations are produced.",
            "Publication dates are observed link/RSS/series dates, not inferred reporting periods. "
            "Future links are excluded and counted; an undated index is explicitly undated.",
            "Missing sources remain null or failed. A partial run is not cached as successful.",
            "Credit-spread signal is unknown here; observed AAA narrowing is counterevidence "
            "to generalized widening, not proof of all-credit deterioration.",
        ],
    }


def render_html(report):
    esc = lambda value: html.escape(str(value)) if value is not None else "unknown"

    def table(headers, rows):
        return "<div class='scroll'><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>" % (
            "".join("<th>%s</th>" % esc(h) for h in headers),
            "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % v for v in row) for row in rows))

    def link(url, label):
        return "<a href='%s' rel='noopener'>%s</a>" % (esc(url), esc(label))

    macro = []
    for c in report["sourceChecks"]:
        if c["group"] != "macro_market":
            continue
        links = "".join("<li>%s <small>%s</small></li>" % (
            link(p["url"], p["title"]), esc(p["publication_date"])) for p in c["date_candidates"][:5])
        macro.append(
            "<article><span class='label'>%s / %s</span><h3>%s</h3><p>%s</p>"
            "<small>Observed date: %s · Checked: %s</small><ul>%s</ul>%s</article>" % (
                esc(c["status"]), esc(c["family"]), link(c["url"], c["name"]),
                esc(c["excerpt"] or c["error"] or "No dated evidence observed."),
                esc(c["publication_date"]), esc(c["checked_at"]), links,
                "<p class='warning'>Index or series only; no semantic review.</p>"))
    counts = report["coverage"]
    nav_table = table(["Code / Product", "NAV Date", "Unit NAV", "Collection"], [
        [esc(n["code"] + " / " + n["name"]), esc(n["date"]), esc(n["unit_nav"]),
         esc(n["status"] + (" / stale" if n["stale"] else ""))] for n in report["navLatest"]])
    section_table = table(["Section", "Coverage", "Independent Review"], [
        [link(report["original_report"] + "#" + r["id"], r["title"]),
         esc("present" if r["present"] else "MISSING"), esc(r["status"])]
        for r in report["sectionLedger"]])
    claim_table = table(["Claim", "Historical Status", "Today"], [
        [esc(r["id"] + " / " + r["title"]), esc(r["historical_status"]),
         esc(r["status"] + "; " + r["evidence_status"])] for r in report["claimLedger"]])
    manager_table = table(["Manager / Fund", "Current Names", "Short Tenure Flag", "Review"], [
        [esc(r["name"] + " / " + r["code"]), esc(", ".join(r["current_managers"] or []) or None),
         esc(r["is_new_manager"]), esc(r["status"])] for r in report["managerLedger"]])
    source_table = table(["Registry", "Evidence Scope", "Original Reverified"], [
        [esc(r["id"] + " / " + r["title"]), esc(r["status"]), "No"]
        for r in report["historicSourceLedger"]])
    failures = table(["Query", "HTTP", "Error"], [
        [esc(r["id"]), esc(r["http_status"]), esc(r["error"])] for r in report["failures"]])
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Asymmetry Daily Evidence | %s</title><style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#0c1017;
color:#e9edf3;font:15px/1.7 system-ui,sans-serif}main{max-width:1120px;margin:auto;padding:40px 24px}
a{color:#d6b88b;text-decoration:none}a:hover{text-decoration:underline}h1{font-size:clamp(30px,5vw,54px);
line-height:1.15;margin:18px 0}h2{font-size:24px;margin-top:45px}h3{font-size:17px}
.label,small{color:#a6b2c5}.label{text-transform:uppercase;letter-spacing:1px;font-size:11px}
.warning{color:#e6b76b}.banner{padding:20px;border-left:3px solid #d6b88b;background:#151c27}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:25px 0}
.stats div,article{background:#151c27;border:1px solid #263142;padding:18px;border-radius:10px}
.stats strong{font-size:28px;display:block}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
article p{overflow-wrap:anywhere}table{width:100%%;border-collapse:collapse;font-size:13px}
th,td{padding:12px;text-align:left;border-bottom:1px solid #263142;vertical-align:top}
th{color:#a6b2c5}.scroll{overflow:auto}ul{padding-left:20px}details{margin:20px 0}
@media(max-width:680px){main{padding:25px 16px}.grid{grid-template-columns:1fr}
.stats{grid-template-columns:1fr 1fr}table{min-width:560px}}
</style></head><body><main><span class="label">Asymmetry / Public Evidence / %s</span>
<h1>Macro First.<br>Judgment Still Pending.</h1>
<p>%s · %s · Last independent review: %s</p>
<div class="banner">%s<br><strong class="warning">HTTP 200 is not fact reverified.
Partial evidence must not be presented as a completed all-content review.</strong></div>
<div class="stats"><div><strong>%s / %s</strong>successful queries</div>
<div><strong>%s / 26</strong>sections / claims retained</div>
<div><strong>14</strong>manager ledgers</div><div><strong>0</strong>fresh semantic reviews</div></div>
<p>%s · %s · %s</p><h2>Macro &amp; Market Sources</h2><div class="grid">%s</div>
<h2>Latest Fund &amp; ETF NAV Observations</h2><p>No returns, dividend reconstruction or forecasts.</p>%s
<h2>Failures &amp; Unknowns</h2>%s
<h2>Whole-Content Ledger</h2>%s
<details><summary>26 DOC100 Claims: Historical Status Preserved</summary>%s</details>
<details><summary>14 Managers: No Completed Fresh Review</summary>%s</details>
<details><summary>65 Registered Sources: Historic vs Related Evidence</summary>%s</details>
<h2>Limitations</h2><ul>%s</ul></main></body></html>""" % (
        esc(report["asof"]), esc(report["asof"]), esc(report["status"]),
        esc(report["checked_at"]), esc(report["last_independent_review"]),
        esc(REVIEW_MODE), counts["success"], counts["attempted"], counts["sections"],
        link(report["original_report"], "Original frozen website"),
        link("audit.json", "Structured evidence"), link("evidence/manifest.json", "Evidence manifest"),
        "".join(macro), nav_table, failures, section_table, claim_table, manager_table,
        source_table, "".join("<li>%s</li>" % esc(s) for s in report["limitations"]))


def load_inputs(public_root, asof):
    root = public_root / SITE_PATH
    data_raw = (root / "research-data.json").read_bytes()
    site_raw = (root / "index.html").read_bytes()
    data = json.loads(data_raw)
    if len(data["names"]) != 31 or len(data["managerCards"]) != 14:
        raise ValueError("Registry shape changed; independent review and collector update required")
    if len(data["doc100"]["claims"]) != 26 or len(data["sources"]) != 65:
        raise ValueError("Claim/source registry changed; independent review required")
    reports = sorted((public_root / "reports").glob("*/intelligence.json"), reverse=True)
    candidates = [p for p in reports if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.parent.name)
                  and p.parent.name <= asof]
    if not candidates:
        raise ValueError("No existing dated intelligence schema reference")
    intel_raw = candidates[0].read_bytes()
    script_raw = Path(__file__).read_bytes()
    verifier_raw = Path(__file__).with_name("verify_asymmetry_daily.py").read_bytes()
    config_path = public_root / "research-engine/research/daily_config.json"
    config_raw = config_path.read_bytes() if config_path.exists() else b"{}"
    config = json.loads(config_raw)
    policy_path = public_root / "research-engine/research/asymmetry-daily-policy.json"
    policy_raw = policy_path.read_bytes() if policy_path.exists() else b"{}"
    policy = json.loads(policy_raw)
    manual_date = strict_date(policy.get("current_manual_review_date", LAST_REVIEW))
    if manual_date > today():
        raise ValueError("Manual review policy has a future date")
    intel = json.loads(intel_raw)
    intel["daily_source_priority"] = policy.get(
        "daily_source_priority", config.get("daily_source_priority", []))
    intel["current_manual_review_date"] = manual_date
    fingerprints = {
        "research_data": digest(data_raw), "site": digest(site_raw),
        "collector_code": digest(script_raw), "verifier_code": digest(verifier_raw),
        "intel_schema_reference": digest(intel_raw),
        "daily_source_priority_config": digest(config_raw),
        "daily_review_policy": digest(policy_raw),
    }
    return data, site_raw.decode("utf-8"), intel, fingerprints, candidates[0].parent.name


def run(public_root, report_root, asof, workers=6, timeout=18, max_requests=96, force=False):
    from verify_asymmetry_daily import verify_report

    data, site, intel, fingerprints, intel_date = load_inputs(public_root, asof)
    daily = report_root / "daily"
    dated = daily / "dates" / asof
    latest = daily / "latest.json"
    previous = None
    if latest.exists():
        try:
            previous = json_load(latest)
        except (OSError, ValueError):
            pass
    # No standard report/manifest gate: daily evidence always runs on a new date.
    if not force and dated.joinpath("audit.json").exists():
        try:
            cached = json_load(dated / "audit.json")
            errors = verify_report(cached, data)
            if (not errors and cached["status"] == "success"
                    and cached["input_fingerprints"] == fingerprints
                    and cached["verified_on"] == today()):
                print("Same-day successful evidence cache:", dated / "audit.json", flush=True)
                if not previous or previous.get("asof", "") <= asof:
                    atomic_json(latest, cached)
                return cached
        except (OSError, ValueError, KeyError):
            pass
    if previous and previous.get("asof", "") > asof:
        previous = None
    jobs = build_jobs(data, intel, asof, intel.get("daily_source_priority"))
    print("Collecting %d bounded requests, workers=%d, timeout=%ss" % (
        len(jobs), workers, timeout), flush=True)
    scheduled = jobs[:max_requests]
    with ThreadPoolExecutor(max_workers=min(workers, 6)) as executor:
        checks = list(executor.map(lambda job: fetch_check(job, asof, timeout), scheduled))
    for job in jobs[max_requests:]:
        checks.append({
            **job, "status": "failed", "checked_at": timestamp(), "publication_date": None,
            "date_candidates": [], "content_sha256": None, "excerpt": "", "http_status": None,
            "error": "Request budget exhausted; query not sent", "fact_reverified": False,
            "requires_independent_review": True, "last_success": None, "stale": True,
            "attempted": False,
        })
    for check in checks:
        check.setdefault("attempted", True)
        print(check["id"], check["status"], check["error"] or "", flush=True)
    report = assemble(data, site, checks, previous, asof, fingerprints, intel_date,
                      intel["current_manual_review_date"])
    report["original_report"] = os.path.relpath(
        str(public_root / SITE_PATH / "index.html"), str(dated))
    report["daily_source_priority_loaded"] = bool(intel.get("daily_source_priority"))
    report["coverage"]["attempted"] = sum(c["attempted"] for c in checks)
    report["coverage"]["planned"] = len(checks)
    report["coverage"]["not_attempted"] = sum(not c["attempted"] for c in checks)
    for group, row in report["coverage"]["groups"].items():
        subset = [c for c in checks if c["group"] == group]
        row["attempted"] = sum(c["attempted"] for c in subset)
        row["planned"] = len(subset)
        row["not_attempted"] = sum(not c["attempted"] for c in subset)
    errors = verify_report(report, data)
    if errors:
        raise ValueError("Refusing publication of invalid report: " + "; ".join(errors[:8]))
    evidence = dated / "evidence"
    for check in checks:
        # Only safe public, structured extracts. No cookies, raw personal docs or environment.
        atomic_json(evidence / (check["id"] + ".json"), check)
    atomic_json(evidence / "manifest.json", [
        {"id": c["id"], "file": c["id"] + ".json", "url": c["url"],
         "checked_at": c["checked_at"], "content_sha256": c["content_sha256"],
         "status": c["status"]} for c in checks])
    atomic_json(dated / "audit.json", report)
    errors = verify_report(json_load(dated / "audit.json"), data)
    if errors:
        raise ValueError("Dated report failed read-back validation")
    atomic_bytes(dated / "audit.html", render_html(report).encode("utf-8"))
    if not previous or previous.get("asof", "") <= asof:
        atomic_json(latest, json_load(dated / "audit.json"))
    print(json.dumps({
        "status": report["status"], "coverage": report["coverage"],
        "dated_json": str(dated / "audit.json"), "html": str(dated / "audit.html"),
        "latest": str(latest), "requires_independent_review": True,
    }, ensure_ascii=False), flush=True)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-root", type=Path, default=Path(
        os.environ.get("RESEARCH_PUBLIC_ROOT", str(Path(__file__).resolve().parents[2]))))
    parser.add_argument("--report-root", type=Path)
    parser.add_argument("--date", default=today())
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--timeout", type=float, default=18)
    parser.add_argument("--max-requests", type=int, default=96)
    parser.add_argument("--force", action="store_true", help="Bypass successful same-day cache")
    parser.add_argument("--plan", action="store_true", help="Print jobs without querying or writing")
    args = parser.parse_args(argv)
    try:
        asof = strict_date(args.date)
        if asof > today():
            raise ValueError("Future audit dates are forbidden")
        if not 1 <= args.workers <= 6 or not 1 <= args.timeout <= 60 or not 1 <= args.max_requests <= 96:
            raise ValueError("workers 1..6, timeout 1..60, max-requests 1..96 required")
        public_root = args.public_root.resolve()
        report_root = args.report_root.resolve() if args.report_root else public_root / SITE_PATH
        if args.plan:
            data, _, intel, _, _ = load_inputs(public_root, asof)
            print(json.dumps(build_jobs(data, intel, asof, intel.get("daily_source_priority")),
                             ensure_ascii=False, indent=2))
            return 0
        result = run(public_root, report_root, asof, args.workers, args.timeout,
                     args.max_requests, args.force)
        return 0 if result["status"] == "success" else 2
    except (ValueError, OSError, KeyError) as exc:
        print("Audit not published:", type(exc).__name__, str(exc)[:400], flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
