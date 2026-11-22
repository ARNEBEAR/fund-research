"""Validate daily evidence and its invariants; --self-test is offline.

CLI: --audit-file FILE [--public-root CHECKOUT], or --public-root CHECKOUT
     [--date YYYY-MM-DD] [--report-root DIRECTORY].
AUDIT_SCHEMA is a portable JSON Schema. The built-in walker covers exactly its
used subset so validation does not require installing jsonschema.
"""

import argparse
import json
import math
import os
import re
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo


REVIEW_MODE = "scheduled evidence collection and rule checks; no fresh AI or human review"
SECTION_IDS = {
    "verdict", "doc100", "audit", "market", "blind", "managers", "portfolio",
    "scenarios", "replay", "execution", "sources",
}
DATE = {"type": ["string", "null"], "format": "date"}
HASH = {"type": ["string", "null"], "pattern": "^[0-9a-f]{64}$"}
LEDGER_ROW = {
    "type": "object",
    "required": ["status", "requires_independent_review", "fact_reverified"],
    "properties": {
        "status": {"type": "string"}, "requires_independent_review": {"const": True},
        "fact_reverified": {"const": False}, "last_independent_review": DATE,
        "verified_on": DATE,
    },
}
AUDIT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Asymmetry Daily Public Evidence",
    "type": "object",
    "required": [
        "schema_version", "asof", "checked_at", "verified_on", "source_dates", "status",
        "stale", "last_success", "review_mode", "last_independent_review",
        "requires_independent_review", "independent_review_complete", "input_fingerprints",
        "coverage", "sourceChecks", "navLatest", "sectionLedger", "claimLedger",
        "managerLedger", "historicSourceLedger", "changes", "failures", "errors", "limitations",
    ],
    "properties": {
        "schema_version": {"const": "asymmetry-daily-evidence/1"},
        "asof": {"type": "string", "format": "date"},
        "verified_on": {"type": "string", "format": "date"},
        "checked_at": {"type": "string", "format": "date-time"},
        "source_dates": {"type": "array", "items": {"type": "string", "format": "date"},
                         "uniqueItems": True},
        "status": {"enum": ["success", "partial"]}, "stale": {"type": "boolean"},
        "last_success": {"type": ["object", "null"]},
        "review_mode": {"const": REVIEW_MODE}, "last_independent_review": DATE,
        "requires_independent_review": {"const": True},
        "independent_review_complete": {"const": False},
        "input_fingerprints": {"type": "object", "required": [
            "research_data", "site", "collector_code", "verifier_code", "intel_schema_reference"],
            "additionalProperties": {"type": "string", "pattern": "^[0-9a-f]{64}$"}},
        "coverage": {"type": "object", "required": [
            "attempted", "success", "failed", "planned", "not_attempted", "groups",
            "sections", "claims", "managers", "funds", "etfs", "registered_sources",
            "semantic_reviews_today"]},
        "sourceChecks": {
            "type": "array", "minItems": 1, "items": {
                "type": "object", "required": [
                    "id", "url", "kind", "group", "status", "checked_at", "publication_date",
                    "date_candidates", "content_sha256", "excerpt", "http_status", "error",
                    "attempted", "requires_independent_review", "fact_reverified",
                    "stale", "last_success"],
                "properties": {
                    "id": {"type": "string"}, "url": {"type": "string"},
                    "checked_at": {"type": "string", "format": "date-time"},
                    "publication_date": DATE, "content_sha256": HASH,
                    "excerpt": {"type": "string", "maxLength": 1200},
                    "status": {"enum": ["collected", "failed"]},
                    "attempted": {"type": "boolean"}, "fact_reverified": {"const": False},
                    "requires_independent_review": {"const": True}, "stale": {"type": "boolean"},
                    "date_candidates": {"type": "array", "items": {
                        "type": "object", "required": ["title", "url", "publication_date"],
                        "properties": {"publication_date": {"type": "string", "format": "date"}}}},
                },
            },
        },
        "navLatest": {"type": "array", "minItems": 37, "items": {
            "type": "object", "required": [
                "code", "product_kind", "status", "date", "unit_nav", "cumulative_nav",
                "stale", "error", "checked_at", "verified_on", "last_success", "return_method"],
            "properties": {
                "code": {"type": "string", "pattern": "^\\d{6}$"}, "date": DATE,
                "unit_nav": {"type": ["number", "null"], "exclusiveMinimum": 0},
                "cumulative_nav": {"type": ["number", "null"], "exclusiveMinimum": 0},
                "status": {"enum": ["collected", "failed"]},
                "product_kind": {"enum": ["fund", "etf"]}, "verified_on": DATE,
            },
        }},
        "sectionLedger": {"type": "array", "minItems": 11, "items": LEDGER_ROW},
        "claimLedger": {"type": "array", "minItems": 26, "maxItems": 26, "items": LEDGER_ROW},
        "managerLedger": {"type": "array", "minItems": 14, "maxItems": 14, "items": LEDGER_ROW},
        "historicSourceLedger": {"type": "array", "minItems": 65, "maxItems": 65, "items": LEDGER_ROW},
        "changes": {"type": "array"}, "failures": {"type": "array"},
        "errors": {"type": "array"}, "limitations": {"type": "array", "minItems": 1},
    },
}


