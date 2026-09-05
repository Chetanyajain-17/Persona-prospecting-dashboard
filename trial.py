import os
import re
import requests
import pandas as pd
import streamlit as st


# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="IT Persona Discovery Engine",
    layout="wide"
)

LUSHA_URL = "https://api.lusha.com/v3/contacts/prospecting"


# ============================================================
# DISCOVERY SEARCH GROUPS
#
# These are intentionally broader than the old exact-title
# search. The idea is to give Lusha several ways to discover
# relevant technology people.
# ============================================================

DISCOVERY_GROUPS = {

    "Technology & IT": [
        "IT",
        "Information Technology",
        "Information Systems",
        "Technology",
        "Technology Management",
        "IT Management",
        "IT Operations",
        "Technology Operations",
        "IT Services",
        "IT Service Management",
        "IT Service Delivery",
        "IT Infrastructure",
    ],

    "Infrastructure & Network": [
        "Infrastructure",
        "IT Infrastructure",
        "Infrastructure Management",
        "Network",
        "Network Management",
        "Network Infrastructure",
        "Systems",
        "Systems Administration",
        "Systems Management",
        "Cloud Infrastructure",
        "Cloud Architecture",
    ],

    "Security": [
        "Information Security",
        "Cyber Security",
        "Cybersecurity",
        "Network Security",
        "Security",
        "Security Operations",
        "Information Security Management",
        "Cybersecurity Management",
    ],

    "Executive Technology": [
        "CTO",
        "Chief Technology Officer",
        "CIO",
        "Chief Information Officer",
        "CISO",
        "Chief Information Security Officer",
        "Chief Security Officer",
        "Head of Technology",
        "Head of IT",
        "Technology Director",
        "IT Director",
    ],
}


# ============================================================
# PERSONA CLASSIFICATION
# ============================================================

PERSONA_RULES = {

    "CTO / CIO / CISO": [
        r"\bcto\b",
        r"chief technology officer",
        r"chief technical officer",
        r"\bcio\b",
        r"chief information officer",
        r"\bciso\b",
        r"chief information security officer",
        r"chief security officer",
    ],

    "IT Leadership": [
        r"\bit manager\b",
        r"\bit director\b",
        r"\bit head\b",
        r"head of it",
        r"head - it",
        r"head, it",
        r"head of information technology",
        r"information technology head",
        r"information technology manager",
        r"information technology director",
        r"information technology lead",
        r"manager of information technology",
        r"director of information technology",
        r"information systems manager",
        r"information systems director",
        r"information systems head",
        r"technology manager",
        r"technology director",
        r"technology head",
        r"head of technology",
        r"director of technology",
        r"technology lead",
        r"it operations manager",
        r"it operations director",
        r"technology operations manager",
        r"it service manager",
        r"it service delivery manager",
    ],

    "Infrastructure / Network": [
        r"infrastructure manager",
        r"infrastructure director",
        r"infrastructure lead",
        r"it infrastructure manager",
        r"it infrastructure director",
        r"it infrastructure lead",
        r"infrastructure architect",
        r"network manager",
        r"network director",
        r"network lead",
        r"network architect",
        r"network administrator",
        r"network engineer",
        r"network security",
        r"systems administrator",
        r"system administrator",
        r"systems manager",
        r"systems engineer",
        r"system engineer",
        r"server administrator",
        r"cloud architect",
        r"cloud infrastructure",
        r"cloud engineer",
    ],

    "Cyber Security": [
        r"\bciso\b",
        r"chief information security officer",
        r"information security manager",
        r"information security director",
        r"information security lead",
        r"information security architect",
        r"cyber security manager",
        r"cybersecurity manager",
        r"cyber security director",
        r"cybersecurity director",
        r"cyber security lead",
        r"cybersecurity lead",
        r"security manager",
        r"security director",
        r"security architect",
        r"security engineer",
        r"information security",
        r"cyber security",
        r"cybersecurity",
        r"security operations",
        r"soc manager",
        r"soc lead",
    ],

    "IT Operations / Service": [
        r"it operations",
        r"it support manager",
        r"it support lead",
        r"it service manager",
        r"it service delivery",
        r"service desk manager",
        r"help desk manager",
        r"technical support manager",
        r"technical support lead",
        r"desktop support manager",
        r"desktop support lead",
        r"it administrator",
        r"it administration",
    ],

    "IT Asset / Technology Management": [
        r"it asset",
        r"information technology asset",
        r"technology asset",
        r"asset management.*it",
        r"it.*asset management",
        r"software asset management",
        r"hardware asset management",
        r"technology management",
        r"systems management",
    ],
}


