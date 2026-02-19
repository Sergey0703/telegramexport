#!/usr/bin/env python3
"""
Telegram Store Scraper & Web-Export Tool

Automates extraction of product listings from Telegram channels.
Downloads media, parses product metadata, and organizes into structured format.
"""

import argparse
import asyncio
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.types import Message, MessageMediaPhoto, MessageMediaDocument

# Constants
SESSION_NAME = "telegram_scraper"
DOWNLOADS_DIR = Path("Downloads")
UNPARSED_DIR = DOWNLOADS_DIR / "Unparsed"

# Regex patterns for parsing
PRICE_PATTERNS = [
    r"(?:Ціна|Price|Ціна\:|Price\:)\s*[:\-]?\s*(\d+)\s*(?:грн|UAH|USD|\$)?",
    r"(\d+)\s*(?:грн|UAH|USD|\$)",
]

SIZE_PATTERN = r"\b(XS|S|M|L|XL|XXL)\b"


class TelegramScraper:
    def __init__(self, api_id: int, api_hash: str, channel: str):
        self.api_id = api_id
        self.api_hash = api_hash
        self.channel = channel
        self.client = TelegramClient(SESSION_NAME, api_id, api_hash)
        self.products = []
        self.unparsed_count = 0

    async def start(self):
        """Start the Telegram client and authenticate."""
        await self.client.start()
        print(f"✓ Logged in as {(await self.client.get_me()).first_name}")

    async def stop(self):
        """Disconnect the client."""
        await self.client.disconnect()

    def parse_product_info(self, message_text: str) -> Optional[dict]:
        """
        Extract product name, price, and attributes from message text.
        Returns None if parsing fails.
        """
        if not message_text or not message_text.strip():
            return None

        lines = message_text.strip().split("\n")
        name = lines[0].strip() if lines else None

        # Extract price
        price = None
        for pattern in PRICE_PATTERNS:
            match = re.search(pattern, message_text, re.IGNORECASE)
            if match:
                price = int(match.group(1))
                break

        # If no price found, cannot be a product post
        if price is None:
            return None

        # Extract size if present
        size_match = re.search(SIZE_PATTERN, message_text, re.IGNORECASE)
        size = size_match.group(1).upper() if size_match else None

        # Description is everything after the first line
        description = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""

        return {
            "name": self._sanitize_name(name),
            "price": price,
            "size": size,
            "description": description,
            "raw_text": message_text,
        }

    def _sanitize_name(self, name: str) -> str:
        """Sanitize product name for folder creation."""
        # Remove special characters that can't be in folder names
        name = re.sub(r'[<>:"/\\|?*]', "", name)
        # Limit length
        name = name[:50].strip()
        # Replace spaces with underscores
        name = name.replace(" ", "_")
        return name

    async def download_media(self, message: Message, product_folder: Path) -> list:
        """Download all media from a message to the product folder."""
        downloaded_files = []

        if isinstance(message.media, MessageMediaPhoto):
            # Single photo
            file_path = await self.client.download_media(
                message.media, file=str(product_folder / "img_1.jpg")
            )
            if file_path:
                downloaded_files.append(os.path.basename(file_path))

        elif isinstance(message.media, MessageMediaDocument):
            # Document (could be photo or file)
            file_path = await self.client.download_media(
                message.media, file=str(product_folder / "img_1.jpg")
            )
            if file_path:
                downloaded_files.append(os.path.basename(file_path))

        # Handle albums (multiple photos in one message)
        if message.media and hasattr(message.media, "grouped_id") and message.media.grouped_id:
            # Get all messages in the album
            album_messages = await self.client.get_messages(
                self.channel,
                filter=lambda m: m.media and m.media.grouped_id == message.media.grouped_id,
            )
            for idx, album_msg in enumerate(album_messages):
                if album_msg.media:
                    file_path = await self.client.download_media(
                        album_msg.media,
                        file=str(product_folder / f"img_{idx + 1}.jpg"),
                    )
                    if file_path:
                        downloaded_files.append(os.path.basename(file_path))

        return downloaded_files

    async def scrape_channel(self, limit: int = 100):
        """
        Scrape product posts from the channel.

        Args:
            limit: Number of messages to scan
        """
        print(f"\n📡 Scanning last {limit} messages from {self.channel}...")

        entity = await self.client.get_entity(self.channel)
        messages = await self.client.get_messages(entity, limit=limit)

        for msg in messages:
            if not msg.message:
                continue

            # Check if message has media (photos)
            has_media = isinstance(msg.media, (MessageMediaPhoto, MessageMediaDocument))

            if not has_media:
                continue

            product_info = self.parse_product_info(msg.message)

            if product_info is None:
                # Message has media but couldn't be parsed
                self.unparsed_count += 1
                continue

            # Create product folder
            folder_name = f"{product_info['name']}_{product_info['price']}"
            product_folder = DOWNLOADS_DIR / folder_name
            product_folder.mkdir(parents=True, exist_ok=True)

            # Download media
            downloaded_files = await self.download_media(msg, product_folder)

            if not downloaded_files:
                # No media downloaded, skip
                continue

            # Save metadata
            metadata = {
                "name": product_info["name"],
                "price": product_info["price"],
                "size": product_info["size"],
                "description": product_info["description"],
                "images": downloaded_files,
                "message_date": msg.date.isoformat() if msg.date else None,
                "message_id": msg.id,
            }

            # Save metadata.json
            import json
            with open(product_folder / "metadata.json", "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            # Save raw text backup
            with open(product_folder / "info.txt", "w", encoding="utf-8") as f:
                f.write(product_info["raw_text"])

            self.products.append({
                "name": product_info["name"],
                "price": product_info["price"],
                "size": product_info["size"],
                "description": product_info["description"],
                "images": ";".join(downloaded_files),
                "folder": folder_name,
            })

            print(f"  ✓ Downloaded: {folder_name} ({len(downloaded_files)} images)")

            # Rate limiting to avoid FloodWait
            await asyncio.sleep(0.5)

        print(f"\n📊 Summary:")
        print(f"  • Products downloaded: {len(self.products)}")
        print(f"  • Unparsed media messages: {self.unparsed_count}")

    def generate_export(self, format: str = "csv"):
        """
        Generate export file for web platform import.

        Args:
            format: Export format ('csv' or 'xlsx')
        """
        if not self.products:
            print("\n⚠ No products to export.")
            return

        df = pd.DataFrame(self.products)

        # Reorder columns for standard e-commerce import
        columns_order = ["name", "price", "size", "description", "images", "folder"]
        df = df[columns_order]

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if format == "xlsx":
            export_path = DOWNLOADS_DIR / f"export_{timestamp}.xlsx"
            df.to_excel(export_path, index=False, sheet_name="Products")
        else:
            export_path = DOWNLOADS_DIR / f"export_{timestamp}.csv"
            df.to_csv(export_path, index=False, encoding="utf-8-sig")

        print(f"\n💾 Export saved: {export_path}")


async def main():
    parser = argparse.ArgumentParser(
        description="Telegram Store Scraper - Extract products from Telegram channels"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Number of messages to scan (default: 100)"
    )
    parser.add_argument(
        "--channel",
        type=str,
        help="Telegram channel username or link (overrides .env)"
    )
    parser.add_argument(
        "--export-format",
        choices=["csv", "xlsx"],
        default="csv",
        help="Export format (default: csv)"
    )

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    channel = args.channel or os.getenv("CHANNEL")

    # Validate credentials
    if not api_id or not api_hash:
        print("❌ Error: API_ID and API_HASH must be set in .env file")
        print("   Get credentials from https://my.telegram.org/apps")
        return

    if not channel:
        print("❌ Error: CHANNEL must be set in .env or provided via --channel")
        return

    # Create output directories
    DOWNLOADS_DIR.mkdir(exist_ok=True)
    UNPARSED_DIR.mkdir(exist_ok=True)

    scraper = TelegramScraper(int(api_id), api_hash, channel)

    try:
        await scraper.start()
        await scraper.scrape_channel(limit=args.limit)
        scraper.generate_export(format=args.export_format)
    except FloodWaitError as e:
        print(f"\n⚠ Rate limited. Please wait {e.seconds} seconds and try again.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise
    finally:
        await scraper.stop()


if __name__ == "__main__":
    asyncio.run(main())