def schema_errors(value, schema, path="$"):
    errors = []
    types = schema.get("type")
    if types:
        types = types if isinstance(types, list) else [types]
        kinds = {
            "object": isinstance(value, dict), "array": isinstance(value, list),
            "string": isinstance(value, str), "null": value is None,
            "boolean": isinstance(value, bool),
            "number": isinstance(value, (int, float)) and not isinstance(value, bool)
                      and math.isfinite(value),
        }
        if not any(kinds.get(kind, False) for kind in types):
            return [path + ": invalid type"]
    if "const" in schema and (type(value) is not type(schema["const"]) or value != schema["const"]):
        errors.append(path + ": wrong constant")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(path + ": outside enum")
    if isinstance(value, dict):
        errors.extend(path + ": missing " + key for key in schema.get("required", []) if key not in value)
        properties = schema.get("properties", {})
        for key, item in value.items():
            child_schema = properties.get(key)
            if child_schema is None and isinstance(schema.get("additionalProperties"), dict):
                child_schema = schema["additionalProperties"]
            if child_schema:
                errors.extend(schema_errors(item, child_schema, path + "." + key))
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", float("inf")):
            errors.append(path + ": wrong item count")
        if schema.get("uniqueItems"):
            encoded = [json.dumps(item, sort_keys=True) for item in value]
            if len(set(encoded)) != len(value):
                errors.append(path + ": duplicate items")
        for i, item in enumerate(value):
            errors.extend(schema_errors(item, schema.get("items", {}), path + "[" + str(i) + "]"))
    if isinstance(value, str):
        if len(value) > schema.get("maxLength", float("inf")):
            errors.append(path + ": text too long")
        if schema.get("pattern") and not re.search(schema["pattern"], value):
            errors.append(path + ": pattern mismatch")
        try:
            if schema.get("format") == "date":
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                    raise ValueError()
                date.fromisoformat(value)
            if schema.get("format") == "date-time":
                stamp = datetime.fromisoformat(value)
                if stamp.tzinfo is None:
                    raise ValueError()
        except ValueError:
            errors.append(path + ": invalid date format")
    if isinstance(value, (int, float)) and not isinstance(value, bool) and "exclusiveMinimum" in schema:
        if value <= schema["exclusiveMinimum"]:
            errors.append(path + ": nonpositive observation")
    return errors


