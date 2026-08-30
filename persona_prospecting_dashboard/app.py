import os
import re
import requests
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Persona Prospecting Dashboard", layout="wide")

DEFAULT_PERSONAS = [
    "CTO", "CIO", "CISO", "Chief Information Officer", "Chief Technology Officer",
    "Chief Information Security Officer", "IT Head", "Head of IT", "IT Manager",
    "IT Director", "VP IT", "VP Information Technology", "Head of Infrastructure",
    "Head of Cyber Security", "Cybersecurity Head", "Information Security Manager" , "System Administrator"
]

def search_query(org, location, persona):
    return f'site:linkedin.com/in/ "{persona}" "{org}" "{location}"'

def search_serper(query, api_key, num=10):
    r = requests.post(
        "https://google.serper.dev/search",
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        json={"q": query, "num": num},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("organic", [])

def extract_profiles(results):
    rows, seen = [], set()
    for item in results:
        url = item.get("link", "")
        if "linkedin.com/in/" not in url:
            continue
        url = url.split("?")[0].rstrip("/")
        if url in seen:
            continue
        seen.add(url)
        title = item.get("title", "")
        rows.append({
            "Name": title.split(" - ")[0].strip() if title else "",
            "Position": title,
            "LinkedIn": url,
            "Search snippet": item.get("snippet", ""),
        })
    return rows

def zintlr_enrich(linkedin_url, access_token, secret_key, reveal_email=True, reveal_phone=True):
    r = requests.post(
        "https://b2b2b.zintlr.com/b2b2b/v1/ln-url-to-ph-email/",
        headers={
            "Access-Token": access_token,
            "Secret-Key": secret_key,
            "Content-Type": "application/json",
        },
        json={
            "ln_url": linkedin_url,
            "phone_unlock": reveal_phone,
            "email_unlock": reveal_email,
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()

def flatten(data):
    emails, phones = [], []
    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if isinstance(v, (dict, list)):
                    walk(v)
                elif isinstance(v, str):
                    if "email" in k.lower() and "@" in v:
                        emails.append(v)
                    if ("phone" in k.lower() or "mobile" in k.lower()) and v.strip():
                        phones.append(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(data)
    return {
        "Email": ", ".join(dict.fromkeys(emails)),
        "Phone": ", ".join(dict.fromkeys(phones)),
    }

st.title("Persona Prospecting Dashboard")
st.caption("Public-profile discovery + single-provider contact enrichment")

with st.sidebar:
    st.header("Configuration")
    serper_key = st.text_input("Serper API key", type="password")
    z_access = st.text_input("Zintlr Access-Token", type="password")
    z_secret = st.text_input("Zintlr Secret-Key", type="password")
    max_profiles = st.slider("Max results per persona", 1, 10, 5)
    reveal_email = st.checkbox("Reveal email", True)
    reveal_phone = st.checkbox("Reveal phone", True)

    uploaded = st.file_uploader("Optional persona CSV", type=["csv"])
    personas = pd.read_csv(uploaded).iloc[:, 0].dropna().astype(str).tolist() if uploaded else DEFAULT_PERSONAS

c1, c2 = st.columns(2)
org = c1.text_input("Organization name", placeholder="Example: Infosys")
location = c2.text_input("Location", placeholder="Example: Bengaluru, India")

if st.button("Find personas", type="primary", use_container_width=True):
    if not org or not location:
        st.error("Enter both organization and location.")
        st.stop()
    if not serper_key:
        st.error("Add a Serper API key.")
        st.stop()

    all_rows = []
    progress = st.progress(0)

    for i, persona in enumerate(personas):
        try:
            results = search_serper(search_query(org, location, persona), serper_key, max_profiles)
            for row in extract_profiles(results):
                row.update({
                    "Persona": persona,
                    "Organization": org,
                    "Location": location,
                    "Email": "",
                    "Phone": "",
                    "Enrichment provider": "",
                    "Enrichment status": "Not enriched",
                })
                all_rows.append(row)
        except Exception as e:
            st.warning(f"{persona}: {e}")
        progress.progress((i + 1) / len(personas))

    if all_rows:
        df = pd.DataFrame(all_rows).drop_duplicates("LinkedIn")
        st.session_state["prospects"] = df
        st.success(f"Found {len(df)} unique public profile results.")
    else:
        st.warning("No matching public profile results found.")

if "prospects" in st.session_state:
    df = st.session_state["prospects"]

    st.subheader("Prospects")
    st.dataframe(
        df[["Name", "Position", "Persona", "LinkedIn", "Email", "Phone",
            "Enrichment provider", "Enrichment status"]],
        use_container_width=True,
        hide_index=True,
        column_config={"LinkedIn": st.column_config.LinkColumn("LinkedIn")}
    )

    selected = st.multiselect("Select profiles to enrich with Zintlr", df["LinkedIn"].tolist())

    if st.button("Enrich selected"):
        if not z_access or not z_secret:
            st.error("Add Zintlr credentials first.")
            st.stop()
        if not selected:
            st.info("Select at least one profile.")
            st.stop()

        for url in selected:
            idx = df.index[df["LinkedIn"] == url][0]
            try:
                result = flatten(zintlr_enrich(url, z_access, z_secret, reveal_email, reveal_phone))
                df.at[idx, "Email"] = result["Email"]
                df.at[idx, "Phone"] = result["Phone"]
                df.at[idx, "Enrichment provider"] = "Zintlr"
                df.at[idx, "Enrichment status"] = "Enriched"
            except Exception as e:
                df.at[idx, "Enrichment provider"] = "Zintlr"
                df.at[idx, "Enrichment status"] = f"Error: {e}"

        st.session_state["prospects"] = df
        st.rerun()

    st.download_button(
        "Download CSV",
        df.to_csv(index=False).encode(),
        file_name=f"{re.sub(r'[^A-Za-z0-9]+','_',org)}_personas.csv",
        mime="text/csv",
    )

st.divider()
st.caption(
    "This app does not log into, crawl, or automate LinkedIn. It discovers public LinkedIn "
    "profile URLs through a search API and uses the authorized Zintlr API for enrichment."
)
