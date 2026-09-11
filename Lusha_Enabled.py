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
# ============================================================

def find_contacts(
    api_key,
    exact_company_name,
    company_domain="",
    company_country="",
    company_state="",
    company_city="",
    page=0,
    size=50
):

    company_include = {
        "names": [
            exact_company_name
        ]
    }

    # Optional company location filter
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

    # IMPORTANT:
    # Do NOT send jobTitles here.
    #
    # Lusha returns contacts belonging to the exact company.
    # classify_persona() performs the IT filtering locally.

    payload = {

        "pagination": {
            "page": page,
            "size": size
        },

        "filters": {

            "companies": {
                "include": company_include
            }
        }
    }

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

    # ========================================================
    # COMPANY
    # ========================================================

    company = contact.get("company", {})

    if not isinstance(company, dict):
        company = {}

    # ========================================================
    # LOCATION
    # ========================================================

    location = contact.get("location", {})

    if not isinstance(location, dict):
        location = {}

    # ========================================================
    # NAME
    # ========================================================

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

    # ========================================================
    # JOB TITLE
    # ========================================================

    raw_job_title = (
        contact.get("jobTitle")
        or contact.get("job_title")
        or contact.get("title")
        or ""
    )

    if isinstance(raw_job_title, dict):

        title = (
            raw_job_title.get("title")
            or raw_job_title.get("name")
            or ""
        )

        departments = (
            raw_job_title.get("departments")
            or []
        )

        seniority = (
            raw_job_title.get("seniority")
            or ""
        )

    else:

        title = str(raw_job_title)

        departments = (
            contact.get("departments")
            or []
        )

        seniority = (
            contact.get("seniority")
            or ""
        )

    # ========================================================
    # DEPARTMENT
    # ========================================================

    if isinstance(departments, list):

        department = ", ".join(
            str(x)
            for x in departments
            if x
        )

    else:

        department = str(
            departments or ""
        )

    # ========================================================
    # SENIORITY
    # ========================================================

    if isinstance(seniority, str):

        seniority = seniority.replace(
            "_",
            " "
        ).title()

    else:

        seniority = str(
            seniority or ""
        )

    # ========================================================
    # LINKEDIN
    # ========================================================

    social_links = contact.get("socialLinks", {})

    if not isinstance(social_links, dict):
        social_links = {}

    linkedin = (
        social_links.get("linkedin")
        or contact.get("linkedin")
        or contact.get("linkedinUrl")
        or contact.get("linkedin_url")
        or ""
    )

    linkedin_id = ""

    if linkedin:

        linkedin_match = re.search(
            r"linkedin\.com/in/([^/?#]+)",
            str(linkedin),
            re.IGNORECASE
        )

        if linkedin_match:
            linkedin_id = linkedin_match.group(1)

    # ========================================================
    # PERSONA
    # ========================================================

    qualified, persona, reason = classify_persona(
        title
    )

    # ========================================================
    # RETURN
    # ========================================================

    return {

        "Name": name,

        "Current Title": title,

        "Persona": persona,

        "Department": department,

        "Seniority": seniority,

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

        "LinkedIn ID": linkedin_id,

        "Contact ID": (
            contact.get("id")
            or contact.get("contactId")
            or ""
        ),

        "Qualified": qualified,

        "Reason": reason
    }


# ============================================================
# FETCH + CLASSIFY LUSHA IT PERSONAS
# ============================================================

def fetch_lusha_it_personas(
    api_key,
    exact_company_name,
    company_domain="",
    company_country="",
    company_state="",
    company_city="",
    max_pages=5,
    page_size=50
):

    all_rows = []
    raw_contacts = []

    for page in range(max_pages):

        response, payload = find_contacts(
            api_key=api_key,
            exact_company_name=exact_company_name,
            company_domain=company_domain,
            company_country=company_country,
            company_state=company_state,
            company_city=company_city,
            page=page,
            size=page_size
        )

        if response.status_code != 200:

            try:
                error_body = response.json()

            except Exception:
                error_body = response.text[:1000]

            raise RuntimeError(
                f"Lusha contact search returned HTTP "
                f"{response.status_code}: {error_body}"
            )

        try:
            data = response.json()

        except ValueError:

            raise RuntimeError(
                "Lusha returned invalid JSON."
            )

        contacts = extract_contacts(data)

        if not contacts:
            break

        raw_contacts.extend(
            contacts
        )

        for contact in contacts:

            normalized = normalize_contact(
                contact
            )

            if normalized:
                all_rows.append(
                    normalized
                )

        if len(contacts) < page_size:
            break

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
        "LinkedIn ID",
        "Contact ID",
        "Qualified",
        "Reason"
    ]

    if not all_rows:

        empty_df = pd.DataFrame(
            columns=columns
        )

        return (
            empty_df,
            empty_df.copy(),
            raw_contacts
        )

    all_df = pd.DataFrame(
        all_rows
    )

    # Remove duplicates by Contact ID
    if "Contact ID" in all_df.columns:

        with_id = all_df[
            all_df["Contact ID"]
            .astype(str)
            .str.strip()
            != ""
        ].copy()

        without_id = all_df[
            all_df["Contact ID"]
            .astype(str)
            .str.strip()
            == ""
        ].copy()

        if not with_id.empty:

            with_id = with_id.drop_duplicates(
                subset=["Contact ID"],
                keep="first"
            )

        all_df = pd.concat(
            [
                with_id,
                without_id
            ],
            ignore_index=True
        )

    else:

        all_df = all_df.drop_duplicates()

    # Final IT qualification
    qualified_df = all_df[
        all_df["Qualified"] == True
    ].copy()

    return (
        all_df,
        qualified_df,
        raw_contacts
    )


# ============================================================
# APOLLO ORGANIZATION ENRICHMENT
# ============================================================

def apollo_org_enrich(
    api_key,
    domain,
    company_name=""
):

    if not api_key or not api_key.strip():

        return (
            None,
            {
                "error":
                    "Apollo API key is missing."
            }
        )

    clean_domain = re.sub(
        r"^https?://",
        "",
        str(domain or "").strip(),
        flags=re.IGNORECASE
    )

    clean_domain = (
        clean_domain
        .split("/")[0]
        .strip()
        .lower()
    )

    clean_domain = clean_domain.removeprefix(
        "www."
    )

    if not clean_domain:

        return (
            None,
            {
                "error":
                    "Company domain is missing."
            }
        )

    url = (
        "https://api.apollo.io/"
        "api/v1/organizations/enrich"
    )

    headers = {
        "accept": "application/json",
        "x-api-key": api_key.strip(),
    }

    params = {
        "domain": clean_domain,
    }

    if company_name and company_name.strip():

        params["name"] = (
            company_name.strip()
        )

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=30,
    )

    return response, {
        "url": url,
        "params": params,
        "headers": {
            "accept": "application/json",
            "x-api-key": "***masked***"
        },
    }


# ============================================================
# APOLLO COMPLETE ORGANIZATION
# ============================================================

def apollo_complete_org(
    api_key,
    organization_id
):

    if not api_key or not api_key.strip():

        return (
            None,
            {
                "error":
                    "Apollo API key is missing."
            }
        )

    if (
        not organization_id
        or str(organization_id).strip()
        in {"", "Not available"}
    ):

        return (
            None,
            {
                "error":
                    "Apollo organization ID is missing."
            }
        )

    url = (
        f"https://api.apollo.io/"
        f"api/v1/organizations/"
        f"{organization_id}"
    )

    headers = {
        "accept": "application/json",
        "x-api-key": api_key.strip(),
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=30,
    )

    return response, {
        "url": url,
        "headers": {
            "accept": "application/json",
            "x-api-key": "***masked***"
        },
    }


# ============================================================
# APOLLO TECHNOLOGY EXTRACTION
# ============================================================

