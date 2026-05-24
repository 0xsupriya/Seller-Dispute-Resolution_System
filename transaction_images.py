import html
import json
import mimetypes
import re
import urllib.parse
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path


WORKBOOK_PATH = Path("SHD_Dispute_data.xlsx")
OUTPUT_ROOT = Path("downloads")
TIMEOUT_SECONDS = 30
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CodexImageDownloader/1.0"
NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
IMAGE_COLUMNS = {
    "E": ("Product images", "product_images"),
    "F": ("PDP Images", "pdp_images"),
    "G": ("DSQC", "dsqc"),
}
IMG_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".jfif", ".svg"}


class ImageLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if tag.lower() == "img":
            src = attr_map.get("src")
            if src:
                self.links.append(src)
        if tag.lower() == "a":
            href = attr_map.get("href")
            if href and any(part in href.lower() for part in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg")):
                self.links.append(href)


def load_rows(workbook_path: Path) -> list[dict[str, str]]:
    with zipfile.ZipFile(workbook_path) as archive:
        shared_strings = []
        shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        for item in shared_root.findall("a:si", NS):
            shared_strings.append("".join(node.text or "" for node in item.iterfind(".//a:t", NS)))

        sheet_root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        rows = sheet_root.find("a:sheetData", NS)
        if rows is None:
            return []

        parsed_rows: list[dict[str, str]] = []
        for row in list(rows)[1:]:
            row_data: dict[str, str] = {}
            for cell in row.findall("a:c", NS):
                ref = cell.attrib.get("r", "")
                column = "".join(ch for ch in ref if ch.isalpha())
                value_node = cell.find("a:v", NS)
                value = value_node.text if value_node is not None else ""
                if cell.attrib.get("t") == "s" and value:
                    value = shared_strings[int(value)]
                row_data[column] = value or ""
            parsed_rows.append(row_data)
        return parsed_rows


def normalize_url(raw_url: str) -> str:
    raw_url = raw_url.strip()
    if not raw_url:
        return ""
    if raw_url.upper() == "NA":
        return ""
    if raw_url.startswith(("http://", "https://")):
        normalized = raw_url
    else:
        normalized = f"https://{raw_url.lstrip('/')}"
    return rewrite_google_drive_url(normalized)


def split_urls(raw_value: str) -> list[str]:
    matches = re.findall(r"https?://[^\s,]+|(?:[A-Za-z0-9.-]+\.[A-Za-z]{2,}[^\s,]*)", raw_value)
    return [normalize_url(match) for match in matches if normalize_url(match)]


def rewrite_google_drive_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc not in {"drive.google.com", "www.drive.google.com"}:
        return rewrite_sharepoint_url(url)

    query = urllib.parse.parse_qs(parsed.query)
    file_id = ""
    if parsed.path == "/open":
        file_id = query.get("id", [""])[0]
    else:
        match = re.search(r"/file/d/([^/]+)", parsed.path)
        if match:
            file_id = match.group(1)

    if not file_id:
        return rewrite_sharepoint_url(url)
    return rewrite_sharepoint_url(f"https://drive.google.com/uc?export=download&id={file_id}")


def rewrite_sharepoint_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if ".sharepoint.com" not in parsed.netloc:
        return url

    query = urllib.parse.parse_qs(parsed.query)
    query["download"] = ["1"]
    rebuilt_query = urllib.parse.urlencode(query, doseq=True)
    return urllib.parse.urlunparse(parsed._replace(query=rebuilt_query))


def is_html_content_type(content_type: str | None) -> bool:
    if not content_type:
        return False
    lowered = content_type.lower()
    return lowered.startswith("text/html") or lowered.startswith("application/xhtml+xml")


def make_request(url: str) -> urllib.request.Request:
    return urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "image/*,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned or "file"


def extension_from_response(url: str, content_type: str | None) -> str:
    parsed = urllib.parse.urlparse(url)
    path_ext = Path(parsed.path).suffix.lower()
    if path_ext in IMG_EXTENSIONS:
        return path_ext
    if content_type:
        guessed = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if guessed:
            if guessed == ".jpe":
                return ".jpg"
            return guessed
    return ".bin"


def write_bytes(target_dir: Path, filename_stem: str, url: str, payload: bytes, content_type: str | None) -> Path:
    extension = extension_from_response(url, content_type)
    target_path = target_dir / f"{safe_name(filename_stem)}{extension}"
    counter = 1
    while target_path.exists():
        target_path = target_dir / f"{safe_name(filename_stem)}_{counter}{extension}"
        counter += 1
    target_path.write_bytes(payload)
    return target_path


def extract_image_links(base_url: str, html_text: str) -> list[str]:
    parser = ImageLinkParser()
    parser.feed(html_text)
    seen: set[str] = set()
    resolved: list[str] = []
    for link in parser.links:
        absolute = urllib.parse.urljoin(base_url, html.unescape(link))
        if absolute not in seen:
            seen.add(absolute)
            resolved.append(absolute)
    return resolved


def download_direct_image(url: str, target_dir: Path, filename_stem: str) -> list[str]:
    with urllib.request.urlopen(make_request(url), timeout=TIMEOUT_SECONDS) as response:
        payload = response.read()
        content_type = response.headers.get("Content-Type", "")
        saved = write_bytes(target_dir, filename_stem, response.geturl(), payload, content_type)
        return [str(saved)]


def download_images_from_html(url: str, target_dir: Path, filename_prefix: str) -> list[str]:
    with urllib.request.urlopen(make_request(url), timeout=TIMEOUT_SECONDS) as response:
        content_type = response.headers.get("Content-Type", "")
        body = response.read()
        final_url = response.geturl()

    if content_type.lower().startswith("image/") or not is_html_content_type(content_type):
        saved = write_bytes(target_dir, filename_prefix, final_url, body, content_type)
        return [str(saved)]

    html_text = body.decode("utf-8", errors="ignore")
    links = extract_image_links(final_url, html_text)
    saved_paths: list[str] = []
    for index, image_url in enumerate(links, start=1):
        with urllib.request.urlopen(make_request(image_url), timeout=TIMEOUT_SECONDS) as image_response:
            image_bytes = image_response.read()
            image_type = image_response.headers.get("Content-Type", "")
            saved = write_bytes(
                target_dir,
                f"{filename_prefix}_{index}",
                image_response.geturl(),
                image_bytes,
                image_type,
            )
            saved_paths.append(str(saved))
    return saved_paths


def download_source(url: str, target_dir: Path, filename_prefix: str) -> list[str]:
    parsed = urllib.parse.urlparse(url)
    path_ext = Path(parsed.path).suffix.lower()
    if path_ext in IMG_EXTENSIONS:
        return download_direct_image(url, target_dir, filename_prefix)
    return download_images_from_html(url, target_dir, filename_prefix)


def existing_files(target_dir: Path) -> list[str]:
    if not target_dir.exists():
        return []
    return [str(path) for path in sorted(p for p in target_dir.iterdir() if p.is_file())]


def main() -> None:
    OUTPUT_ROOT.mkdir(exist_ok=True)
    rows = load_rows(WORKBOOK_PATH)
    summary_path = OUTPUT_ROOT / "summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    else:
        summary = {}

    for row in rows:
        transaction_id = row.get("A", "").strip()
        if not transaction_id:
            continue

        transaction_dir = OUTPUT_ROOT / safe_name(transaction_id)
        transaction_dir.mkdir(exist_ok=True)
        row_summary: dict[str, object] = {
            "transaction_id": transaction_id,
            "product_name": row.get("C", ""),
            "downloads": {},
            "errors": [],
        }

        for column, (label, folder_name) in IMAGE_COLUMNS.items():
            raw_url = row.get(column, "").strip()
            if not raw_url:
                continue

            source_dir = transaction_dir / folder_name
            source_dir.mkdir(exist_ok=True)
            normalized_urls = split_urls(raw_url)
            if not normalized_urls:
                single_url = normalize_url(raw_url)
                if not single_url:
                    continue
                normalized_urls = [single_url]
            current_files = existing_files(source_dir)
            if current_files:
                row_summary["downloads"][label] = {
                    "source_url": normalized_urls if len(normalized_urls) > 1 else normalized_urls[0],
                    "saved_files": current_files,
                }
                continue
            try:
                saved_files: list[str] = []
                source_errors: list[str] = []
                for index, normalized_url in enumerate(normalized_urls, start=1):
                    try:
                        saved_files.extend(download_source(normalized_url, source_dir, f"{folder_name}_{index}"))
                    except Exception as exc:
                        source_errors.append(f"{normalized_url} -> {exc}")
                row_summary["downloads"][label] = {
                    "source_url": normalized_urls if len(normalized_urls) > 1 else normalized_urls[0],
                    "saved_files": saved_files,
                }
                if not saved_files and not source_errors:
                    source_errors.append(f"{normalized_urls[0]} -> no downloadable files found")
                row_summary["errors"].extend(f"{label}: {message}" for message in source_errors)
            except Exception as exc:
                joined_url = ", ".join(normalized_urls)
                row_summary["errors"].append(f"{label}: {joined_url} -> {exc}")

        summary[transaction_id] = row_summary
        (transaction_dir / "metadata.json").write_text(json.dumps(row_summary, indent=2), encoding="utf-8")
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Processed {len(summary)} transactions into {OUTPUT_ROOT}")


if __name__ == "__main__":
    main()
