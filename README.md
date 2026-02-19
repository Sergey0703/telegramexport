# Telegram Store Scraper & Web-Export Tool

Automates extraction of product listings from Telegram channels. Downloads media, parses product metadata (name, price, size), and organizes them into a structured format ready for web store imports (Shopify, WooCommerce, etc.).

## Features

- 🔐 Secure authentication via Telegram API
- 📥 Downloads high-resolution images from posts
- 🖼️ Handles albums (multiple photos per post)
- 🏷️ Parses product name, price, size via regex
- 📁 Organizes products into structured folders
- 📊 Exports to CSV/XLSX for bulk platform import
- ⚡ Rate limiting to avoid Telegram flood bans

## Quick Start

### 1. Get Telegram API Credentials

1. Go to https://my.telegram.org/apps
2. Log in with your phone number
3. Create a new application
4. Copy your `API_ID` and `API_HASH`

### 2. Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment template
copy .env.example .env
```

### 3. Configuration

Edit `.env` file:

```env
API_ID=your_api_id_here
API_HASH=your_api_hash_here
CHANNEL=@your_channel_name
```

### 4. Run the Scraper

```bash
# Basic usage (scans last 100 messages)
python main.py

# Scan specific number of messages
python main.py --limit 200

# Override channel from command line
python main.py --channel @another_channel

# Export as Excel instead of CSV
python main.py --export-format xlsx
```

### 5. First-Time Authentication

On first run, Telegram will send an OTP code to your account. Enter it in the terminal when prompted. Session will be saved for future runs.

## Output Structure

```
Downloads/
├── Nike_Hoodie_1500/
│   ├── img_1.jpg
│   ├── img_2.jpg
│   ├── metadata.json
│   └── info.txt
├── Adidas_Pants_800/
│   ├── img_1.jpg
│   ├── metadata.json
│   └── info.txt
└── export_20260219_143022.csv
```

## Export Format (CSV)

| name | price | size | description | images | folder |
|------|-------|------|-------------|--------|--------|
| Nike_Hoodie | 1500 | L | Cotton blend... | img_1.jpg;img_2.jpg | Nike_Hoodie_1500 |

## Message Parsing

The scraper identifies product posts by:
- Messages containing photos/documents
- Text with price keywords: "Ціна:", "Price:", or numerical values with "грн", "UAH", "USD", "$"
- First line = Product name
- Remaining lines = Description

### Supported Price Formats
- `Ціна: 1500 грн`
- `Price: $50`
- `1200 UAH`
- `Ціна - 800`

## Safety Features

- ⏱️ **Rate Limiting**: 0.5s delay between messages
- 🚫 **FloodWait Handling**: Catches and reports rate limits
- 📂 **Unparsed Folder**: Messages with media but no price go to `Downloads/Unparsed/`
- 🔒 **Secure Storage**: API keys in `.env`, never hardcoded

## Troubleshooting

### "API_ID and API_HASH must be set"
Ensure `.env` file exists in the project directory with valid credentials.

### "FloodWaitError"
Telegram is rate-limiting. Wait the specified time before running again.

### No products downloaded
- Check if channel is accessible (public or you're a member)
- Verify messages contain photos and price information
- Try increasing `--limit`

### Session file issues
Delete `telegram_scraper.session` file to re-authenticate.

## Requirements

- Python 3.9+
- Windows/Linux/macOS

## License

MIT