def _walk_for_technology_objects(
    value,
    results=None,
    category_hint=""
):

    if results is None:
        results = []

    if isinstance(value, dict):

        for key, item in value.items():

            key_l = str(key).lower()

            new_category = category_hint

            if any(
                x in key_l
                for x in [
                    "category",
                    "categories"
                ]
            ):

                if isinstance(item, str):
                    new_category = item

            _walk_for_technology_objects(
                item,
                results,
                new_category
            )

        name = (
            value.get("name")
            or value.get("technology_name")
            or value.get("technology")
            or value.get("display_name")
        )

        uid = (
            value.get("uid")
            or value.get("technology_uid")
            or value.get("id")
        )

        category = (
            value.get("category")
            or value.get("technology_category")
            or category_hint
            or ""
        )

        if (
            isinstance(name, str)
            and name.strip()
        ):

            tech_context = any(
                k in value
                for k in [
                    "uid",
                    "technology_uid",
                    "technology_name",
                    "technology_category",
                    "category"
                ]
            )

            if tech_context:

                results.append({
                    "Technology":
                        name.strip(),

                    "Category":
                        (
                            str(category).strip()
                            if category
                            else "Uncategorized"
                        ),

                    "Technology UID":
                        (
                            str(uid).strip()
                            if uid
                            else ""
                        )
                })

    elif isinstance(value, list):

        for item in value:

            if (
                isinstance(item, str)
                and item.strip()
            ):

                results.append({
                    "Technology":
                        item.strip(),

                    "Category":
                        (
                            category_hint
                            or "Uncategorized"
                        ),

                    "Technology UID":
                        ""
                })

            else:

                _walk_for_technology_objects(
                    item,
                    results,
                    category_hint
                )

    return results