def verify_report(report, data=None, now=None):
    errors = schema_errors(report, AUDIT_SCHEMA)
    if errors:
        return errors
    current = now or datetime.now(ZoneInfo("Asia/Shanghai"))
    asof = report["asof"]
    if asof > current.date().isoformat():
        errors.append("Future asof")
    if datetime.fromisoformat(report["checked_at"]) > current:
        errors.append("Future checked_at")
    if report["verified_on"] != report["checked_at"][:10]:
        errors.append("verified_on must be actual collection date")
    if report["last_independent_review"] not in (None, "2026-11-21", "2026-11-22"):
        errors.append("Scheduled rules cannot advance independent review date")
    if report["last_independent_review"] and report["last_independent_review"] > asof:
        errors.append("Future independent review")
    checks = report["sourceChecks"]
    ids = [c["id"] for c in checks]
    if len(set(ids)) != len(ids):
        errors.append("Duplicate source query IDs")
    failed = [c for c in checks if c["status"] == "failed"]
    success = len(checks) - len(failed)
    coverage = report["coverage"]
    expected = {
        "attempted": sum(c["attempted"] for c in checks), "success": success, "failed": len(failed),
        "planned": len(checks), "not_attempted": sum(not c["attempted"] for c in checks),
        "sections": len(report["sectionLedger"]), "claims": 26, "managers": 14, "funds": 31,
        "registered_sources": 65, "semantic_reviews_today": 0,
    }
    for key, count in expected.items():
        if coverage.get(key) != count:
            errors.append("Coverage mismatch: " + key)
    if {c["id"] for c in failed} != {c.get("id") for c in report["failures"]}:
        errors.append("Failure ledger incomplete")
    if report["errors"] != report["failures"]:
        errors.append("Error ledger inconsistent")
    if report["status"] != ("partial" if failed else "success") or report["stale"] != bool(failed):
        errors.append("Failed collection masquerades as success")
    for group in ("macro_market", "nav", "manager", "announcements"):
        rows = [c for c in checks if c["group"] == group]
        summary = coverage.get("groups", {}).get(group, {})
        counts = {
            "attempted": sum(c["attempted"] for c in rows),
            "success": sum(c["status"] == "collected" for c in rows),
            "failed": sum(c["status"] == "failed" for c in rows),
            "planned": len(rows), "not_attempted": sum(not c["attempted"] for c in rows),
        }
        if summary != counts:
            errors.append("Group coverage mismatch: " + group)
    for check in checks:
        if datetime.fromisoformat(check["checked_at"]) > current:
            errors.append("Future source checked_at: " + check["id"])
        if check["publication_date"] and check["publication_date"] > asof:
            errors.append("Future source publication: " + check["id"])
        for candidate in check["date_candidates"]:
            if candidate["publication_date"] > asof:
                errors.append("Future dated source link")
        if check["status"] == "collected" and (
                not check["content_sha256"] or check["http_status"] != 200
                or check["error"] or not check["attempted"] or check["stale"]):
            errors.append("Unsubstantiated collection: " + check["id"])
        if check["status"] == "failed" and (not check["error"] or not check["stale"]):
            errors.append("Silent source failure: " + check["id"])
    dates = sorted({c["publication_date"] for c in checks if c["publication_date"]})
    if report["source_dates"] != dates:
        errors.append("source_dates mismatch")
    nav = report["navLatest"]
    codes = [n["code"] for n in nav]
    if len(set(codes)) != len(codes):
        errors.append("Duplicate NAV codes")
    funds = {n["code"] for n in nav if n["product_kind"] == "fund"}
    etfs = {n["code"] for n in nav if n["product_kind"] == "etf"}
    if len(funds) != 31 or len(etfs) < 6 or coverage["etfs"] != len(etfs):
        errors.append("Incomplete NAV fund/ETF coverage")
    by_id = {c["id"]: c for c in checks}
    for row in nav:
        if row["date"] and row["date"] > asof:
            errors.append("Future NAV date")
        check = by_id.get(row.get("source_check_id"), {})
        if check.get("code") != row["code"] or check.get("status") != row["status"]:
            errors.append("NAV source identity/status mismatch")
        if row["status"] == "collected" and (
                row["date"] is None or row["unit_nav"] is None or row["stale"]
                or row["verified_on"] != row["checked_at"][:10]):
            errors.append("Silent missing NAV")
        if row["status"] == "failed" and (not row["error"] or not row["stale"] or row["verified_on"]):
            errors.append("Failed NAV has fresh verification")
        if "return" in row or "forecast" in row:
            errors.append("Unexpected returns/forecast in NAV evidence")
    section_ids = [r.get("id") for r in report["sectionLedger"]]
    if (not SECTION_IDS.issubset(set(section_ids)) or len(section_ids) != len(set(section_ids))
            or any(not r.get("present") for r in report["sectionLedger"])):
        errors.append("Whole-section coverage missing")
    claim_ids = [r.get("id") for r in report["claimLedger"]]
    if set(claim_ids) != {"A%02d" % n for n in range(1, 27)}:
        errors.append("Claim IDs missing or duplicated")
    manager_codes = [r.get("code") for r in report["managerLedger"]]
    if len(set(manager_codes)) != 14:
        errors.append("Manager coverage missing")
    if len([c for c in checks if c["kind"] == "manager"]) != 14 or len(
            [c for c in checks if c["kind"] == "announcements"]) != 14:
        errors.append("Manager/announcement queries missing")
    for ledger in ("sectionLedger", "claimLedger", "managerLedger"):
        for row in report[ledger]:
            if row["status"] != "needs independent review":
                errors.append("Rule mode claimed completed judgment: " + ledger)
            if row.get("last_independent_review") != report["last_independent_review"]:
                errors.append("Independent review baseline mismatch")
            if row.get("verified_on") is not None or row.get("independent_review_complete", False):
                errors.append("Scheduled ledger claimed semantic verification")
    for row in report["historicSourceLedger"]:
        if not row.get("historical") or row.get("original_source_fetched_today"):
            errors.append("Historic source called current")
        if row["status"] not in ("needs_research", "historical; related family collected"):
            errors.append("Invalid historic source status")
    if data:
        if funds != set(data["names"]):
            errors.append("Fund registry codes differ")
        if set(manager_codes) != {c["code"] for c in data["managerCards"]}:
            errors.append("Manager registry codes differ")
        historical = {c["id"]: c for c in report["historicSourceLedger"]}
        if set(historical) != {s["id"] for s in data["sources"]}:
            errors.append("Source registry IDs differ")
        for claim in data["doc100"]["claims"]:
            row = next((c for c in report["claimLedger"] if c["id"] == claim["id"]), {})
            if row.get("historical_status") != claim["status"] or row.get("source_ids") != claim["source_ids"]:
                errors.append("Historical claim status/source links changed")
    return errors


