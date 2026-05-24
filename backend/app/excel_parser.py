import re
import urllib.parse
import zipfile
import xml.etree.ElementTree as ET
from io import BytesIO
from typing import Dict, List

NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

COLUMN_MAP = {
    "A": "transaction_id",
    "B": "seller_name",
    "C": "product_name",
    "D": "dispute_reason",
    "E": "seller_urls",
    "F": "pdp_urls",
    "G": "dsqc_urls",
}


def normalize_url(raw_url: str) -> str:
    raw_url = raw_url.strip()
    if not raw_url or raw_url.upper() == "NA":
        return ""
    if raw_url.startswith(("http://", "https://")):
        return raw_url
    return f"https://{raw_url.lstrip('/')}"


def split_urls(raw_value: str) -> List[str]:
    if not raw_value or not raw_value.strip():
        return []
    matches = re.findall(
        r"https?://[^\s,]+|(?:[A-Za-z0-9.-]+\.[A-Za-z]{2,}[^\s,]*)",
        raw_value,
    )
    seen = set()
    urls = []
    for match in matches:
        url = normalize_url(match)
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def parse_excel(file_bytes: bytes) -> List[Dict]:
    """Read dispute rows from the Excel upload."""
    with zipfile.ZipFile(BytesIO(file_bytes)) as archive:
        shared_strings = []
        shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        for item in shared_root.findall("a:si", NS):
            shared_strings.append("".join(node.text or "" for node in item.iterfind(".//a:t", NS)))

        sheet_root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        rows = sheet_root.find("a:sheetData", NS)
        if rows is None:
            return []

        parsed_rows = []
        for row in list(rows)[1:]:
            row_data = {}
            for cell in row.findall("a:c", NS):
                ref = cell.attrib.get("r", "")
                column = "".join(ch for ch in ref if ch.isalpha())
                value_node = cell.find("a:v", NS)
                value = value_node.text if value_node is not None else ""
                if cell.attrib.get("t") == "s" and value:
                    value = shared_strings[int(value)]
                row_data[column] = (value or "").strip()

            transaction_id = row_data.get("A", "")
            if not transaction_id:
                continue

            parsed_rows.append(
                {
                    "transaction_id": transaction_id,
                    "seller_name": row_data.get("B", ""),
                    "product_name": row_data.get("C", ""),
                    "dispute_reason": row_data.get("D", ""),
                    "images": {
                        "seller": split_urls(row_data.get("E", "")),
                        "pdp": split_urls(row_data.get("F", "")),
                        "dsqc": split_urls(row_data.get("G", "")),
                    },
                }
            )
        return parsed_rows