# ============================================================
# NON-IT EXCLUSIONS
# ============================================================

EXCLUDED_PATTERNS = [
    r"\baccount manager\b",
    r"\bkey account\b",
    r"\baccount executive\b",
    r"\bsales\b",
    r"\bsales manager\b",
    r"\bbusiness development\b",
    r"\bbd manager\b",
    r"\bmarketing\b",
    r"\bmarketing manager\b",
    r"\bhuman resources\b",
    r"\bhr manager\b",
    r"\brecruiter\b",
    r"\brecruitment\b",
    r"\bfinance\b",
    r"\bfinancial\b",
    r"\baccountant\b",
    r"\baccounts manager\b",
    r"\blegal\b",
    r"\bprocurement\b",
    r"\bpurchase manager\b",
]


# ============================================================
# PERSONA MATCHER
# ============================================================

def classify_persona(title):

    if not title:
        return False, "Unknown", "No job title"

    title = str(title).strip()
    t = title.lower()

    # First remove obvious non-IT roles.
    for pattern in EXCLUDED_PATTERNS:

        if re.search(pattern, t):
            return (
                False,
                "Excluded",
                f"Excluded by rule: {pattern}"
            )

    # Exact persona groups.
    for persona, patterns in PERSONA_RULES.items():

        for pattern in patterns:

            if re.search(pattern, t):
                return (
                    True,
                    persona,
                    f"Matched: {pattern}"
                )

    # --------------------------------------------------------
    # Flexible technology detection
    # --------------------------------------------------------

    technology_terms = [
        "information technology",
        "information systems",
        "technology",
        "infrastructure",
        "network",
        "cybersecurity",
        "cyber security",
        "information security",
        "systems administration",
        "system administration",
        "it operations",
        "it services",
    ]

    senior_terms = [
        "manager",
        "director",
        "head",
        "lead",
        "chief",
        "vp",
        "vice president",
        "architect",
        "administrator",
    ]

    has_technology = any(
        term in t for term in technology_terms
    )

    has_seniority = any(
        term in t for term in senior_terms
    )

    if has_technology and has_seniority:

        return (
            True,
            "Technology / IT",
            "Technology keyword + seniority keyword"
        )

    return (
        False,
        "Not IT",
        "No IT/Technology persona match"
    )


# ============================================================
# LOCATION
# ============================================================

def make_location(country, state, city):

    location = {}

    if country.strip():
        location["country"] = country.strip()

    if state.strip():
        location["state"] = state.strip()

    if city.strip():
        location["city"] = city.strip()

    return location


# ============================================================
# BUILD LUSHA PAYLOAD
# ============================================================

def build_payload(
    company_name,
    company_country,
    company_state,
    company_city,
    employee_country,
    employee_state,
    employee_city,
    job_titles,
    page_size=50
):

    contact_include = {
        "jobTitles": job_titles
    }

    employee_location = make_location(
        employee_country,
        employee_state,
        employee_city
    )

    if employee_location:

        contact_include["locations"] = [
            employee_location
        ]

    company_include = {}

    if company_name.strip():

        company_include["names"] = [
            company_name.strip()
        ]

    company_location = make_location(
        company_country,
        company_state,
        company_city
    )

    if company_location:

        company_include["locations"] = [
            company_location
        ]

    return {
        "pagination": {
            "page": 0,
            "size": page_size
        },

        "filters": {
            "contacts": {
                "include": contact_include
            },

            "companies": {
                "include": company_include
            }
        }
    }


# ============================================================
# LUSHA API
# ============================================================

def lusha_request(api_key, payload):

    headers = {
        "api_key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    return requests.post(
        LUSHA_URL,
        headers=headers,
        json=payload,
        timeout=60
    )


# ============================================================
# EXTRACT CONTACTS
# ============================================================

