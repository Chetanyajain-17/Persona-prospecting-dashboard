# Persona Prospecting Dashboard

## Flow
1. Enter organization + location.
2. Search a predefined persona list for public LinkedIn profile URLs.
3. Deduplicate results.
4. Display name, position, persona and LinkedIn URL.
5. Select profiles and enrich them using Zintlr.
6. Display email/phone in the same dashboard.
7. Export CSV.

## Run
```bash
pip install -r requirements.txt
streamlit run app.py
```

Required credentials:
- Serper API key
- Zintlr Access-Token
- Zintlr Secret-Key

## Important
LinkedIn prohibits third-party software that scrapes or automates its website, so this version
does not crawl LinkedIn directly. It uses a public web-search API for discovery and Zintlr's
authorized API for enrichment.

For production, add authentication, PostgreSQL/Supabase storage, provider credit budgets,
role normalization, logging, retries, and privacy/compliance controls.