def extract_technology_rows(
    *apollo_payloads
):

    found = []

    for payload in apollo_payloads:

        if isinstance(payload, dict):

            found.extend(
                _walk_for_technology_objects(
                    payload,
                    []
                )
            )

            org = (
                payload.get("organization")
                or payload.get("org")
                or {}
            )

            if isinstance(org, dict):

                for key in [
                    "technology_names",
                    "technologies",
                    "current_technologies",
                    "technology_stack",
                    "tech_stack"
                ]:

                    value = org.get(key)

                    if isinstance(
                        value,
                        list
                    ):

                        for item in value:

                            if (
                                isinstance(item, str)
                                and item.strip()
                            ):

                                found.append({
                                    "Technology":
                                        item.strip(),

                                    "Category":
                                        "Uncategorized",

                                    "Technology UID":
                                        ""
                                })

    if not found:

        return pd.DataFrame(
            columns=[
                "Technology",
                "Category",
                "Technology UID"
            ]
        )

    df = pd.DataFrame(
        found
    )

    for col in [
        "Technology",
        "Category",
        "Technology UID"
    ]:

        if col not in df.columns:
            df[col] = ""

    df["Technology"] = (
        df["Technology"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df["Category"] = (
        df["Category"]
        .fillna("Uncategorized")
        .astype(str)
        .str.strip()
    )

    df["Technology UID"] = (
        df["Technology UID"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df = df[
        df["Technology"] != ""
    ].copy()

    df["_key"] = (
        df["Technology"].str.lower()
        + "|"
        + df["Category"].str.lower()
        + "|"
        + df["Technology UID"].str.lower()
    )

    df = (
        df
        .drop_duplicates("_key")
        .drop(columns=["_key"])
        .reset_index(drop=True)
    )

    return df


# ============================================================
# GENERAL HELPERS
# ============================================================

def _first_value(
    data,
    *keys,
    default="Not available"
):

    if not isinstance(data, dict):
        return default

    for key in keys:

        value = data.get(key)

        if value not in (
            None,
            "",
            [],
            {}
        ):

            return value

    return default


def _format_money(value):

    if value in (
        None,
        "",
        "Not available"
    ):

        return "Not available"

    try:

        return f"${float(value):,.0f}"

    except Exception:

        return str(value)


def _format_number(value):

    if value in (
        None,
        "",
        "Not available"
    ):

        return "Not available"

    try:

        return f"{int(float(value)):,}"

    except Exception:

        return str(value)


# ============================================================
# COMPANY 360
# ============================================================

def render_company_360(
    apollo_data,
    exact_name,
    domain,
    technology_data=None
):

    st.markdown(
        "## 🏢 Company 360"
    )

    st.caption(
        "Company intelligence is driven by the selected "
        "Lusha company/domain. Apollo provides company "
        "enrichment and Lusha provides IT-person discovery."
    )

    org = {}

    if isinstance(
        apollo_data,
        dict
    ):

        org = (
            apollo_data.get("organization")
            or apollo_data.get("org")
            or apollo_data
        )

        if not isinstance(
            org,
            dict
        ):

            org = {}

    employee_count = _first_value(
        org,
        "estimated_num_employees",
        "num_employees",
        "employee_count",
    )

    industry = _first_value(
        org,
        "industry"
    )

    revenue = _first_value(
        org,
        "annual_revenue",
        "revenue",
        "estimated_annual_revenue",
    )

    founded = _first_value(
        org,
        "founded_year",
        "year_founded"
    )

    phone = _first_value(
        org,
        "phone",
        "corporate_phone"
    )

    website = _first_value(
        org,
        "website_url",
        "website",
        default=(
            f"https://{domain}"
            if domain
            else "Not available"
        )
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Employees",
        _format_number(
            employee_count
        )
    )

    c2.metric(
        "Industry",
        industry
    )

    c3.metric(
        "Annual Revenue",
        _format_money(
            revenue
        )
    )

    c4.metric(
        "Founded",
        founded
    )

    # ========================================================
    # IDENTITY
    # ========================================================

    st.markdown(
        "### 🔎 Company Identity"
    )

    identity = pd.DataFrame(
        [
            [
                "Company",
                exact_name,
                "Lusha / Apollo"
            ],
            [
                "Domain",
                domain or "Not available",
                "Lusha"
            ],
            [
                "Apollo Organization ID",
                _first_value(
                    org,
                    "id",
                    "organization_id"
                ),
                "Apollo"
            ],
            [
                "Industry",
                industry,
                "Apollo"
            ],
            [
                "Website",
                website,
                "Apollo / Domain"
            ],
            [
                "Corporate Phone",
                phone,
                "Apollo"
            ],
        ],
        columns=[
            "Field",
            "Value",
            "Source"
        ]
    )

    st.dataframe(
        identity,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # LOCATIONS
    # ========================================================

    locations = org.get(
        "locations"
    )

    if not isinstance(
        locations,
        list
    ):

        locations = []

    headquarters = _first_value(
        org,
        "raw_address",
        "street_address",
        "headquarters_address",
        "city",
        default="Not available",
    )

    if locations:

        location_rows = []

        for loc in locations:

            if not isinstance(
                loc,
                dict
            ):
                continue

            location_rows.append({
                "Location": _first_value(
                    loc,
                    "raw_address",
                    "street_address",
                    "address"
                ),

                "City": _first_value(
                    loc,
                    "city"
                ),

                "State": _first_value(
                    loc,
                    "state",
                    "state_name"
                ),

                "Country": _first_value(
                    loc,
                    "country",
                    "country_name"
                ),
            })

        if location_rows:

            st.markdown(
                "### 📍 Locations"
            )

            st.dataframe(
                pd.DataFrame(
                    location_rows
                ),
                use_container_width=True,
                hide_index=True
            )

    else:

        st.markdown(
            "### 📍 Headquarters"
        )

        st.info(
            str(headquarters)
        )

    # ========================================================
    # FUNDING
    # ========================================================

    st.markdown(
        "### 💰 Corporate & Funding"
    )

    funding = (
        org.get("funding_events")
        or org.get("funding_rounds")
        or []
    )

    if (
        isinstance(funding, list)
        and funding
    ):

        funding_rows = []

        for item in funding:

            if not isinstance(
                item,
                dict
            ):
                continue

            funding_rows.append({
                "Round": _first_value(
                    item,
                    "type",
                    "round",
                    "name"
                ),

                "Amount": _format_money(
                    _first_value(
                        item,
                        "amount",
                        "amount_usd",
                        default="Not available"
                    )
                ),

                "Date": _first_value(
                    item,
                    "date",
                    "announced_date"
                ),

                "Investors": _first_value(
                    item,
                    "investors",
                    "investor_names"
                ),
            })

        if funding_rows:

            st.dataframe(
                pd.DataFrame(
                    funding_rows
                ),
                use_container_width=True,
                hide_index=True
            )

    else:

        st.info(
            "No funding-round data returned by Apollo "
            "for this company."
        )

    parent = (
        org.get(
            "owned_by_organization"
        )
        or org.get(
            "parent_organization"
        )
    )

    ultimate_parent = org.get(
        "ultimate_parent_organization"
    )

    subsidiaries = (
        org.get(
            "suborganizations"
        )
        or []
    )

    hierarchy = pd.DataFrame(
        [
            [
                "Immediate Parent",
                (
                    parent.get("name")
                    if isinstance(
                        parent,
                        dict
                    )
                    else (
                        parent
                        or "Not available"
                    )
                )
            ],

            [
                "Ultimate Parent",
                (
                    ultimate_parent.get("name")
                    if isinstance(
                        ultimate_parent,
                        dict
                    )
                    else (
                        ultimate_parent
                        or "Not available"
                    )
                )
            ],

            [
                "Direct Subsidiaries",
                (
                    len(subsidiaries)
                    if isinstance(
                        subsidiaries,
                        list
                    )
                    else 0
                )
            ],
        ],
        columns=[
            "Relationship",
            "Value"
        ]
    )

    st.dataframe(
        hierarchy,
        use_container_width=True,
        hide_index=True
    )

    # ========================================================
    # TECHNOLOGY
    # ========================================================

    st.markdown(
        "### 💻 Technology Intelligence"
    )

    tech_df = (
        technology_data
        if isinstance(
            technology_data,
            pd.DataFrame
        )
        else extract_technology_rows(
            apollo_data
        )
    )

    if not tech_df.empty:

        t1, t2 = st.columns(2)

        t1.metric(
            "Technologies Detected",
            f"{len(tech_df):,}"
        )

        t2.metric(
            "Technology Categories",
            f"{tech_df['Category'].replace('', 'Uncategorized').nunique():,}"
        )

        st.dataframe(
            tech_df.sort_values(
                [
                    "Category",
                    "Technology"
                ]
            ),
            use_container_width=True,
            hide_index=True
        )

        category_counts = (
            tech_df
            .assign(
                Category=tech_df[
                    "Category"
                ].replace(
                    "",
                    "Uncategorized"
                )
            )
            .groupby(
                "Category"
            )
            .size()
            .reset_index(
                name="Count"
            )
            .sort_values(
                "Count",
                ascending=False
            )
        )

        st.markdown(
            "#### Technology Categories"
        )

        st.dataframe(
            category_counts,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.warning(
            "Apollo did not return technology-stack fields "
            "in the organization payload. The app will attempt "
            "Apollo Complete Organization Info when an organization "
            "ID is available."
        )

    # ========================================================
    # IT PERSONA SUMMARY
    # ========================================================

    st.markdown(
        "### 👥 IT Personas"
    )

    personas_df = st.session_state.get(
        "lusha_it_personas"
    )

    persona_company = st.session_state.get(
        "lusha_persona_company"
    )

    if (
        isinstance(
            personas_df,
            pd.DataFrame
        )
        and persona_company == exact_name
    ):

        if personas_df.empty:

            st.warning(
                "No IT personas were found for this company."
            )

        else:

            p1, p2 = st.columns(2)

            p1.metric(
                "Qualified IT Personas",
                f"{len(personas_df):,}"
            )

            p2.metric(
                "Persona Types",
                f"{personas_df['Persona'].nunique():,}"
            )

            st.dataframe(
                personas_df,
                use_container_width=True,
                hide_index=True
            )

    else:

        st.info(
            "Click **3️⃣ Fetch IT Personas from Lusha** below "
            "to retrieve and classify contacts."
        )

    # ========================================================
    # SOURCE STATUS
    # ========================================================

    st.markdown(
        "### 📚 Source Status"
    )

    source_status = pd.DataFrame(
        [
            [
                "Lusha",
                "Company resolution",
                "Active"
            ],
            [
                "Lusha",
                "IT persona / contact discovery",
                "Active"
            ],
            [
                "Apollo",
                "Organization enrichment",
                "Active"
            ],
            [
                "Tofler",
                "Indian corporate / financial data",
                "API not configured"
            ],
            [
                "Zauba / MCA-derived",
                "Corporate registry data",
                "API not configured"
            ],
        ],
        columns=[
            "Source",
            "Data Area",
            "Status"
        ]
    )

    st.dataframe(
        source_status,
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# BULK HELPERS
# ============================================================

def clean_domain(value):

    if value is None:
        return ""

    value = str(value).strip()

    if not value or value.lower() in {
        "nan",
        "none",
        "null"
    }:
        return ""

    value = re.sub(
        r"^https?://",
        "",
        value,
        flags=re.IGNORECASE
    )

    value = (
        value
        .split("/")[0]
        .split("?")[0]
        .split("#")[0]
    )

    value = value.strip().lower()

    value = value.removeprefix(
        "www."
    )

    return value


def first_nonempty(
    *values,
    default=""
):

    for value in values:

        if value not in (
            None,
            "",
            [],
            {},
            "nan"
        ):

            return value

    return default


def flatten_apollo_company(
    apollo_json,
    input_company="",
    input_domain=""
):

    org = {}

    if isinstance(
        apollo_json,
        dict
    ):

        org = (
            apollo_json.get(
                "organization"
            )
            or apollo_json.get(
                "org"
            )
            or apollo_json
        )

        if not isinstance(
            org,
            dict
        ):

            org = {}

    domain = clean_domain(
        first_nonempty(
            org.get("primary_domain"),
            org.get("domain"),
            org.get("website_url"),
            input_domain,
        )
    )

    linkedin = first_nonempty(
        org.get("linkedin_url"),
        org.get("linkedin_company_url"),
    )

    return {

        "Input Company":
            input_company,

        "Input Domain":
            input_domain,

        "Company":
            first_nonempty(
                org.get("name"),
                input_company,
                default="Not available"
            ),

        "Domain":
            domain or "Not available",

        "Apollo Organization ID":
            first_nonempty(
                org.get("id"),
                org.get("organization_id"),
                default="Not available"
            ),

        "Industry":
            first_nonempty(
                org.get("industry"),
                default="Not available"
            ),

        "Employees":
            first_nonempty(
                org.get(
                    "estimated_num_employees"
                ),
                org.get(
                    "num_employees"
                ),
                default="Not available"
            ),

        "Annual Revenue":
            first_nonempty(
                org.get("annual_revenue"),
                org.get(
                    "estimated_annual_revenue"
                ),
                org.get("revenue"),
                default="Not available"
            ),

        "Founded":
            first_nonempty(
                org.get("founded_year"),
                org.get("year_founded"),
                default="Not available"
            ),

        "Country":
            first_nonempty(
                org.get("country"),
                org.get("country_name"),
                default="Not available"
            ),

        "City":
            first_nonempty(
                org.get("city"),
                default="Not available"
            ),

        "State":
            first_nonempty(
                org.get("state"),
                org.get("state_name"),
                default="Not available"
            ),

        "Corporate Phone":
            first_nonempty(
                org.get("phone"),
                org.get("corporate_phone"),
                default="Not available"
            ),

        "Website":
            first_nonempty(
                org.get("website_url"),
                org.get("website"),
                default=(
                    f"https://{domain}"
                    if domain
                    else "Not available"
                )
            ),

        "LinkedIn Company":
            linkedin or "Not available",

        "Technology Count":
            0,

        "Technologies":
            "Not available",

        "Employee Growth":
            first_nonempty(
                org.get(
                    "employee_growth_rate"
                ),
                org.get(
                    "employee_growth"
                ),
                default="Not available"
            ),

        "Funding":
            first_nonempty(
                org.get("total_funding"),
                org.get(
                    "total_funding_amount"
                ),
                default="Not available"
            ),

        "Parent Company": (
            org.get(
                "owned_by_organization",
                {}
            ).get("name")
            if isinstance(
                org.get(
                    "owned_by_organization"
                ),
                dict
            )
            else first_nonempty(
                org.get(
                    "parent_organization"
                ),
                default="Not available"
            )
        ) or "Not available",

        "Data Source":
            "Apollo",

        "Status":
            (
                "Enriched"
                if org
                else
                "No Apollo organization returned"
            ),

        "Error":
            "",
    }


def resolve_lusha_company_for_bulk(
    api_key,
    company_name
):

    if not company_name.strip():

        return (
            None,
            "Company name is empty"
        )

    try:

        response = find_companies(
            api_key,
            company_name.strip()
        )

    except requests.RequestException as e:

        return (
            None,
            f"Lusha connection error: {e}"
        )

    if response.status_code != 200:

        try:
            body = response.json()

        except Exception:
            body = response.text[:300]

        return (
            None,
            f"Lusha HTTP {response.status_code}: {body}"
        )

    try:

        values = response.json().get(
            "values",
            []
        )

    except Exception:

        values = []

    if not values:

        return (
            None,
            "No Lusha company match"
        )

    target = company_name.strip().lower()

    exact = next(
        (
            x
            for x in values
            if str(
                x.get("name", "")
            ).strip().lower()
            == target
        ),
        values[0]
    )

    domain = clean_domain(
        first_nonempty(
            exact.get(
                "domains_homepage"
            ),
            exact.get(
                "fqdn"
            ),
            exact.get(
                "domain"
            ),
        )
    )

    return {
        "name":
            exact.get(
                "name",
                company_name
            ),

        "domain":
            domain,

        "lusha_id":
            exact.get(
                "id",
                ""
            )
    }, ""


def bulk_apollo_enrich(
    api_key,
    domain,
    company_name=""
):

    try:

        response, request_info = (
            apollo_org_enrich(
                api_key,
                domain,
                company_name
            )
        )

        return (
            response,
            request_info
        )

    except requests.RequestException as e:

        return (
            None,
            {
                "error": str(e)
            }
        )


# ============================================================
# BULK FILE PREPARATION
# ============================================================

def prepare_bulk_dataframe(
    uploaded_file
):

    name = str(
        getattr(
            uploaded_file,
            "name",
            ""
        )
    ).lower()

    if name.endswith(".csv"):

        uploaded_file.seek(0)

        raw = uploaded_file.read()

        if not raw:

            raise ValueError(
                "The uploaded CSV is empty."
            )

        last_error = None
        df = None
        text = ""

        for encoding in (
            "utf-8-sig",
            "utf-8",
            "cp1252",
            "latin1"
        ):

            try:

                text = raw.decode(
                    encoding
                )

                from io import StringIO

                df = pd.read_csv(
                    StringIO(text),
                    sep=None,
                    engine="python",
                    dtype=str,
                    keep_default_na=False,
                )

                break

            except Exception as exc:

                last_error = exc

        if df is None:

            raise ValueError(
                f"Could not parse CSV: {last_error}"
            )

        if len(df.columns) == 1:

            first_col = str(
                df.columns[0]
            )

            for sep in [
                ",",
                ";",
                "\t",
                "|"
            ]:

                if (
                    sep in first_col
                    or any(
                        sep in str(v)
                        for v in df.iloc[
                            :10,
                            0
                        ].tolist()
                    )
                ):

                    try:

                        df = pd.read_csv(
                            StringIO(text),
                            sep=sep,
                            dtype=str,
                            keep_default_na=False,
                        )

                        if len(
                            df.columns
                        ) > 1:

                            break

                    except Exception:
                        pass

    else:

        uploaded_file.seek(0)

        df = pd.read_excel(
            uploaded_file,
            dtype=str
        )

    if df is None or df.empty:

        raise ValueError(
            "The uploaded file is empty."
        )

    df.columns = [
        str(c)
        .replace("\ufeff", "")
        .strip()
        for c in df.columns
    ]

    normalized = {
        re.sub(
            r"[\s_\-]+",
            " ",
            str(c).strip().lower()
        ).strip(): c
        for c in df.columns
    }

    company_col = None
    domain_col = None

    company_candidates = [
        "company",
        "company name",
        "organization",
        "organization name",
        "account",
        "account name",
        "companyname"
    ]

    domain_candidates = [
        "domain",
        "company domain",
        "website",
        "website domain",
        "url",
        "company url",
        "company website",
        "companydomain"
    ]

    for candidate in company_candidates:

        if candidate in normalized:

            company_col = normalized[
                candidate
            ]

            break

    for candidate in domain_candidates:

        if candidate in normalized:

            domain_col = normalized[
                candidate
            ]

            break

    if company_col is None:

        for norm_name, original in normalized.items():

            if (
                "company" in norm_name
                or "organization" in norm_name
            ):

                company_col = original

                break

    if domain_col is None:

        for norm_name, original in normalized.items():

            if (
                "domain" in norm_name
                or "website" in norm_name
                or norm_name == "url"
            ):

                domain_col = original

                break

    if (
        company_col is None
        and domain_col is None
    ):

        raise ValueError(
            "Could not find a Company or Domain column. "
            f"Detected columns: "
            f"{', '.join(map(str, df.columns))}. "
            "Use headers like Company, Company Name, "
            "Domain, Website or URL."
        )

    work = pd.DataFrame(
        index=df.index
    )

    if company_col is not None:

        work["Input Company"] = (
            df[company_col]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    else:

        work["Input Company"] = ""

    if domain_col is not None:

        work["Input Domain"] = (
            df[domain_col]
            .fillna("")
            .astype(str)
            .map(clean_domain)
        )

    else:

        work["Input Domain"] = ""

    # Preserve additional columns
    for col in df.columns:

        if col in {
            company_col,
            domain_col
        }:
            continue

        safe = (
            str(col)
            .replace("\ufeff", "")
            .strip()
        )

        if (
            safe
            and safe not in work.columns
        ):

            work[safe] = df[
                col
            ].fillna("")

    work["Input Company"] = (
        work["Input Company"]
        .replace({
            "nan": "",
            "None": "",
            "NaN": ""
        })
        .fillna("")
        .astype(str)
        .str.strip()
    )

    work["Input Domain"] = (
        work["Input Domain"]
        .replace({
            "nan": "",
            "None": "",
            "NaN": ""
        })
        .fillna("")
        .astype(str)
        .map(clean_domain)
    )

    work["_dedupe_key"] = work.apply(
        lambda r:
            r["Input Domain"]
            if r["Input Domain"]
            else
            r["Input Company"]
            .strip()
            .lower(),
        axis=1
    )

    work = (
        work[
            work["_dedupe_key"] != ""
        ]
        .drop_duplicates(
            "_dedupe_key",
            keep="first"
        )
        .drop(
            columns=["_dedupe_key"]
        )
        .reset_index(
            drop=True
        )
    )

    if work.empty:

        raise ValueError(
            "No usable company/domain rows "
            "were found in the uploaded file."
        )

    return work


# ============================================================
# BULK PROCESSING
# ============================================================

def run_bulk_processing(
    base_df,
    lusha_key,
    apollo_key,
    selected_companies=None,
    fetch_personas=True,
    persona_max_pages=5,
    persona_page_size=50,
    progress_callback=None
):

    rows = []

    total = len(
        base_df
    )

    for idx, (
        _,
        source_row
    ) in enumerate(
        base_df.iterrows(),
        start=1
    ):

        input_company = str(
            source_row.get(
                "Input Company",
                ""
            )
            or ""
        ).strip()

        input_domain = clean_domain(
            source_row.get(
                "Input Domain",
                ""
            )
        )

        resolved_name = input_company

        domain = input_domain

        lusha_used = False

        # ====================================================
        # USE EXPLICIT USER SELECTION
        # ====================================================

        if (
            selected_companies
            and input_company
            in selected_companies
        ):

            selection = (
                selected_companies[
                    input_company
                ]
            )

            resolved_name = (
                selection.get(
                    "name"
                )
                or input_company
            )

            domain = clean_domain(
                selection.get(
                    "domain",
                    ""
                )
            )

            lusha_used = bool(
                selection.get(
                    "lusha_used",
                    False
                )
            )

        # ====================================================
        # RESOLVE DOMAIN THROUGH LUSHA IF NECESSARY
        # ====================================================

        if not domain:

            if not lusha_key.strip():

                result = {
                    **{
                        c: source_row.get(
                            c,
                            ""
                        )
                        for c in base_df.columns
                    },

                    "Company":
                        input_company
                        or "Not available",

                    "Domain":
                        "Not available",

                    "Data Source":
                        "Lusha/Apollo",

                    "Status":
                        "Skipped",

                    "Error":
                        "Domain missing and "
                        "Lusha API key is not configured.",
                }

                rows.append(
                    result
                )

                if progress_callback:
                    progress_callback(
                        idx,
                        total
                    )

                continue

            resolved, error = (
                resolve_lusha_company_for_bulk(
                    lusha_key,
                    input_company
                )
            )

            lusha_used = True

            if resolved:

                resolved_name = (
                    resolved["name"]
                    or input_company
                )

                domain = resolved[
                    "domain"
                ]

            else:

                result = {
                    **{
                        c: source_row.get(
                            c,
                            ""
                        )
                        for c in base_df.columns
                    },

                    "Company":
                        input_company
                        or "Not available",

                    "Domain":
                        "Not available",

                    "Data Source":
                        "Lusha",

                    "Status":
                        "Failed",

                    "Error":
                        error,
                }

                rows.append(
                    result
                )

                if progress_callback:
                    progress_callback(
                        idx,
                        total
                    )

                continue

        if not domain:

            result = {
                **{
                    c: source_row.get(
                        c,
                        ""
                    )
                    for c in base_df.columns
                },

                "Company":
                    resolved_name
                    or "Not available",

                "Domain":
                    "Not available",

                "Data Source":
                    "Lusha",

                "Status":
                    "Failed",

                "Error":
                    "No domain found for this company.",
            }

            rows.append(
                result
            )

            if progress_callback:
                progress_callback(
                    idx,
                    total
                )

            continue

        # ====================================================
        # APOLLO
        # ====================================================

        response, request_info = (
            bulk_apollo_enrich(
                apollo_key,
                domain,
                resolved_name
            )
        )

        if (
            response is not None
            and response.status_code == 200
        ):

            try:

                apollo_json = (
                    response.json()
                )

            except ValueError:

                apollo_json = {}

            tech_df = (
                extract_technology_rows(
                    apollo_json
                )
            )

            org = (
                apollo_json.get(
                    "organization"
                )
                if isinstance(
                    apollo_json,
                    dict
                )
                else None
            )

            org = (
                org
                if isinstance(
                    org,
                    dict
                )
                else {}
            )

            org_id = first_nonempty(
                org.get("id"),
                org.get(
                    "organization_id"
                ),
                default=""
            )

            tech_source = (
                "Organization Enrichment"
            )

            # =================================================
            # APOLLO COMPLETE ORG FOR TECHNOLOGY
            # =================================================

            if (
                tech_df.empty
                and org_id
            ):

                try:

                    complete_response, _ = (
                        apollo_complete_org(
                            apollo_key,
                            org_id
                        )
                    )

                    if (
                        complete_response
                        is not None
                        and complete_response.status_code
                        == 200
                    ):

                        complete_json = (
                            complete_response.json()
                        )

                        tech_df = (
                            extract_technology_rows(
                                apollo_json,
                                complete_json
                            )
                        )

                        tech_source = (
                            "Apollo Complete "
                            "Organization Info"
                        )

                        if isinstance(
                            complete_json,
                            dict
                        ):

                            apollo_json[
                                "_complete_organization"
                            ] = complete_json

                except Exception:
                    pass

            # =================================================
            # LUSHA IT PERSONAS
            # =================================================

            persona_count = 0
            persona_names = ""
            persona_titles = ""
            persona_types = ""
            persona_error = ""

            if (
                fetch_personas
                and lusha_key.strip()
            ):

                try:

                    (
                        all_contacts_df,
                        qualified_df,
                        raw_contacts
                    ) = (
                        fetch_lusha_it_personas(
                            api_key=lusha_key,
                            exact_company_name=resolved_name,
                            company_domain=domain,
                            max_pages=persona_max_pages,
                            page_size=persona_page_size
                        )
                    )

                    persona_count = len(
                        qualified_df
                    )

                    if not qualified_df.empty:

                        persona_names = (
                            " | ".join(
                                qualified_df[
                                    "Name"
                                ]
                                .fillna("")
                                .astype(str)
                                .tolist()
                            )
                        )

                        persona_titles = (
                            " | ".join(
                                qualified_df[
                                    "Current Title"
                                ]
                                .fillna("")
                                .astype(str)
                                .tolist()
                            )
                        )

                        persona_types = (
                            " | ".join(
                                qualified_df[
                                    "Persona"
                                ]
                                .fillna("")
                                .astype(str)
                                .tolist()
                            )
                        )

                except Exception as persona_exc:

                    persona_error = str(
                        persona_exc
                    )

            # =================================================
            # FINAL RESULT
            # =================================================

            result = {
                **{
                    c: source_row.get(
                        c,
                        ""
                    )
                    for c in base_df.columns
                },

                **flatten_apollo_company(
                    apollo_json,
                    input_company,
                    input_domain
                ),

                "Lusha Resolved Name":
                    resolved_name,

                "Lusha Used":
                    (
                        "Yes"
                        if lusha_used
                        else "No"
                    ),

                "Technology Count":
                    len(tech_df),

                "Technologies":
                    (
                        ", ".join(
                            tech_df[
                                "Technology"
                            ].tolist()
                        )
                        if not tech_df.empty
                        else
                        "Not available"
                    ),

                "Technology Source":
                    (
                        tech_source
                        if not tech_df.empty
                        else
                        "Not available"
                    ),

                "IT Persona Count":
                    persona_count,

                "IT Persona Names":
                    (
                        persona_names
                        or "None"
                    ),

                "IT Persona Titles":
                    (
                        persona_titles
                        or "None"
                    ),

                "IT Persona Types":
                    (
                        persona_types
                        or "None"
                    ),

                "IT Persona Error":
                    persona_error,
            }

        else:

            status = (
                f"Apollo HTTP "
                f"{response.status_code}"
                if response is not None
                else
                "Apollo connection error"
            )

            if response is not None:

                try:

                    error_body = (
                        response.json()
                    )

                except Exception:

                    error_body = (
                        response.text[:500]
                    )

            else:

                error_body = (
                    request_info.get(
                        "error",
                        "Unknown error"
                    )
                    if isinstance(
                        request_info,
                        dict
                    )
                    else
                    "Unknown error"
                )

            result = {
                **{
                    c: source_row.get(
                        c,
                        ""
                    )
                    for c in base_df.columns
                },

                "Company":
                    resolved_name
                    or input_company
                    or "Not available",

                "Domain":
                    domain
                    or "Not available",

                "Lusha Resolved Name":
                    resolved_name,

                "Lusha Used":
                    (
                        "Yes"
                        if lusha_used
                        else "No"
                    ),

                "Data Source":
                    "Apollo",

                "Status":
                    "Failed",

                "Error":
                    f"{status}: {error_body}",
            }

            rows.append(
                result
            )

            if progress_callback:
                progress_callback(
                    idx,
                    total
                )

            if (
                response is not None
                and response.status_code
                in (401, 403)
            ):

                raise RuntimeError(
                    f"Apollo authentication/"
                    f"permission failure "
                    f"({response.status_code}). "
                    "Bulk processing stopped. "
                    "Check the Apollo API key "
                    "and API scope."
                )

            continue

        rows.append(
            result
        )

        if progress_callback:
            progress_callback(
                idx,
                total
            )

    return pd.DataFrame(
        rows
    )


# ============================================================
# BULK UI
# ============================================================

def render_bulk_processing():

    st.markdown(
        "## 📦 Bulk Company Processing"
    )

    st.caption(
        "Upload companies → resolve Lusha matches → "
        "select the exact company/domain → Apollo enrichment "
        "→ Lusha IT persona discovery."
    )

    template = pd.DataFrame({
        "Company": [
            "Denave",
            "Motherhood Hospital"
        ],

        "Domain": [
            "",
            ""
        ],
    })

    st.download_button(
        "⬇️ Download CSV template",
        template.to_csv(
            index=False
        ).encode("utf-8"),
        file_name=(
            "company_bulk_template.csv"
        ),
        mime="text/csv",
    )

    uploaded = st.file_uploader(
        "Upload company list",
        type=[
            "csv",
            "xlsx",
            "xls"
        ],
        key="bulk_company_uploader",
        help=(
            "Recommended column: Company. "
            "Domain is optional; you will select/"
            "confirm the exact domain before processing."
        ),
    )

    if not uploaded:

        st.info(
            "Upload your company list to start bulk processing."
        )

        return

    try:

        base_df = prepare_bulk_dataframe(
            uploaded
        )

    except Exception as e:

        st.error(
            f"Could not read the file: {e}"
        )

        return

    st.success(
        f"Loaded {len(base_df):,} unique companies."
    )

    st.dataframe(
        base_df.head(20),
        use_container_width=True,
        hide_index=True
    )

    st.info(
        "Lusha company resolution and IT-person "
        "discovery are enabled. Contact discovery "
        "uses Lusha prospecting credits."
    )

    # ========================================================
    # RESET STATE WHEN FILE CHANGES
    # ========================================================

    current_signature = (
        f"{uploaded.name}:"
        f"{len(base_df)}:"
        f"{','.join(base_df['Input Company'].astype(str).tolist()[:20])}"
    )

    if (
        st.session_state.get(
            "bulk_file_signature"
        )
        != current_signature
    ):

        st.session_state[
            "bulk_file_signature"
        ] = current_signature

        st.session_state[
            "bulk_matches"
        ] = {}

        st.session_state[
            "bulk_selections"
        ] = {}

        st.session_state[
            "bulk_results"
        ] = None

    # ========================================================
    # STEP 1
    # ========================================================

    st.markdown(
        "### 1️⃣ Find Lusha Company Matches"
    )

    if st.button(
        "🔎 Find Matches for All Companies",
        use_container_width=True,
    ):

        if not api_key.strip():

            st.error(
                "Enter your Lusha API key in the sidebar first."
            )

            return

        matches = {}
        errors = []

        progress = st.progress(
            0,
            text="Resolving companies..."
        )

        total = len(
            base_df
        )

        for i, input_company in enumerate(
            base_df[
                "Input Company"
            ].tolist(),
            start=1
        ):

            try:

                response = find_companies(
                    api_key,
                    input_company
                )

                if response.status_code == 200:

                    values = (
                        response.json()
                        .get(
                            "values",
                            []
                        )
                    )

                    matches[
                        input_company
                    ] = values

                    if not values:

                        errors.append(
                            f"{input_company}: "
                            "No Lusha company matches"
                        )

                else:

                    errors.append(
                        f"{input_company}: "
                        f"Lusha HTTP "
                        f"{response.status_code}"
                    )

            except requests.RequestException as e:

                errors.append(
                    f"{input_company}: {e}"
                )

            progress.progress(
                i / total,
                text=(
                    f"Resolving "
                    f"{i} / {total}"
                )
            )

        progress.empty()

        st.session_state[
            "bulk_matches"
        ] = matches

        st.session_state[
            "bulk_selections"
        ] = {}

        st.session_state[
            "bulk_results"
        ] = None

        st.session_state[
            "bulk_resolution_errors"
        ] = errors

    matches = st.session_state.get(
        "bulk_matches",
        {}
    )

    # ========================================================
    # STEP 2
    # ========================================================

    if matches:

        st.markdown(
            "### 2️⃣ Select the Exact Company / Domain"
        )

        st.info(
            "For every company, select the Lusha record "
            "you want. The selected domain will be used "
            "for Apollo. The selected exact company name "
            "will be used for Lusha contact discovery."
        )

        if st.session_state.get(
            "bulk_resolution_errors"
        ):

            with st.expander(
                "⚠️ Resolution warnings"
            ):

                for err in st.session_state[
                    "bulk_resolution_errors"
                ]:

                    st.write(err)

        selections = {}

        for row_index, (
            _,
            source_row
        ) in enumerate(
            base_df.iterrows()
        ):

            input_company = str(
                source_row.get(
                    "Input Company",
                    ""
                )
                or ""
            ).strip()

            row_matches = matches.get(
                input_company,
                []
            )

            input_domain = clean_domain(
                source_row.get(
                    "Input Domain",
                    ""
                )
            )

            st.markdown(
                f"#### {row_index + 1}. "
                f"{input_company}"
            )

            options = []
            option_meta = []

            if input_domain:

                options.append(
                    f"📄 Use uploaded domain: "
                    f"{input_domain}"
                )

                option_meta.append({
                    "name":
                        input_company,

                    "domain":
                        input_domain,

                    "lusha_used":
                        False,
                })

            for company in row_matches:

                name = company.get(
                    "name",
                    "Unknown"
                )

                company_domain = clean_domain(
                    company.get(
                        "domains_homepage"
                    )
                    or company.get(
                        "fqdn"
                    )
                    or company.get(
                        "domain"
                    )
                    or ""
                )

                has_contacts = company.get(
                    "has_prospecting_contacts",
                    False
                )

                options.append(
                    f"🏢 {name} | "
                    f"{company_domain or 'No domain'} | "
                    f"{'✅ Contacts available' if has_contacts else '❌ No contacts'}"
                )

                option_meta.append({
                    "name":
                        name,

                    "domain":
                        company_domain,

                    "lusha_used":
                        True,

                    "lusha_id":
                        company.get(
                            "id",
                            ""
                        ),

                    "has_contacts":
                        has_contacts,
                })

            # Manual option
            options.append(
                "✍️ Enter domain manually"
            )

            option_meta.append({
                "name":
                    input_company,

                "domain":
                    "",

                "lusha_used":
                    False,

                "manual_domain":
                    True,
            })

            selected_option = st.radio(
                "Select exact record / domain source",
                range(len(options)),
                format_func=lambda x,
                    options=options:
                    options[x],
                key=(
                    f"bulk_exact_company_"
                    f"{row_index}"
                ),
            )

            selected = dict(
                option_meta[
                    selected_option
                ]
            )

            if (
                selected.get(
                    "manual_domain"
                )
                or not selected.get(
                    "domain"
                )
            ):

                manual_key = (
                    f"bulk_manual_domain_"
                    f"{row_index}"
                )

                manual_value = st.text_input(
                    "Company Website / Domain "
                    "(required for Apollo)",
                    value=(
                        input_domain
                        if selected.get(
                            "manual_domain"
                        )
                        else ""
                    ),
                    placeholder="example.com",
                    key=manual_key,
                    help=(
                        "Enter the company's official "
                        "website domain."
                    ),
                )

                selected["domain"] = clean_domain(
                    manual_value
                )

                if selected["domain"]:

                    st.success(
                        f"Manual domain accepted: "
                        f"**{selected['domain']}**"
                    )

                else:

                    st.warning(
                        "Enter the official domain "
                        "before confirming."
                    )

            selections[
                input_company
            ] = selected

            st.caption(
                f"Selected → "
                f"**{selected['name']}** | "
                f"Domain → "
                f"**{selected['domain'] or 'Not available'}**"
            )

        st.session_state[
            "bulk_selections"
        ] = selections

        # ====================================================
        # STEP 3
        # ====================================================

        st.markdown("---")

        st.markdown(
            "### 3️⃣ Confirm Selections"
        )

        if selections:

            confirmation = pd.DataFrame([
                {
                    "Input Company":
                        company,

                    "Selected Company":
                        item.get(
                            "name",
                            ""
                        ),

                    "Selected Domain":
                        item.get(
                            "domain",
                            ""
                        ),

                    "Lusha Used":
                        (
                            "Yes"
                            if item.get(
                                "lusha_used"
                            )
                            else
                            "No"
                        ),
                }

                for company, item
                in selections.items()
            ])

            st.dataframe(
                confirmation,
                use_container_width=True,
                hide_index=True
            )

            # =================================================
            # PERSONA SETTINGS
            # =================================================

            st.markdown(
                "### 👥 Lusha IT Persona Fetch"
            )

            fetch_bulk_personas = st.checkbox(
                "Fetch IT personas from Lusha",
                value=True,
                help=(
                    "Fetch contacts from each exact selected "
                    "Lusha company and classify them locally "
                    "using the existing IT persona rules."
                ),
            )

            persona_max_pages = st.number_input(
                "Maximum Lusha contact pages per company",
                min_value=1,
                max_value=20,
                value=5,
                step=1,
                disabled=not fetch_bulk_personas,
            )

            persona_page_size = st.selectbox(
                "Contacts per Lusha page",
                [
                    25,
                    50,
                    100
                ],
                index=1,
                disabled=not fetch_bulk_personas,
            )

            if fetch_bulk_personas:

                st.warning(
                    "⚠️ IT-person fetching uses Lusha "
                    "prospecting/contact credits."
                )

            # =================================================
            # VALIDATION
            # =================================================

            can_run = bool(
                apollo_api_key.strip()
            )

            all_selected = (
                len(selections)
                == len(base_df)
            )

            missing_domains = [
                company
                for company, item
                in selections.items()
                if not clean_domain(
                    item.get(
                        "domain"
                    )
                )
            ]

            if not can_run:

                st.error(
                    "Enter your Apollo API key "
                    "before processing."
                )

            if (
                all_selected
                and missing_domains
            ):

                st.error(
                    "Domain is missing for: "
                    + ", ".join(
                        missing_domains
                    )
                )

            # =================================================
            # PROCESS
            # =================================================

            if st.button(
                "🚀 Confirm & Process Selected Companies",
                type="primary",
                use_container_width=True,
                disabled=(
                    not can_run
                    or not all_selected
                    or bool(missing_domains)
                ),
            ):

                progress = st.progress(
                    0,
                    text="Starting company enrichment..."
                )

                status_box = st.empty()

                def update_progress(
                    done,
                    total
                ):

                    pct = (
                        int(
                            done
                            / total
                            * 100
                        )
                        if total
                        else 100
                    )

                    progress.progress(
                        pct,
                        text=(
                            f"Processing "
                            f"{done:,} / "
                            f"{total:,} companies"
                        )
                    )

                    status_box.caption(
                        f"Completed: "
                        f"{done:,} of "
                        f"{total:,}"
                    )

                try:

                    results = (
                        run_bulk_processing(
                            base_df,
                            api_key,
                            apollo_api_key,
                            selected_companies=selections,
                            fetch_personas=(
                                fetch_bulk_personas
                            ),
                            persona_max_pages=int(
                                persona_max_pages
                            ),
                            persona_page_size=int(
                                persona_page_size
                            ),
                            progress_callback=(
                                update_progress
                            ),
                        )
                    )

                    st.session_state[
                        "bulk_results"
                    ] = results

                    progress.progress(
                        100,
                        text=(
                            "Bulk processing completed"
                        )
                    )

                    st.success(
                        "Bulk processing completed."
                    )

                except RuntimeError as e:

                    progress.empty()

                    st.error(
                        str(e)
                    )

                except Exception as e:

                    progress.empty()

                    st.error(
                        "Bulk processing stopped "
                        f"unexpectedly: {e}"
                    )

    # ========================================================
    # BULK RESULTS
    # ========================================================

    results = st.session_state.get(
        "bulk_results"
    )

    if (
        isinstance(
            results,
            pd.DataFrame
        )
        and not results.empty
    ):

        st.markdown(
            "### 📊 Bulk Results"
        )

        total = len(
            results
        )

        enriched = (
            int(
                (
                    results[
                        "Status"
                    ].astype(str)
                    == "Enriched"
                ).sum()
            )
            if "Status" in results
            else 0
        )

        failed = (
            int(
                (
                    results[
                        "Status"
                    ].astype(str)
                    .isin(
                        [
                            "Failed",
                            "Skipped"
                        ]
                    )
                ).sum()
            )
            if "Status" in results
            else 0
        )

        persona_total = (
            int(
                pd.to_numeric(
                    results.get(
                        "IT Persona Count",
                        pd.Series(
                            [0] * len(results)
                        )
                    ),
                    errors="coerce"
                )
                .fillna(0)
                .sum()
            )
        )

        x, y, z, w = st.columns(4)

        x.metric(
            "Processed",
            f"{total:,}"
        )

        y.metric(
            "Enriched",
            f"{enriched:,}"
        )

        z.metric(
            "Failed / Skipped",
            f"{failed:,}"
        )

        w.metric(
            "IT Personas",
            f"{persona_total:,}"
        )

        st.dataframe(
            results,
            use_container_width=True,
            hide_index=True
        )

        csv_bytes = (
            results
            .to_csv(
                index=False
            )
            .encode("utf-8")
        )

        st.download_button(
            "⬇️ Download Results CSV",
            csv_bytes,
            file_name=(
                "company_360_bulk_results.csv"
            ),
            mime="text/csv",
            use_container_width=True,
        )

        try:

            from io import BytesIO

            output = BytesIO()

            with pd.ExcelWriter(
                output,
                engine="openpyxl"
            ) as writer:

                results.to_excel(
                    writer,
                    index=False,
                    sheet_name="Company 360"
                )

            st.download_button(
                "⬇️ Download Results Excel",
                output.getvalue(),
                file_name=(
                    "company_360_bulk_results.xlsx"
                ),
                mime=(
                    "application/vnd.openxmlformats-"
                    "officedocument.spreadsheetml.sheet"
                ),
                use_container_width=True,
            )

        except Exception:

            st.caption(
                "Excel export unavailable in this environment; "
                "CSV export is available."
            )


# ============================================================
# MAIN UI
# ============================================================

st.title(
    "🎯 Domain-First IT Persona Finder"
)

st.caption(
    "Company name → exact Lusha company → domain → "
    "Company 360 intelligence → IT Personas"
)

st.info(
    "Company resolution happens first. After selecting "
    "the exact Lusha company, you can fetch its IT personas."
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header(
    "🔑 Lusha"
)

api_key = st.sidebar.text_input(
    "Lusha API Key",
    value=os.getenv(
        "LUSHA_API_KEY",
        ""
    ),
    type="password"
)

st.sidebar.header(
    "🚀 Apollo"
)

apollo_api_key = st.sidebar.text_input(
    "Apollo API Key",
    value=os.getenv(
        "APOLLO_API_KEY",
        ""
    ),
    type="password",
    help=(
        "Used for Apollo Organization Enrichment. "
        "Apollo people enrichment is not used."
    )
)


st.sidebar.header(
    "🏢 Company"
)

company_name = st.sidebar.text_input(
    "Company Name",
    placeholder="Motherhood Hospital"
)


st.sidebar.header(
    "📍 Optional Company Location"
)

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

        st.json(
            data
        )

        st.stop()

    st.session_state[
        "company_matches"
    ] = values

    # Clear old persona results
    st.session_state.pop(
        "lusha_all_contacts",
        None
    )

    st.session_state.pop(
        "lusha_it_personas",
        None
    )

    st.session_state.pop(
        "lusha_raw_contacts",
        None
    )

    st.success(
        f"Found {len(values)} company matches."
    )


# ============================================================
# DISPLAY COMPANY MATCHES
# ============================================================

if (
    "company_matches"
    in st.session_state
):

    matches = st.session_state[
        "company_matches"
    ]

    st.subheader(
        "🏢 Select the exact Lusha company"
    )

    labels = []

    for i, company in enumerate(
        matches
    ):

        name = company.get(
            "name",
            "Unknown"
        )

        domain = (
            company.get(
                "domains_homepage"
            )
            or company.get(
                "fqdn"
            )
            or company.get(
                "domain"
            )
            or ""
        )

        has_contacts = company.get(
            "has_prospecting_contacts",
            False
        )

        contact_status = (
            "✅ Prospecting contacts available"
            if has_contacts
            else
            "❌ No prospecting contacts"
        )

        labels.append(
            f"{name} | "
            f"{domain} | "
            f"{contact_status}"
        )

    selected_index = st.radio(
        "Company matches",
        range(len(labels)),
        format_func=lambda x:
            labels[x]
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
        or selected_company.get(
            "domain"
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

    st.markdown(
        "### Selected Company"
    )

    c1, c2, c3 = st.columns(3)

    c1.write(
        f"**Exact Lusha Name:** "
        f"{exact_name}"
    )

    c2.write(
        f"**Domain:** "
        f"{domain}"
    )

    c3.write(
        f"**Prospecting Contacts:** "
        f"{'YES' if has_contacts else 'NO'}"
    )

    st.session_state[
        "selected_company"
    ] = selected_company

    # ========================================================
    # COMPANY 360
    # ========================================================

    st.markdown(
        "### Step 2"
    )

    company360_button = st.button(
        "2️⃣ Load Company 360",
        type="primary",
        use_container_width=True,
    )

    if company360_button:

        if not apollo_api_key.strip():

            st.warning(
                "Apollo API key is not entered. "
                "Company 360 will still show the selected "
                "company, but Apollo enrichment cannot run."
            )

            st.session_state[
                "company360_data"
            ] = None

            st.session_state[
                "company360_tech"
            ] = pd.DataFrame()

            st.session_state[
                "company360_domain"
            ] = domain

            st.session_state[
                "company360_name"
            ] = exact_name

        else:

            with st.spinner(
                "Enriching company from Apollo..."
            ):

                try:

                    (
                        apollo_response,
                        apollo_request
                    ) = apollo_org_enrich(
                        apollo_api_key,
                        domain,
                        exact_name,
                    )

                except requests.RequestException as e:

                    st.error(
                        f"Apollo connection error: {e}"
                    )

                    apollo_response = None
                    apollo_request = None

            if apollo_response is not None:

                if (
                    apollo_response.status_code
                    == 200
                ):

                    try:

                        apollo_json = (
                            apollo_response.json()
                        )

                    except ValueError:

                        apollo_json = {}

                    technology_payload = (
                        apollo_json
                    )

                    org_for_id = (
                        apollo_json.get(
                            "organization"
                        )
                        if isinstance(
                            apollo_json,
                            dict
                        )
                        else {}
                    )

                    org_for_id = (
                        org_for_id
                        if isinstance(
                            org_for_id,
                            dict
                        )
                        else {}
                    )

                    org_id = (
                        org_for_id.get(
                            "id"
                        )
                        or org_for_id.get(
                            "organization_id"
                        )
                        or ""
                    )

                    tech_df = (
                        extract_technology_rows(
                            apollo_json
                        )
                    )

                    if (
                        tech_df.empty
                        and org_id
                    ):

                        with st.spinner(
                            "Checking Apollo Complete "
                            "Organization Info for technology stack..."
                        ):

                            try:

                                (
                                    complete_response,
                                    _
                                ) = (
                                    apollo_complete_org(
                                        apollo_api_key,
                                        org_id
                                    )
                                )

                                if (
                                    complete_response
                                    is not None
                                    and
                                    complete_response.status_code
                                    == 200
                                ):

                                    complete_json = (
                                        complete_response.json()
                                    )

                                    technology_payload = {
                                        **apollo_json,
                                        "_complete_organization":
                                            complete_json,
                                    }

                                    tech_df = (
                                        extract_technology_rows(
                                            apollo_json,
                                            complete_json
                                        )
                                    )

                                    st.session_state[
                                        "company360_complete_org"
                                    ] = complete_json

                                elif (
                                    complete_response
                                    is not None
                                    and
                                    complete_response.status_code
                                    in (
                                        401,
                                        403
                                    )
                                ):

                                    st.session_state[
                                        "company360_complete_org"
                                    ] = None

                                    st.info(
                                        f"Apollo Complete "
                                        f"Organization Info returned "
                                        f"HTTP {complete_response.status_code}; "
                                        "technology stack may require "
                                        "additional Apollo API scope."
                                    )

                            except Exception as tech_error:

                                st.session_state[
                                    "company360_complete_org"
                                ] = None

                                st.info(
                                    f"Technology lookup was unavailable: "
                                    f"{tech_error}"
                                )

                    st.session_state[
                        "company360_data"
                    ] = technology_payload

                    st.session_state[
                        "company360_tech"
                    ] = tech_df

                    st.session_state[
                        "company360_domain"
                    ] = domain

                    st.session_state[
                        "company360_name"
                    ] = exact_name

                    st.success(
                        "Apollo organization enrichment completed."
                    )

                else:

                    st.error(
                        f"Apollo returned HTTP "
                        f"{apollo_response.status_code}."
                    )

                    try:

                        st.json(
                            apollo_response.json()
                        )

                    except Exception:

                        st.code(
                            apollo_response.text
                        )

    if (
        st.session_state.get(
            "company360_name"
        )
        == exact_name
    ):

        render_company_360(
            st.session_state.get(
                "company360_data"
            ),
            exact_name,
            st.session_state.get(
                "company360_domain",
                domain
            ),
            st.session_state.get(
                "company360_tech"
            ),
        )

    # ========================================================
    # STEP 3 — ENABLED LUSHA IT PERSONAS
    # ========================================================

    st.markdown(
        "### Step 3 — IT Persona Fetch"
    )

    st.caption(
        "Contacts are fetched from the exact selected "
        "Lusha company. The existing Python persona rules "
        "then identify IT / Technology / Security contacts."
    )

    fetch_personas_button = st.button(
        "3️⃣ Fetch IT Personas from Lusha",
        type="primary",
        use_container_width=True,
    )

    if fetch_personas_button:

        if not api_key.strip():

            st.error(
                "Enter your Lusha API key in the sidebar."
            )

            st.stop()

        selected = st.session_state.get(
            "selected_company",
            {}
        )

        exact_name_for_contacts = (
            selected.get(
                "name"
            )
            or exact_name
        )

        domain_for_contacts = (
            selected.get(
                "domains_homepage"
            )
            or selected.get(
                "fqdn"
            )
            or selected.get(
                "domain"
            )
            or domain
            or ""
        )

        with st.spinner(
            "Fetching Lusha contacts and "
            "classifying IT personas..."
        ):

            try:

                (
                    all_contacts_df,
                    qualified_df,
                    raw_contacts
                ) = (
                    fetch_lusha_it_personas(
                        api_key=api_key,
                        exact_company_name=(
                            exact_name_for_contacts
                        ),
                        company_domain=(
                            domain_for_contacts
                        ),
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
                        ),
                        max_pages=5,
                        page_size=50,
                    )
                )

                st.session_state[
                    "lusha_all_contacts"
                ] = all_contacts_df

                st.session_state[
                    "lusha_it_personas"
                ] = qualified_df

                st.session_state[
                    "lusha_raw_contacts"
                ] = raw_contacts

                st.session_state[
                    "lusha_persona_company"
                ] = exact_name_for_contacts

                st.session_state[
                    "lusha_persona_domain"
                ] = domain_for_contacts

                st.success(
                    f"Lusha returned "
                    f"{len(all_contacts_df):,} contacts. "
                    f"{len(qualified_df):,} qualified "
                    "as IT personas."
                )

            except RuntimeError as e:

                st.error(
                    str(e)
                )

            except requests.RequestException as e:

                st.error(
                    f"Lusha connection error: {e}"
                )

            except Exception as e:

                st.error(
                    f"Unexpected Lusha persona error: {e}"
                )

    # ========================================================
    # PERSONA RESULTS
    # ========================================================

    it_personas_df = st.session_state.get(
        "lusha_it_personas"
    )

    if isinstance(
        it_personas_df,
        pd.DataFrame
    ):

        st.markdown(
            "### 🎯 Qualified IT Personas"
        )

        qualified_count = len(
            it_personas_df
        )

        if qualified_count == 0:

            st.warning(
                "No contacts matched the current "
                "IT persona rules."
            )

        else:

            all_contacts = (
                st.session_state.get(
                    "lusha_all_contacts"
                )
            )

            total_contacts = (
                len(all_contacts)
                if isinstance(
                    all_contacts,
                    pd.DataFrame
                )
                else 0
            )

            c1, c2, c3 = st.columns(3)

            c1.metric(
                "Contacts Found",
                f"{total_contacts:,}"
            )

            c2.metric(
                "IT Personas",
                f"{qualified_count:,}"
            )

            qualification_rate = (
                qualified_count
                / total_contacts
                * 100
                if total_contacts
                else 0
            )

            c3.metric(
                "Qualification Rate",
                f"{qualification_rate:.1f}%"
            )

            display_columns = [
                "Name",
                "Current Title",
                "Persona",
                "Department",
                "Seniority",
                "Company",
                "Employee City",
                "Employee State",
                "Employee Country",
                "LinkedIn",
                "LinkedIn ID",
                "Contact ID",
                "Reason",
            ]

            display_columns = [
                col
                for col in display_columns
                if col in it_personas_df.columns
            ]

            st.dataframe(
                it_personas_df[
                    display_columns
                ],
                use_container_width=True,
                hide_index=True
            )

            # =================================================
            # PERSONA CSV
            # =================================================

            csv_data = (
                it_personas_df
                .to_csv(
                    index=False
                )
                .encode("utf-8")
            )

            st.download_button(
                "⬇️ Download IT Personas CSV",
                csv_data,
                file_name=(
                    "lusha_it_personas.csv"
                ),
                mime="text/csv",
                use_container_width=True,
            )

            # =================================================
            # PERSONA EXCEL
            # =================================================

            try:

                from io import BytesIO

                output = BytesIO()

                with pd.ExcelWriter(
                    output,
                    engine="openpyxl"
                ) as writer:

                    it_personas_df.to_excel(
                        writer,
                        index=False,
                        sheet_name="IT Personas"
                    )

                st.download_button(
                    "⬇️ Download IT Personas Excel",
                    output.getvalue(),
                    file_name=(
                        "lusha_it_personas.xlsx"
                    ),
                    mime=(
                        "application/vnd.openxmlformats-"
                        "officedocument.spreadsheetml.sheet"
                    ),
                    use_container_width=True,
                )

            except Exception:

                st.caption(
                    "Excel export unavailable; "
                    "CSV export is available."
                )


# ============================================================
# BULK MODE
# ============================================================

st.divider()

render_bulk_processing()
