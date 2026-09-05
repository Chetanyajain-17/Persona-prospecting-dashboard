import os
import re
import requests
import pandas as pd
import streamlit as st


# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="Universal IT Persona Finder",
    layout="wide"
)

LUSHA_COMPANY_FILTER_URL = (
    "https://api.lusha.com/v3/companies/prospecting/filters/names"
)

LUSHA_CONTACT_URL = (
    "https://api.lusha.com/v3/contacts/prospecting"
)


# ============================================================
# PERSONA RULES
# ============================================================

PERSONA_RULES = {

    "CTO": [
        r"\bcto\b",
        r"chief technology officer",
        r"chief technical officer",
    ],

    "CIO": [
        r"\bcio\b",
        r"chief information officer",
    ],

    "CISO": [
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

    "Infrastructure": [
        r"infrastructure manager",
        r"infrastructure director",
        r"infrastructure lead",
        r"it infrastructure manager",
        r"it infrastructure director",
        r"it infrastructure lead",
        r"infrastructure architect",
        r"cloud infrastructure",
        r"cloud architect",
        r"cloud engineer",
    ],

    "Network": [
        r"network manager",
        r"network director",
        r"network lead",
        r"network architect",
        r"network administrator",
        r"network engineer",
        r"network security",
    ],

    "Systems": [
        r"systems administrator",
        r"system administrator",
        r"systems manager",
        r"systems engineer",
        r"system engineer",
        r"systems architect",
        r"system architect",
        r"server administrator",
    ],

    "Cyber Security": [
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

    "IT Operations": [
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

    "IT Asset Management": [
        r"it asset",
        r"information technology asset",
        r"technology asset",
        r"it.*asset management",
        r"asset management.*it",
        r"software asset management",
        r"hardware asset management",
    ],

    "Technology Management": [
        r"technology management",
        r"technology operations",
        r"information systems",
        r"information technology",
    ],
}


# ============================================================
# NON-IT EXCLUSIONS
# ============================================================

EXCLUDED = [
    r"\baccount manager\b",
    r"\baccount executive\b",
    r"\bkey account\b",
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
]


# ============================================================
# PERSONA CLASSIFIER
# ============================================================

def classify_persona(title):

    if not title:
        return False, "Unknown", "No job title"

    title = str(title).strip()
    t = title.lower()

    # Obvious non-IT exclusions
    for pattern in EXCLUDED:

        if re.search(pattern, t):

            return (
                False,
                "Excluded",
                f"Excluded: {pattern}"
            )

    # Strong persona rules
    for persona, patterns in PERSONA_RULES.items():

        for pattern in patterns:

            if re.search(pattern, t):

                return (
                    True,
                    persona,
                    f"Matched: {pattern}"
                )

    # Flexible technology matching
    technology_words = [
        "information technology",
        "information systems",
        "technology",
        "infrastructure",
        "network",
        "cybersecurity",
        "cyber security",
        "information security",
        "systems",
        "it operations",
        "it services",
    ]

    senior_words = [
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
        word in t
        for word in technology_words
    )

    has_seniority = any(
        word in t
        for word in senior_words
    )

    if has_technology and has_seniority:

        return (
            True,
            "Technology / IT",
            "Flexible technology + seniority match"
        )

    return (
        False,
        "Not IT",
        "No IT persona rule matched"
    )


# ============================================================
# LUSHA HEADERS
# ============================================================

def get_headers(api_key):

    return {
        "api_key": api_key,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }


# ============================================================
# STEP 1
# COMPANY NAME -> LUSHA COMPANY RECORDS
# ============================================================

def find_companies(api_key, company_name):

    params = {
        "query": company_name.strip()
    }

    response = requests.get(
        LUSHA_COMPANY_FILTER_URL,
        headers=get_headers(api_key),
        params=params,
        timeout=60
    )

    return response


# ============================================================
# STEP 2
# CONTACT SEARCH
#
# IMPORTANT:
# We use the exact company NAME returned by Lusha.
# We do NOT use the user's approximate name.
# ============================================================

def find_contacts(
    api_key,
    exact_company_name,
    company_domain="",
    company_country="",
    company_state="",
    company_city=""
):

    # --------------------------------------------------------
    # IMPORTANT FIX
    #
    # DO NOT restrict Lusha contact discovery to our own
    # predefined job-title list.
    #
    # First retrieve contacts from the EXACT resolved company.
    # Then the existing Python classifier decides whether the
    # person is an IT / Technology / Security persona.
    #
    # This prevents valid personas from being missed simply
    # because Lusha stores their title differently.
    # --------------------------------------------------------

    company_include = {
        "names": [
            exact_company_name
        ]
    }

    # --------------------------------------------------------
    # Company location remains OPTIONAL and works exactly
    # like before.
    # --------------------------------------------------------

    if company_country or company_state or company_city:

        location = {}

        if company_country:
            location["country"] = company_country

        if company_state:
            location["state"] = company_state

        if company_city:
            location["city"] = company_city

        if location:

            company_include["locations"] = [
                location
            ]

    # --------------------------------------------------------
    # CONTACT SEARCH
    #
    # We intentionally DO NOT send jobTitles here.
    #
    # Lusha finds contacts belonging to the exact company.
    # Our existing classify_persona() then filters them.
    # --------------------------------------------------------

    payload = {

        "pagination": {
            "page": 0,
            "size": 50
        },

        "filters": {

            "companies": {
                "include": company_include
            }
        }
    }

    # --------------------------------------------------------
    # Domain is still resolved and displayed exactly as before.
    # We do not change the existing verified company-name
    # selector because that is already proven to work with
    # your Lusha API.
    # --------------------------------------------------------

    response = requests.post(
        LUSHA_CONTACT_URL,
        headers=get_headers(api_key),
        json=payload,
        timeout=60
    )

    return response, payload

# ============================================================
# CONTACT EXTRACTION
# ============================================================

def extract_contacts(data):

    if not isinstance(data, dict):
        return []

    possible = [
        "contacts",
        "results",
        "data"
    ]

    for key in possible:

        value = data.get(key)

        if isinstance(value, list):
            return value

        if isinstance(value, dict):

            for nested_key in possible:

                nested = value.get(
                    nested_key
                )

                if isinstance(nested, list):
                    return nested

    return []


# ============================================================
# NORMALIZE CONTACT
# ============================================================

def normalize_contact(contact):

    if not isinstance(contact, dict):
        return None

    company = contact.get(
        "company",
        {}
    )

    if not isinstance(company, dict):
        company = {}

    location = contact.get(
        "location",
        {}
    )

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

    qualified, persona, reason = classify_persona(
        title
    )

    return {

        "Name": name,

        "Current Title": title,

        "Persona": persona,

        "Department": (
            contact.get("department")
            or ""
        ),

        "Seniority": (
            contact.get("seniority")
            or ""
        ),

        "Company": (
            company.get("name")
            or contact.get("companyName")
            or ""
        ),

        "Company Domain": (
            company.get("domain")
            or contact.get("companyDomain")
            or ""
        ),

        "Employee City": (
            location.get("city")
            or contact.get("city")
            or ""
        ),

        "Employee State": (
            location.get("state")
            or contact.get("state")
            or ""
        ),

        "Employee Country": (
            location.get("country")
            or contact.get("country")
            or ""
        ),

        "LinkedIn": linkedin,

        "Contact ID": (
            contact.get("id")
            or contact.get("contactId")
            or ""
        ),

        "Qualified": qualified,

        "Reason": reason
    }


# ============================================================
# UI
# ============================================================

st.title(
    "🎯 Domain-First IT Persona Finder"
)

st.caption(
    "Company name → exact Lusha company → domain → "
    "IT persona discovery"
)

st.warning(
    "Company resolution happens first. Contact Prospecting "
    "runs only after you select a Lusha company."
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header("🔑 Lusha")

api_key = st.sidebar.text_input(
    "Lusha API Key",
    value=os.getenv(
        "LUSHA_API_KEY",
        ""
    ),
    type="password"
)


st.sidebar.header("🏢 Company")

company_name = st.sidebar.text_input(
    "Company Name",
    placeholder="Motherhood Hospital"
)


st.sidebar.header("📍 Optional Company Location")

use_location = st.sidebar.checkbox(
    "Use company location filter",
    value=False
)

company_country = ""
company_state = ""
company_city = ""

if use_location:

    company_country = st.sidebar.text_input(
        "Country",
        value="India"
    )

    company_state = st.sidebar.text_input(
        "State",
        placeholder="Karnataka"
    )

    company_city = st.sidebar.text_input(
        "City",
        placeholder="Bangalore"
    )


# ============================================================
# STEP 1 BUTTON
# ============================================================

find_company_button = st.sidebar.button(
    "1️⃣ Find Company",
    type="primary",
    use_container_width=True
)


# ============================================================
# COMPANY RESOLUTION
# ============================================================

if find_company_button:

    if not api_key.strip():

        st.error(
            "Enter your Lusha API key."
        )

        st.stop()

    if not company_name.strip():

        st.error(
            "Enter a company name."
        )

        st.stop()

    with st.spinner(
        "Finding matching Lusha companies..."
    ):

        try:

            response = find_companies(
                api_key,
                company_name
            )

        except requests.RequestException as e:

            st.error(
                f"Connection error: {e}"
            )

            st.stop()

    if response.status_code != 200:

        st.error(
            f"Lusha returned HTTP "
            f"{response.status_code}"
        )

        try:
            st.json(
                response.json()
            )

        except Exception:
            st.code(
                response.text
            )

        st.stop()

    data = response.json()

    values = data.get(
        "values",
        []
    )

    if not values:

        st.error(
            "Lusha did not return any company matches."
        )

        st.json(data)

        st.stop()

    st.session_state[
        "company_matches"
    ] = values

    st.success(
        f"Found {len(values)} company matches."
    )


# ============================================================
# DISPLAY COMPANY MATCHES
# ============================================================

if "company_matches" in st.session_state:

    matches = st.session_state[
        "company_matches"
    ]

    st.subheader(
        "🏢 Select the exact Lusha company"
    )

    # Build readable labels
    labels = []

    for i, company in enumerate(matches):

        name = company.get(
            "name",
            "Unknown"
        )

        domain = company.get(
            "domains_homepage"
            or "fqdn",
            ""
        )

        has_contacts = company.get(
            "has_prospecting_contacts",
            False
        )

        contact_status = (
            "✅ Prospecting contacts available"
            if has_contacts
            else "❌ No prospecting contacts"
        )

        labels.append(
            f"{name} | {domain} | {contact_status}"
        )

    selected_index = st.radio(
        "Company matches",
        range(len(labels)),
        format_func=lambda x: labels[x]
    )

    selected_company = matches[
        selected_index
    ]

    exact_name = selected_company.get(
        "name",
        ""
    )

    domain = (
        selected_company.get(
            "domains_homepage"
        )
        or selected_company.get(
            "fqdn"
        )
        or ""
    )

    company_id = selected_company.get(
        "id",
        ""
    )

    has_contacts = selected_company.get(
        "has_prospecting_contacts",
        False
    )

    st.markdown("### Selected Company")

    c1, c2, c3 = st.columns(3)

    c1.write(
        f"**Exact Lusha Name:** {exact_name}"
    )

    c2.write(
        f"**Domain:** {domain}"
    )

    c3.write(
        f"**Prospecting Contacts:** "
        f"{'YES' if has_contacts else 'NO'}"
    )

    st.session_state[
        "selected_company"
    ] = selected_company

    # --------------------------------------------------------
    # Don't allow unnecessary contact searches if Lusha says
    # there are no prospecting contacts.
    # --------------------------------------------------------

    if not has_contacts:

        st.warning(
            "Lusha reports that this company record has "
            "no prospecting contacts. Selecting another "
            "company record may be better."
        )

    else:

        st.markdown(
            "### Step 2"
        )

        fetch_button = st.button(
            "2️⃣ Fetch IT Personas",
            type="primary"
        )

        if fetch_button:

            with st.spinner(
                "Fetching IT personas from Lusha..."
            ):

                try:

                    response, payload = find_contacts(
                        api_key=api_key,
                        exact_company_name=exact_name,
                        company_domain=domain,
                        company_country=(
                            company_country
                            if use_location
                            else ""
                        ),
                        company_state=(
                            company_state
                            if use_location
                            else ""
                        ),
                        company_city=(
                            company_city
                            if use_location
                            else ""
                        )
                    )

                except requests.RequestException as e:

                    st.error(
                        f"Contact API error: {e}"
                    )

                    st.stop()

            # ------------------------------------------------
            # API ERROR
            # ------------------------------------------------

            if response.status_code != 200:

                st.error(
                    f"Lusha returned HTTP "
                    f"{response.status_code}"
                )

                try:
                    st.json(
                        response.json()
                    )

                except Exception:
                    st.code(
                        response.text
                    )

                st.subheader(
                    "Contact Request Payload"
                )

                st.json(payload)

                st.stop()

            contact_data = response.json()

            contacts = extract_contacts(
                contact_data
            )

            rows = []

            for contact in contacts:

                row = normalize_contact(
                    contact
                )

                if row:
                    rows.append(row)

            df = pd.DataFrame(
                rows
            )

            # ------------------------------------------------
            # DEDUPLICATE
            # ------------------------------------------------

            if len(df):

                if "LinkedIn" in df.columns:

                    df["_key"] = (
                        df["LinkedIn"]
                        .fillna("")
                        .astype(str)
                        .str.lower()
                        .str.strip()
                    )

                    missing = (
                        df["_key"] == ""
                    )

                    df.loc[
                        missing,
                        "_key"
                    ] = (
                        df.loc[
                            missing,
                            "Name"
                        ]
                        .fillna("")
                        .astype(str)
                        .str.lower()
                        .str.strip()
                        + "|"
                        +
                        df.loc[
                            missing,
                            "Current Title"
                        ]
                        .fillna("")
                        .astype(str)
                        .str.lower()
                        .str.strip()
                    )

                    df = df.drop_duplicates(
                        "_key"
                    )

                    df = df.drop(
                        columns=["_key"]
                    )

                qualified = df[
                    df["Qualified"] == True
                ].copy()

                rejected = df[
                    df["Qualified"] == False
                ].copy()

            else:

                qualified = pd.DataFrame()
                rejected = pd.DataFrame()

            # ------------------------------------------------
            # METRICS
            # ------------------------------------------------

            billing = contact_data.get(
                "billing",
                {}
            )

            credits = billing.get(
                "creditsCharged",
                "Not reported"
            )

            st.subheader(
                "📊 Search Results"
            )

            c1, c2, c3, c4 = st.columns(4)

            c1.metric(
                "Lusha Contacts",
                len(df)
            )

            c2.metric(
                "Qualified IT",
                len(qualified)
            )

            c3.metric(
                "Rejected",
                len(rejected)
            )

            c4.metric(
                "Credits Charged",
                credits
            )

            # ------------------------------------------------
            # RESULTS
            # ------------------------------------------------

            if len(qualified):

                st.subheader(
                    f"✅ Qualified IT Personas "
                    f"({len(qualified)})"
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
                    "Reason"
                ]

                st.dataframe(
                    qualified[columns],
                    use_container_width=True,
                    hide_index=True
                )

                csv = qualified[
                    columns
                ].to_csv(
                    index=False
                ).encode(
                    "utf-8"
                )

                st.download_button(
                    "⬇️ Download Qualified Personas",
                    csv,
                    f"{exact_name}_IT_personas.csv",
                    "text/csv"
                )

            elif len(df):

                st.warning(
                    "Lusha returned contacts, but our "
                    "persona classifier did not qualify them."
                )

            else:

                st.error(
                    "Lusha returned 0 contacts for this "
                    "exact company record."
                )

                st.info(
                    "This means Lusha returned no contacts "
                    "for this particular company/persona "
                    "query. It does not prove that the "
                    "company has no IT employees."
                )

            # ------------------------------------------------
            # REJECTED
            # ------------------------------------------------

            if len(rejected):

                with st.expander(
                    f"❌ Rejected ({len(rejected)})"
                ):

                    rejected_columns = [
                        "Name",
                        "Current Title",
                        "Company",
                        "Department",
                        "Reason",
                        "LinkedIn"
                    ]

                    st.dataframe(
                        rejected[
                            rejected_columns
                        ],
                        use_container_width=True,
                        hide_index=True
                    )

            # ------------------------------------------------
            # PERSONA BREAKDOWN
            # ------------------------------------------------

            if len(qualified):

                st.subheader(
                    "👥 Persona Breakdown"
                )

                breakdown = (
                    qualified[
                        "Persona"
                    ]
                    .value_counts()
                    .rename_axis(
                        "Persona"
                    )
                    .reset_index(
                        name="Contacts"
                    )
                )

                st.dataframe(
                    breakdown,
                    use_container_width=True,
                    hide_index=True
                )

            # ------------------------------------------------
            # RAW RESPONSE
            # ------------------------------------------------

            with st.expander(
                "🔧 Raw Contact API Response"
            ):

                st.json(
                    contact_data
                )
