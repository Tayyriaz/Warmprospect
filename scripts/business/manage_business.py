#!/usr/bin/env python3
"""
Manage businesses from JSON config files under businesses/<business_id>/config.json.
Syncs config to the database. Replaces per-business Python creation scripts.
"""

import sys
import os
import json
import argparse
from pathlib import Path

# Project root (parent of scripts/business/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Keys accepted by config_manager.create_or_update_business (do not pass others)
CONFIG_KEYS = {
    "business_id", "business_name", "system_prompt", "greeting_message",
    "secondary_greeting_message", "primary_goal", "personality", "privacy_statement", "theme_color",
    "widget_position", "website_url", "contact_email", "contact_phone",
    "cta_tree", "rules", "custom_routes", "available_services", "topic_ctas",
    "experiments", "voice_enabled", "chatbot_button_text", "business_logo",
    "enabled_categories",
}


def businesses_dir() -> Path:
    return PROJECT_ROOT / "businesses"


def find_business_configs():
    """Yield (business_id, config_path) for each businesses/<id>/config.json."""
    bdir = businesses_dir()
    if not bdir.is_dir():
        return
    for path in sorted(bdir.iterdir()):
        if path.is_dir():
            cfg = path / "config.json"
            if cfg.is_file():
                yield path.name, cfg


def load_config(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def sync_business(config_path: Path) -> dict:
    from core.config.business_config import config_manager

    raw = load_config(config_path)
    # Only pass keys that the API accepts
    kwargs = {k: raw[k] for k in CONFIG_KEYS if k in raw}
    if "business_id" not in kwargs:
        kwargs["business_id"] = config_path.parent.name
    return config_manager.create_or_update_business(**kwargs)


def cmd_list(_args):
    print("Businesses (from businesses/*/config.json):")
    for bid, cfg_path in find_business_configs():
        print(f"  {bid}  ->  {cfg_path}")


def cmd_sync(args):
    from core.config.business_config import config_manager

    if args.business_id:
        # Sync one business by id
        cfg_path = businesses_dir() / args.business_id / "config.json"
        if not cfg_path.is_file():
            print(f"Config not found: {cfg_path}", file=sys.stderr)
            sys.exit(1)
        config = sync_business(cfg_path)
        print(f"Synced: {config['business_id']} ({config.get('business_name', '')})")
        return

    # Sync all
    count = 0
    for bid, cfg_path in find_business_configs():
        try:
            config = sync_business(cfg_path)
            print(f"Synced: {config['business_id']} ({config.get('business_name', '')})")
            count += 1
        except Exception as e:
            print(f"Error syncing {bid}: {e}", file=sys.stderr)
            if not args.continue_on_error:
                raise
    print(f"Done. Synced {count} business(es).")


def main():
    parser = argparse.ArgumentParser(description="Manage businesses from JSON configs")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List businesses that have config.json")

    sync_p = sub.add_parser("sync", help="Sync config.json to database")
    sync_p.add_argument("business_id", nargs="?", help="Business ID to sync (default: all)")
    sync_p.add_argument("--continue-on-error", action="store_true", help="Continue on error when syncing all")

    args = parser.parse_args()
    if args.command == "list":
        cmd_list(args)
    elif args.command == "sync":
        cmd_sync(args)


if __name__ == "__main__":
    main()
