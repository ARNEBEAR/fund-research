"""Archive public research sources without executing downloaded HTML or scripts."""

import hashlib
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag in ("p", "div", "br", "tr", "h1", "h2", "h3", "li"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        if tag in ("p", "div", "tr", "h1", "h2", "h3", "li"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

    def text(self):
        return "\n".join(line.strip() for line in "".join(self.parts).splitlines() if line.strip())


def archive(item, directory, pdf=False):
    ext = ".pdf" if pdf else ".html"
    path = directory / (item["id"] + ext)
    meta = path.with_suffix(".meta.json")
    if not path.exists():
        req = Request(item["url"], headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=25) as response:
            data = response.read()
            final_url = response.url
            encoding = response.headers.get_content_charset()
        if pdf and not data.startswith(b"%PDF-"):
            raise ValueError("Response is not a PDF")
        path.write_bytes(data)
        meta.write_text(json.dumps({
            "url": item["url"], "final_url": final_url,
            "retrieved_at": datetime.now(timezone.utc).isoformat(), "encoding": encoding,
            "sha256": hashlib.sha256(data).hexdigest(),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    if pdf:
        pages = [{"page": i + 1, "text": p.extract_text()} for i, p in enumerate(PdfReader(path).pages)]
        path.with_suffix(".text.json").write_text(json.dumps(pages, ensure_ascii=False, indent=2), encoding="utf-8")
        return {**item, "status": "archived", "file": str(path.relative_to(ROOT)), "pages": len(pages)}
    data = path.read_bytes()
    encoding = json.loads(meta.read_text()).get("encoding")
    match = re.search(rb"charset\s*=\s*[\"']?([a-zA-Z0-9_-]+)", data[:5000])
    encoding = encoding or (match.group(1).decode() if match else "utf-8")
    parser = TextExtractor()
    parser.feed(data.decode(encoding, errors="replace"))
    text = parser.text()
    path.with_suffix(".txt").write_text(text, encoding="utf-8")
    return {**item, "status": "archived" if len(text) > 400 else "short_or_dynamic_page",
            "file": str(path.relative_to(ROOT)), "extracted_characters": len(text)}


def main():
    config = json.loads((ROOT / "research/deep_sources.json").read_text(encoding="utf-8"))
    directory = ROOT / "data/deep_research"
    directory.mkdir(parents=True, exist_ok=True)
    results = []
    for group in ("articles", "reports"):
        for item in config[group]:
            try:
                result = archive(item, directory, group == "reports")
            except Exception as exc:
                result = {**item, "status": "archive_failed", "error": str(exc)}
            results.append(result)
            print(item["id"], result["status"], flush=True)
    (directory / "manifest.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