def extract_contacts(data):

    if not isinstance(data, dict):
        return []

    # Common structures.
    for key in [
        "contacts",
        "results",
        "data"
    ]:

        value = data.get(key)

        if isinstance(value, list):
            return value

        if isinstance(value, dict):

            for nested_key in [
                "contacts",
                "results",
                "data"
            ]:

                nested = value.get(nested_key)

                if isinstance(nested, list):
                    return nested

    return []


# ============================================================
# NORMALIZE CONTACT
# ============================================================

def normalize_contact(contact, discovery_group):

    if not isinstance(contact, dict):
        return None

    company = contact.get("company")

    if not isinstance(company, dict):
        company = {}

    location = contact.get("location")

    if not isinstance(location, dict):
        location = {}

    first_name = (
        contact.get("firstName")
        or contact.get("first_name")
        or ""
    )

    last_name = (
        contact.get("lastName")
        or contact.get("last_name")
        or ""
    )

    name = (
        contact.get("name")
        or f"{first_name} {last_name}".strip()
    )

    title = (
        contact.get("jobTitle")
        or contact.get("job_title")
        or contact.get("title")
        or ""
    )

    linkedin = (
        contact.get("linkedin")
        or contact.get("linkedinUrl")
        or contact.get("linkedin_url")
        or ""
    )

    company_name = (
        company.get("name")
        or contact.get("companyName")
        or ""
    )

    domain = (
        company.get("domain")
        or contact.get("companyDomain")
        or ""
    )

    city = (
        location.get("city")
        or contact.get("city")
        or ""
    )

    state = (
        location.get("state")
        or contact.get("state")
        or ""
    )

    country = (
        location.get("country")
        or contact.get("country")
        or ""
    )

    department = (
        contact.get("department")
        or ""
    )

    seniority = (
        contact.get("seniority")
        or ""
    )

    contact_id = (
        contact.get("id")
        or contact.get("contactId")
        or ""
    )

    qualified, persona, reason = classify_persona(
        title
    )

    return {
        "Name": name,
        "Current Title": title,
        "Persona": persona,
        "Department": department,
        "Seniority": seniority,
        "Company": company_name,
        "Company Domain": domain,
        "Employee City": city,
        "Employee State": state,
        "Employee Country": country,
        "LinkedIn": linkedin,
        "Contact ID": contact_id,
        "Discovery Group": discovery_group,
        "Qualified": qualified,
        "Reason": reason
    }


# ============================================================
# DEDUPLICATION
# ============================================================

def deduplicate_contacts(rows):

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    # Prefer LinkedIn as unique key.
    if "LinkedIn" in df.columns:

        df["_dedupe"] = (
            df["LinkedIn"]
            .fillna("")
            .astype(str)
            .str.lower()
            .str.strip()
        )

        # If LinkedIn missing, use name + company.
        missing = df["_dedupe"] == ""

        df.loc[missing, "_dedupe"] = (
            df.loc[missing, "Name"]
            .fillna("")
            .astype(str)
            .str.lower()
            .str.strip()
            + "|"
            + df.loc[missing, "Company"]
            .fillna("")
            .astype(str)
            .str.lower()
            .str.strip()
        )

        df = df.drop_duplicates(
            subset=["_dedupe"],
            keep="first"
        )

        df = df.drop(
            columns=["_dedupe"]
        )

    else:

        df = df.drop_duplicates()

    return df.reset_index(drop=True)


# ============================================================
# STREAMLIT UI
# ============================================================

st.title("🎯 IT Persona Discovery Engine")

st.write(
    "Broad Lusha discovery + flexible IT persona classification."
)

