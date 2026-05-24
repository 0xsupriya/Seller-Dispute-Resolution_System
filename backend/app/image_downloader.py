import html
import mimetypes
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Optional, Set

TIMEOUT_SECONDS = 30
USER_AGENT = "Mozilla/5.0 SellerDisputeImageDownloader/1.0"
IMG_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".jfif", ".svg"}


class ImageLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[tuple]) -> None:
        attr_map = dict(attrs)
        if tag.lower() == "img" and attr_map.get("src"):
            self.links.append(attr_map["src"])
        if tag.lower() == "a":
            href = attr_map.get("href")
            if href and any(ext in href.lower() for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp")):
                self.links.append(href)


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned or "file"


def rewrite_sharepoint_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if ".sharepoint.com" not in parsed.netloc:
        return url
    query = urllib.parse.parse_qs(parsed.query)
    query["download"] = ["1"]
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query, doseq=True)))


def rewrite_google_drive_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc not in {"drive.google.com", "www.drive.google.com"}:
        return rewrite_sharepoint_url(url)
    query = urllib.parse.parse_qs(parsed.query)
    file_id = query.get("id", [""])[0] if parsed.path == "/open" else ""
    if not file_id:
        match = re.search(r"/file/d/([^/]+)", parsed.path)
        file_id = match.group(1) if match else ""
    if not file_id:
        return rewrite_sharepoint_url(url)
    return rewrite_sharepoint_url(f"https://drive.google.com/uc?export=download&id={file_id}")


def normalize_url(raw_url: str) -> str:
    raw_url = raw_url.strip()
    if not raw_url or raw_url.upper() == "NA":
        return ""
    if raw_url.startswith(("http://", "https://")):
        return rewrite_google_drive_url(raw_url)
    return rewrite_google_drive_url(f"https://{raw_url.lstrip('/')}")


def make_request(url: str) -> urllib.request.Request:
    return urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "image/*,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )


def extension_from_response(url: str, content_type: Optional[str]) -> str:
    path_ext = Path(urllib.parse.urlparse(url).path).suffix.lower()
    if path_ext in IMG_EXTENSIONS:
        return path_ext
    if content_type:
        guessed = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if guessed:
            return ".jpg" if guessed == ".jpe" else guessed
    return ".jpg"


def write_bytes(target_dir: Path, filename_stem: str, url: str, payload: bytes, content_type: Optional[str]) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    extension = extension_from_response(url, content_type)
    target_path = target_dir / f"{safe_name(filename_stem)}{extension}"
    counter = 1
    while target_path.exists():
        target_path = target_dir / f"{safe_name(filename_stem)}_{counter}{extension}"
        counter += 1
    target_path.write_bytes(payload)
    return target_path


def extract_image_links(base_url: str, html_text: str) -> List[str]:
    parser = ImageLinkParser()
    parser.feed(html_text)
    seen: Set[str] = set()
    resolved: List[str] = []
    for link in parser.links:
        absolute = urllib.parse.urljoin(base_url, html.unescape(link))
        if absolute not in seen:
            seen.add(absolute)
            resolved.append(absolute)
    return resolved


def is_html_content_type(content_type: Optional[str]) -> bool:
    if not content_type:
        return False
    lowered = content_type.lower()
    return lowered.startswith("text/html") or lowered.startswith("application/xhtml+xml")


def download_source(url: str, target_dir: Path, filename_prefix: str) -> List[str]:
    normalized = normalize_url(url)
    if not normalized:
        return []

    parsed = urllib.parse.urlparse(normalized)
    if Path(parsed.path).suffix.lower() in IMG_EXTENSIONS:
        with urllib.request.urlopen(make_request(normalized), timeout=TIMEOUT_SECONDS) as response:
            payload = response.read()
            content_type = response.headers.get("Content-Type", "")
            saved = write_bytes(target_dir, filename_prefix, response.geturl(), payload, content_type)
            return [str(saved)]

    with urllib.request.urlopen(make_request(normalized), timeout=TIMEOUT_SECONDS) as response:
        content_type = response.headers.get("Content-Type", "")
        body = response.read()
        final_url = response.geturl()

    if content_type.lower().startswith("image/") or not is_html_content_type(content_type):
        saved = write_bytes(target_dir, filename_prefix, final_url, body, content_type)
        return [str(saved)]

    links = extract_image_links(final_url, body.decode("utf-8", errors="ignore"))
    saved_paths: List[str] = []
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
