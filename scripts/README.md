# Scripts

Organized by purpose:

## Database (`db/`)

- **migrate_db.py** – Auto-sync database schema with SQLAlchemy models  
  - No options. Run from project root.

## Business Management (`business/`)

- **manage_business.py** – Sync businesses from `businesses/<id>/config.json` to database  

  **Commands:**

  | Command | Description |
  |--------|-------------|
  | `list` | List all businesses that have a `config.json` |
  | `sync [business_id]` | Sync one business or all (omit `business_id` to sync all) |

  **Options (for `sync`):**

  | Option | Description |
  |--------|-------------|
  | `business_id` | (optional) Business ID to sync; if omitted, syncs all businesses |
  | `--continue-on-error` | When syncing all, continue on error instead of exiting |

## Knowledge Base (`kb/`)

- **build_kb_for_business.py** – Build knowledge base for a specific business  

  **Options:**

  | Option | Required | Description |
  |--------|----------|-------------|
  | `--business_id` | Yes | Business ID |
  | `--url` | Yes | Website URL to scrape |

## Utilities (`utils/`)

- **generate_admin_key.py** – Generate secure admin API keys  

  **Options:**

  | Option | Default | Description |
  |--------|---------|-------------|
  | `--length` | `32` | Length of the key in bytes (e.g. 32 → 64 hex chars) |
  | `--format` | `hex` | Output format: `hex`, `base64`, or `urlsafe` |
  | `--env-format` | (flag) | Print as `ADMIN_API_KEY=...` for .env |

---

## Usage

```bash
# Database
python scripts/db/migrate_db.py

# Business management
python scripts/business/manage_business.py list
python scripts/business/manage_business.py sync
python scripts/business/manage_business.py sync goaccel-website
python scripts/business/manage_business.py sync --continue-on-error

# Knowledge base
python scripts/kb/build_kb_for_business.py --business_id goaccel-website --url https://example.com

# Utilities – admin API key
python scripts/utils/generate_admin_key.py
python scripts/utils/generate_admin_key.py --length 64
python scripts/utils/generate_admin_key.py --format base64
python scripts/utils/generate_admin_key.py --format urlsafe
python scripts/utils/generate_admin_key.py --env-format
```