st.warning(
    "Lusha discovery and persona qualification are separate. "
    "A zero-result search does not prove that a company has no "
    "IT/technology employees."
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header("🔑 Lusha")

api_key = st.sidebar.text_input(
    "Lusha API Key",
    value=os.getenv("LUSHA_API_KEY", ""),
    type="password"
)


st.sidebar.header("🏢 Company")

company_name = st.sidebar.text_input(
    "Company Name",
    placeholder="e.g. Denave"
)

company_country = st.sidebar.text_input(
    "Company Country",
    value="India"
)

company_state = st.sidebar.text_input(
    "Company State",
    placeholder="e.g. Karnataka"
)

company_city = st.sidebar.text_input(
    "Company City",
    placeholder="e.g. Bangalore"
)


st.sidebar.header("📍 Employee Location")

employee_country = st.sidebar.text_input(
    "Employee Country",
    placeholder="Optional"
)

employee_state = st.sidebar.text_input(
    "Employee State",
    placeholder="Optional"
)

employee_city = st.sidebar.text_input(
    "Employee City",
    placeholder="Optional"
)


# ============================================================
# SEARCH OPTIONS
# ============================================================

st.sidebar.header("⚙️ Discovery")

run_fallback = st.sidebar.checkbox(
    "Run fallback discovery searches",
    value=True
)

max_groups = st.sidebar.slider(
    "Maximum discovery groups",
    min_value=1,
    max_value=len(DISCOVERY_GROUPS),
    value=len(DISCOVERY_GROUPS)
)


search_button = st.sidebar.button(
    "🔎 Discover Personas",
    type="primary",
    use_container_width=True
)


# ============================================================
# SEARCH
# ============================================================

if search_button:

    if not api_key.strip():

        st.error(
            "Enter your Lusha API key first."
        )

        st.stop()

    if not company_name.strip():

        st.error(
            "Enter a company name first."
        )

        st.stop()

    all_rows = []

    group_stats = []

    raw_responses = []

    groups_to_run = list(
        DISCOVERY_GROUPS.items()
    )[:max_groups]

    # --------------------------------------------------------
    # First discovery group
    # --------------------------------------------------------

    for index, (group_name, titles) in enumerate(
        groups_to_run
    ):

        # If fallback is disabled, only run the first group.
        if index > 0 and not run_fallback:
            break

        st.write(
            f"Searching: **{group_name}**..."
        )

        payload = build_payload(
            company_name=company_name,
            company_country=company_country,
            company_state=company_state,
            company_city=company_city,
            employee_country=employee_country,
            employee_state=employee_state,
            employee_city=employee_city,
            job_titles=titles,
            page_size=50
        )

        try:

            response = lusha_request(
                api_key,
                payload
            )

        except requests.RequestException as e:

            st.error(
                f"{group_name}: API/network error: {e}"
            )

            continue

        # ----------------------------------------------------
        # API error
        # ----------------------------------------------------

        if response.status_code != 200:

            st.error(
                f"{group_name}: "
                f"Lusha HTTP {response.status_code}"
            )

            try:

                error_data = response.json()

            except Exception:

                error_data = {
                    "raw": response.text
                }

            group_stats.append({
                "Discovery Group": group_name,
                "Lusha Returned": 0,
                "API Status": response.status_code,
                "Qualified": 0
            })

            raw_responses.append({
                "group": group_name,
                "payload": payload,
                "response": error_data
            })

            continue

        # ----------------------------------------------------
        # JSON
        # ----------------------------------------------------

        try:

            data = response.json()

        except Exception:

            st.error(
                f"{group_name}: invalid JSON response."
            )

            continue

        raw_responses.append({
            "group": group_name,
            "payload": payload,
            "response": data
        })

        contacts = extract_contacts(data)

        group_rows = []

        for contact in contacts:

            row = normalize_contact(
                contact,
                group_name
            )

            if row:

                group_rows.append(row)

                all_rows.append(row)

        qualified_group_count = sum(
            1
            for row in group_rows
            if row["Qualified"]
        )

        group_stats.append({
            "Discovery Group": group_name,
            "Lusha Returned": len(group_rows),
            "API Status": response.status_code,
            "Qualified": qualified_group_count
        })

        # ----------------------------------------------------
        # Optimization:
        #
        # Once we have a reasonable number of qualified
        # people, don't necessarily need every fallback.
        #
        # BUT we still allow the user to disable this behavior
        # by running all groups.
        # ----------------------------------------------------

        if (
            index == 0
            and run_fallback
            and qualified_group_count >= 10
        ):

            st.info(
                "The first discovery group already found "
                "10+ qualified contacts. Continuing with "
                "fallback groups because duplicate discovery "
                "can reveal additional personas."
            )

    # ========================================================
    # DEDUPLICATE
    # ========================================================

    df = deduplicate_contacts(
        all_rows
    )

    # ========================================================
    # STATS
    # ========================================================

    if len(df):

        qualified_df = df[
            df["Qualified"] == True
        ].copy()

        rejected_df = df[
            df["Qualified"] == False
        ].copy()

    else:

        qualified_df = pd.DataFrame()
        rejected_df = pd.DataFrame()

    total_discovered = len(df)

    total_qualified = len(
        qualified_df
    )

    total_rejected = len(
        rejected_df
    )

    # ========================================================
    # HEADER METRICS
    # ========================================================

    st.subheader(
        f"Results: {company_name}"
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Unique Lusha Contacts",
        total_discovered
    )

    c2.metric(
        "Qualified IT Personas",
        total_qualified
    )

    c3.metric(
        "Rejected",
        total_rejected
    )

    if total_discovered:

        rate = (
            total_qualified /
            total_discovered
        ) * 100

    else:

        rate = 0

    c4.metric(
        "Qualification Rate",
        f"{rate:.1f}%"
    )


    # ========================================================
    # DISCOVERY BREAKDOWN
    # ========================================================

    st.subheader(
        "🔍 Discovery Breakdown"
    )

    stats_df = pd.DataFrame(
        group_stats
    )

    if len(stats_df):

        st.dataframe(
            stats_df,
            use_container_width=True,
            hide_index=True
        )


    # ========================================================
    # ZERO RESULT
    # ========================================================

    if total_discovered == 0:

        st.error(
            "Lusha returned no contacts for the discovery "
            "queries."
        )

        st.info(
            "This does NOT mean the company has no IT "
            "personas. It means Lusha returned no contacts "
            "matching the company + location + discovery "
            "filters used."
        )

        st.subheader(
            "Possible reasons"
        )

        st.markdown(
            """
            - Company name does not match Lusha's company record.
            - Company location filter is too restrictive.
            - Lusha does not have the relevant people indexed.
            - The people use titles outside the discovery groups.
            - The company has multiple records/domains.
            """
        )


    # ========================================================
    # QUALIFIED PERSONAS
    # ========================================================

    if total_qualified:

        st.subheader(
            f"✅ Qualified Personas ({total_qualified})"
        )

        columns = [
            "Name",
            "Current Title",
            "Persona",
            "Department",
            "Seniority",
            "Company",
            "Company Domain",
            "Employee City",
            "Employee State",
            "Employee Country",
            "LinkedIn",
            "Discovery Group",
            "Reason"
        ]

        st.dataframe(
            qualified_df[columns],
            use_container_width=True,
            hide_index=True
        )

        # CSV

        csv = qualified_df[
            columns
        ].to_csv(
            index=False
        ).encode("utf-8")

        st.download_button(
            "⬇️ Download Qualified Personas",
            data=csv,
            file_name=(
                f"{company_name}_IT_personas.csv"
            ),
            mime="text/csv"
        )

    else:

        if total_discovered:

            st.warning(
                "Lusha returned contacts, but none passed "
                "our IT-persona classifier."
            )


    # ========================================================
    # PERSONA BREAKDOWN
    # ========================================================

    if total_qualified:

        st.subheader(
            "👥 Persona Breakdown"
        )

        persona_df = (
            qualified_df[
                "Persona"
            ]
            .value_counts()
            .rename_axis("Persona")
            .reset_index(
                name="Contacts"
            )
        )

        st.dataframe(
            persona_df,
            use_container_width=True,
            hide_index=True
        )


    # ========================================================
    # REJECTED CONTACTS
    # ========================================================

    if total_rejected:

        with st.expander(
            f"❌ Rejected Contacts ({total_rejected})"
        ):

            columns = [
                "Name",
                "Current Title",
                "Company",
                "Department",
                "Reason",
                "LinkedIn",
                "Discovery Group"
            ]

            st.dataframe(
                rejected_df[columns],
                use_container_width=True,
                hide_index=True
            )


    # ========================================================
    # RAW RESPONSES
    # ========================================================

    with st.expander(
        "🛠️ Raw Lusha Responses / Debug"
    ):

        for item in raw_responses:

            st.markdown(
                f"### {item['group']}"
            )

            st.write(
                "Request:"
            )

            st.json(
                item["payload"]
            )

            st.write(
                "Response:"
            )

            st.json(
                item["response"]
            )
