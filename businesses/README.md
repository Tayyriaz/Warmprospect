# Businesses (per-website / per-tenant)

Each business is a folder under `businesses/<business_id>/` with its config, CRM logic, and (optionally) data paths in one place.

## Folder layout

```
businesses/
  <business_id>/
    config.json     # Business config (synced to DB via scripts/manage_business.py)
    crm.py          # Optional: business-specific CRM (CRMTools class)
```

- **config.json** – JSON configuration for the chatbot (system prompt, greeting, CTA tree, theme, etc.). Use `python scripts/business/manage_business.py sync [business_id]` to sync to the database.
- **crm.py** – Optional. Each business wires CRM their own way: REST API, OAuth, webhooks, SDK, or no integration. Define a `CRMTools` class with `search_contact`, `create_new_contact`, `create_deal` methods (or any subset). Auth and config live entirely in that file (or env, or another file)—no shared CRM schema in config.json. If a business has no `crm.py`, CRM functions are not available.

## Knowledge base / index data

Index files (FAISS + metadata) stay under **data/** at project root:

- `data/<business_id>/index.faiss`
- `data/<business_id>/meta.jsonl`

Build them via the admin “Build KB” or `scripts/build_kb_for_business.py`. They are not stored inside `businesses/<business_id>/` so the repo stays clean and builds can stay outside version control.

## Adding a new business

1. Create `businesses/<business_id>/config.json` (see `businesses/goaccel-website/config.json` for fields).
2. Optionally add `businesses/<business_id>/crm.py` with a `CRMTools` class.
3. Run: `python scripts/business/manage_business.py sync <business_id>` (or `sync` with no id to sync all).
4. Build the knowledge base for that business from the admin panel or scripts.

## Commands

- List businesses: `python scripts/business/manage_business.py list`
- Sync one: `python scripts/business/manage_business.py sync goaccel-website`
- Sync all: `python scripts/business/manage_business.py sync`