class HelperTests(unittest.TestCase):
    def test_nav(self):
        from audit_asymmetry_daily import parse_nav
        raw = json.dumps({"ErrCode": 0, "Data": {"LSJZList": [
            {"FSRQ": "2026-11-20", "DWJZ": "2.2378", "LJJZ": "", "JZZZL": ""},
        ]}})
        row = parse_nav(raw, "021902", "2026-11-22")
        self.assertEqual(row["unit_nav"], 2.2378)
        self.assertIsNone(row["cumulative_nav"])
        for value in ("", "0", "NaN", None):
            body = json.loads(raw)
            body["Data"]["LSJZList"][0]["DWJZ"] = value
            with self.assertRaises(ValueError):
                parse_nav(json.dumps(body), "021902", "2026-11-22")
        body = json.loads(raw)
        body["Data"]["LSJZList"] *= 2
        with self.assertRaises(ValueError):
            parse_nav(json.dumps(body), "021902", "2026-11-22")
        with self.assertRaises(ValueError):
            parse_nav(raw, "021902", "2026-11-19")

    def test_manager(self):
        from audit_asymmetry_daily import parse_manager
        raw = """<p>010390</p><table><tr><th>起始期</th><th>截止期</th>
<th>基金经理</th></tr><tr><td>2026-05-29</td><td>至今</td>
<td><a href="/manager/1">Alice</a></td></tr></table>"""
        result = parse_manager(raw, "010390", "2026-11-22")
        self.assertEqual(result["current_managers"], ["Alice"])
        with self.assertRaises(ValueError):
            parse_manager(raw.replace("至今", "2026-11-20"), "010390", "2026-11-22")

    def test_disclosure_and_index(self):
        from audit_asymmetry_daily import parse_announcements, parse_index
        raw = json.dumps({"ErrCode": 0, "Data": [
            {"FUNDCODE": "010390", "TITLE": "基金经理变更", "ID": "AN202611231",
             "PUBLISHDATE": "2026-11-23T00:00:00"},
            {"FUNDCODE": "010390", "TITLE": "第三季度报告", "ID": "AN202610271",
             "PUBLISHDATE": "2026-10-27T00:00:00"},
        ]})
        result = parse_announcements(raw, "010390", "2026-11-22")
        self.assertEqual(len(result["items"]), 1)
        self.assertFalse(result["items"][0]["body_reviewed"])
        page = "<p>" + "public index text " * 12 + "</p>"
        page += '<a href="/20261121/item.html">New</a><a href="/20261123/future.html">Future</a>'
        result = parse_index(page, "https://www.stats.gov.cn/", "2026-11-22")
        self.assertEqual(result["publication_date"], "2026-11-21")
        self.assertEqual(result["excluded_future_count"], 1)
        self.assertLessEqual(len(result["excerpt"]), 1200)
        with self.assertRaises(ValueError):
            parse_index("<p>Access Denied</p>", "https://www.stats.gov.cn/", "2026-11-22")

    def test_atomic_and_schema(self):
        from audit_asymmetry_daily import atomic_json
        with tempfile.TemporaryDirectory(prefix="asymmetry-helpers-") as directory:
            path = Path(directory) / "latest.json"
            atomic_json(path, {"a": 1})
            atomic_json(path, {"a": None})
            self.assertIsNone(json.loads(path.read_text())["a"])
        self.assertTrue(schema_errors({"unit_nav": 0}, {"type": "object", "properties": {
            "unit_nav": {"type": ["number", "null"], "exclusiveMinimum": 0}}}))
        self.assertTrue(verify_report({}))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-root", type=Path, default=Path(
        os.environ.get("RESEARCH_PUBLIC_ROOT", str(Path(__file__).resolve().parents[2]))))
    parser.add_argument("--report-root", type=Path)
    parser.add_argument("--date")
    parser.add_argument("--audit-file", type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--print-schema", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        result = unittest.TextTestRunner(verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(HelperTests))
        return 0 if result.wasSuccessful() else 1
    if args.print_schema:
        print(json.dumps(AUDIT_SCHEMA, indent=2))
        return 0
    root = args.public_root.resolve()
    report_root = args.report_root or root / "proposals/2026-11-21/asymmetry"
    path = args.audit_file or report_root / "daily" / (
        "dates/" + args.date + "/audit.json" if args.date else "latest.json")
    try:
        if args.date:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date) or args.date > datetime.now(
                    ZoneInfo("Asia/Shanghai")).date().isoformat():
                raise ValueError("Invalid or future date")
            date.fromisoformat(args.date)
        report = json.loads(path.read_text(encoding="utf-8"))
        data = json.loads((root / "proposals/2026-11-21/asymmetry/research-data.json").read_text(
            encoding="utf-8"))
        errors = verify_report(report, data)
        if errors:
            print(json.dumps({"valid": False, "errors": errors}, indent=2))
            return 1
        print(json.dumps({"valid": True, "path": str(path), "status": report["status"],
                          "coverage": report["coverage"]}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print("Verification failed:", type(exc).__name__, str(exc)[:300])
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
