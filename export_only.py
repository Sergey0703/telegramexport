#!/usr/bin/env python3
"""
Generate BigCommerce CSV from already-downloaded Downloads/ folders.
Does NOT re-download anything from Telegram.

Usage:
    python export_only.py
    python export_only.py --image-base-url https://cdn.example.com/products
    python export_only.py --format xlsx
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

DOWNLOADS_DIR = Path("Downloads")

# Lines to strip from description (Ukrainian service phrases + contacts)
_STRIP_PATTERNS = [
    r"Ціна[\s:–-].*",           # price line
    r"Розміри?[\s:–-].*",       # sizes line
    r"Для замовлення.*",        # "to order write here"
    r"@\w+",                    # @username mentions
    r"https?://\S+",            # any URLs
]
import re as _re
_STRIP_RE = _re.compile("|".join(_STRIP_PATTERNS), _re.IGNORECASE)


def clean_description(text: str) -> str:
    """Remove Ukrainian service lines and contacts from description."""
    lines = text.splitlines()
    clean = [l for l in lines if not _STRIP_RE.fullmatch(l.strip()) and l.strip()]
    return " ".join(clean).strip()


_JUNK_NAME_RE = _re.compile(r"^(Ціна|Price|Cina)\b", _re.IGNORECASE)


def clean_name(raw_name: str, folder_name: str) -> str:
    """If parsed name is just a price keyword, derive name from folder instead."""
    name = raw_name.replace("_", " ").strip()
    if _JUNK_NAME_RE.match(name):
        # folder format: NNN_Brand_Name_Price  → drop leading number and trailing price
        parts = folder_name.split("_")
        # drop leading digits part and trailing price part, also skip pure-digit parts
        parts = [p for p in parts[1:-1] if not p.isdigit() and not _JUNK_NAME_RE.match(p)]
        name = " ".join(parts).strip()
    return name or "Unknown Brand"


def build_export(image_base_url: str = "", format: str = "csv"):
    folders = sorted(
        p for p in DOWNLOADS_DIR.iterdir()
        if p.is_dir() and (p / "metadata.json").exists()
    )

    if not folders:
        print("❌ No product folders found in Downloads/")
        return

    products = []
    for folder in folders:
        with open(folder / "metadata.json", encoding="utf-8") as f:
            meta = json.load(f)

        # images stored as list in metadata.json
        images = meta.get("images", [])
        if isinstance(images, str):
            images = images.split(";")

        products.append({
            "folder": folder.name,
            "name": clean_name(meta.get("name", ""), folder.name),
            "price_uah": meta.get("price", 0),
            "description": clean_description(meta.get("description", "")),
            "images": images,
        })

    max_images = max(len(p["images"]) for p in products)

    rows = []
    for p in products:
        price_eur = round(p["price_uah"] / 50)

        row = {
            "Item Type": "Product",
            "Product Name": p["name"],
            "Category": "Clothing",
            "Price": price_eur,
            "Product Description": p["description"] or "",
            "Brand Name": "",
            "Product Weight": 0.5,
            "Product Type": "P",
            "Product Visible?": "Y",
        }

        for i in range(max_images):
            col = f"Product Image File – {i + 1}"
            if i < len(p["images"]):
                # WebDAV files are named: FolderName__img_N.jpg
                # Square brackets are stripped from folder name (Windows WebDAV can't copy them)
                webdav_folder = p['folder'].replace('[', '').replace(']', '')
                fname = f"{webdav_folder}__{p['images'][i]}"
                if image_base_url:
                    row[col] = f"{image_base_url.rstrip('/')}/{fname}"
                else:
                    row[col] = fname
            else:
                row[col] = ""

        rows.append(row)

    df = pd.DataFrame(rows)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if format == "xlsx":
        out = DOWNLOADS_DIR / f"export_bigcommerce_{timestamp}.xlsx"
        df.to_excel(out, index=False, sheet_name="Products")
    else:
        out = DOWNLOADS_DIR / f"export_bigcommerce_{timestamp}.csv"
        df.to_csv(out, index=False, encoding="utf-8-sig")

    print(f"Exported {len(rows)} products -> {out}")
    print(f"  Image columns: {max_images}")
    print(f"  Price: UAH / 50 -> EUR (rounded)")
    if image_base_url:
        print(f"  Image URL prefix: {image_base_url}")
    else:
        print(f"  Images: filename only (WebDAV mode)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export Downloads/ to BigCommerce CSV")
    parser.add_argument(
        "--image-base-url", type=str, default="",
        help="Base URL for images (e.g. https://cdn.example.com/products). Empty = WebDAV mode."
    )
    parser.add_argument(
        "--format", choices=["csv", "xlsx"], default="csv",
        help="Output format (default: csv)"
    )
    args = parser.parse_args()
    build_export(image_base_url=args.image_base_url, format=args.format)
