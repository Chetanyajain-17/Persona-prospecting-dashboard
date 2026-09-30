import os
import re
from io import BytesIO, StringIO

import pandas as pd
import requests
import streamlit as st


# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="SEA & India Company Intelligence",
    page_icon="🏢",
    layout="wide",
)

LUSHA_COMPANY_FILTER_URL = (
    "https://api.lusha.com/v3/companies/prospecting/filters/names"
)

APOLLO_ORG_ENRICH_URL = (
    "https://api.apollo.io/api/v1/organizations/enrich"
)


# ============================================================
# SUPPORTED COUNTRIES
# ============================================================

SUPPORTED_COUNTRIES = {
    "India": "IN",
    "Singapore": "SG",
    "Malaysia": "MY",
    "Vietnam": "VN",
    "Philippines": "PH",
}


COUNTRY_ALIASES = {
    "india": "India",
    "in": "India",

    "singapore": "Singapore",
    "sg": "Singapore",

    "malaysia": "Malaysia",
    "my": "Malaysia",

    "vietnam": "Vietnam",
    "viet nam": "Vietnam",
    "vn": "Vietnam",

    "philippines": "Philippines",
    "the philippines": "Philippines",
    "ph": "Philippines",
}


# ============================================================
# HTTP HELPERS
# ============================================================

def lusha_headers(api_key):
    return {
        "api_key": api_key.strip(),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def apollo_headers(api_key):
    return {
        "accept": "application/json",
        "x-api-key": api_key.strip(),
    }


# ============================================================
# GENERAL HELPERS
# ============================================================

def clean_domain(value):
    """
    Normalize:
        https://www.example.com/path
    into:
        example.com
    """

    if value is None:
        return ""

    value = str(value).strip()

    if not value:
        return ""

    if value.lower() in {
        "nan",
        "none",
        "null",
        "not available",
    }:
        return ""

    value = re.sub(
        r"^https?://",
        "",
        value,
        flags=re.IGNORECASE,
    )

    value = (
        value
        .split("/")[0]
        .split("?")[0]
        .split("#")[0]
        .strip()
        .lower()
    )

    value = re.sub(
        r":\d+$",
        "",
        value,
    )

    value = value.removeprefix("www.")

    return value


def first_nonempty(*values, default=""):
    for value in values:

        if value is None:
            continue

        if isinstance(value, str):
            value = value.strip()

            if not value:
                continue

        if value in ([], {}):
            continue

        return value

    return default


def safe_text(value, default="Not available"):
    value = first_nonempty(
        value,
        default=default,
    )

    if value is None:
        return default

    return str(value).strip() or default


def normalize_country(value):
    if value is None:
        return ""

    text = str(value).strip().lower()

    return COUNTRY_ALIASES.get(
        text,
        str(value).strip(),
    )


def normalize_phone(value):
    if value is None:
        return ""

    if isinstance(value, dict):

        value = first_nonempty(
            value.get("number"),
            value.get("raw_number"),
            value.get("sanitized_number"),
            value.get("phone"),
            value.get("value"),
            default="",
        )

    return str(value).strip()


# ============================================================
# LINKEDIN HELPERS
# ============================================================

def extract_linkedin_company_id(linkedin_url):
    """
    Extract a LinkedIn company identifier/slug from a company URL.

    Important:
    A LinkedIn URL slug is not necessarily the same thing as
    LinkedIn's internal numeric identifier. We therefore keep
    Apollo's linkedin_uid when available and only use the URL
    slug as a fallback.
    """

    if not linkedin_url:
        return ""

    text = str(linkedin_url).strip()

    # Numeric LinkedIn company URL
    match = re.search(
        r"linkedin\.com/company/(\d+)",
        text,
        re.IGNORECASE,
    )

    if match:
        return match.group(1)

    # Standard company slug
    match = re.search(
        r"linkedin\.com/company/([^/?#]+)",
        text,
        re.IGNORECASE,
    )

    if match:
        return match.group(1).strip()

    return ""


def normalize_linkedin_url(value):
    if not value:
        return ""

    value = str(value).strip()

    if not value:
        return ""

    if "linkedin.com/" not in value.lower():
        return value

    if not re.match(
        r"^https?://",
        value,
        re.IGNORECASE,
    ):
        value = "https://" + value

    return value.rstrip("/")


# ============================================================
# LUSHA COMPANY SEARCH
# ============================================================

def search_lusha_companies(
    api_key,
    company_name,
):
    """
    Search Lusha company records by company name.
    """

    if not api_key.strip():
        raise ValueError(
            "Lusha API key is missing."
        )

    if not company_name.strip():
        raise ValueError(
            "Company name is missing."
        )

    params = {
        "query": company_name.strip(),
    }

    response = requests.get(
        LUSHA_COMPANY_FILTER_URL,
        headers=lusha_headers(api_key),
        params=params,
        timeout=60,
    )

    if response.status_code != 200:

        try:
            body = response.json()
        except Exception:
            body = response.text[:1000]

        raise RuntimeError(
            f"Lusha returned HTTP "
            f"{response.status_code}: {body}"
        )

    try:
        data = response.json()
    except ValueError:
        raise RuntimeError(
            "Lusha returned invalid JSON."
        )

    values = data.get(
        "values",
        [],
    )

    if not isinstance(values, list):
        return []

    return values


# ============================================================
# LUSHA COMPANY NORMALIZATION
# ============================================================

def normalize_lusha_company(company):
    if not isinstance(company, dict):
        return None

    name = first_nonempty(
        company.get("name"),
        company.get("companyName"),
        default="",
    )

    domain = clean_domain(
        first_nonempty(
            company.get("domains_homepage"),
            company.get("fqdn"),
            company.get("domain"),
            company.get("website"),
            company.get("website_url"),
            default="",
        )
    )

    linkedin_url = normalize_linkedin_url(
        first_nonempty(
            company.get("linkedin_url"),
            company.get("linkedinUrl"),
            company.get("linkedin"),
            company.get("linkedin_company_url"),
            default="",
        )
    )

    linkedin_id = first_nonempty(
        company.get("linkedin_id"),
        company.get("linkedinId"),
        company.get("linkedin_uid"),
        default="",
    )

    if not linkedin_id:
        linkedin_id = extract_linkedin_company_id(
            linkedin_url
        )

    phone = normalize_phone(
        first_nonempty(
            company.get("phone"),
            company.get("phone_number"),
            company.get("corporate_phone"),
            company.get("telephone"),
            default="",
        )
    )

    return {
        "Lusha Company ID": first_nonempty(
            company.get("id"),
            company.get("companyId"),
            default="",
        ),

        "Lusha Company Name": name,

        "Lusha Domain": domain,

        "Lusha LinkedIn URL": linkedin_url,

        "Lusha LinkedIn ID": str(
            linkedin_id
        ).strip(),

        "Lusha Boardline": phone,

        "Lusha Raw": company,
    }


# ============================================================
# LUSHA MATCH RANKING
# ============================================================

def score_lusha_company(
    company,
    input_company,
    input_domain="",
    country="",
):
    """
    Score candidate records only for selecting a likely exact
    company. This is not an API confidence score.
    """

    score = 0

    normalized = normalize_lusha_company(
        company
    )

    if not normalized:
        return 0

    target_name = (
        input_company
        .strip()
        .lower()
    )

    candidate_name = (
        normalized["Lusha Company Name"]
        .strip()
        .lower()
    )

    target_domain = clean_domain(
        input_domain
    )

    candidate_domain = clean_domain(
        normalized["Lusha Domain"]
    )

    # Exact domain is strongest
    if (
        target_domain
        and candidate_domain
        and target_domain == candidate_domain
    ):
        score += 100

    # Exact company name
    if (
        target_name
        and candidate_name == target_name
    ):
        score += 50

    # Name contains target
    elif (
        target_name
        and target_name in candidate_name
    ):
        score += 20

    # Country information if returned
    candidate_country = normalize_country(
        first_nonempty(
            company.get("country"),
            company.get("country_name"),
            default="",
        )
    )

    if (
        country
        and candidate_country
        and candidate_country.lower()
        == normalize_country(country).lower()
    ):
        score += 20

    return score


# ============================================================
# APOLLO ORGANIZATION ENRICHMENT
# ============================================================

def apollo_organization_enrich(
    api_key,
    domain="",
    company_name="",
):
    """
    Apollo company-level enrichment.

    Domain is preferred because it is less ambiguous than
    company name.
    """

    if not api_key.strip():
        raise ValueError(
            "Apollo API key is missing."
        )

    domain = clean_domain(domain)

    if not domain and not company_name.strip():
        raise ValueError(
            "Apollo requires a company domain or company name."
        )

    params = {}

    if domain:
        params["domain"] = domain

    if company_name.strip():
        params["name"] = company_name.strip()

    response = requests.get(
        APOLLO_ORG_ENRICH_URL,
        headers=apollo_headers(api_key),
        params=params,
        timeout=60,
    )

    return response


# ============================================================
# RECURSIVE FIELD SEARCH
# ============================================================

def recursive_find_values(
    value,
    wanted_keys,
    results=None,
):
    """
    Find values anywhere inside nested Apollo/Lusha JSON.

    Useful because API response structures can differ.
    """

    if results is None:
        results = []

    wanted_keys = {
        str(x).lower()
        for x in wanted_keys
    }

    if isinstance(value, dict):

        for key, item in value.items():

            key_lower = str(key).lower()

            if key_lower in wanted_keys:

                if item not in (
                    None,
                    "",
                    [],
                    {},
                ):
                    results.append(item)

            recursive_find_values(
                item,
                wanted_keys,
                results,
            )

    elif isinstance(value, list):

        for item in value:

            recursive_find_values(
                item,
                wanted_keys,
                results,
            )

    return results


# ============================================================
# APOLLO ORGANIZATION EXTRACTION
# ============================================================

def get_apollo_org(apollo_json):

    if not isinstance(
        apollo_json,
        dict,
    ):
        return {}

    org = (
        apollo_json.get("organization")
        or apollo_json.get("org")
    )

    if isinstance(org, dict):
        return org

    return apollo_json


def extract_company_data(
    apollo_json,
    lusha_company=None,
    input_company="",
    input_country="",
    input_domain="",
):
    """
    Create a single normalized company-level record.
    """

    org = get_apollo_org(
        apollo_json
    )

    lusha = (
        normalize_lusha_company(
            lusha_company
        )
        if isinstance(
            lusha_company,
            dict,
        )
        else {}
    )

    if not isinstance(lusha, dict):
        lusha = {}

    # --------------------------------------------------------
    # COMPANY NAME
    # --------------------------------------------------------

    company_name = first_nonempty(
        org.get("name"),
        lusha.get("Lusha Company Name"),
        input_company,
        default="Not available",
    )

    # --------------------------------------------------------
    # DOMAIN / WEBSITE
    # --------------------------------------------------------

    domain = clean_domain(
        first_nonempty(
            org.get("primary_domain"),
            org.get("domain"),
            org.get("website_domain"),
            lusha.get("Lusha Domain"),
            input_domain,
            default="",
        )
    )

    website = first_nonempty(
        org.get("website_url"),
        org.get("website"),
        org.get("website_domain"),
        default="",
    )

    if not website and domain:
        website = f"https://{domain}"

    # --------------------------------------------------------
    # LINKEDIN
    # --------------------------------------------------------

    linkedin_url = normalize_linkedin_url(
        first_nonempty(
            org.get("linkedin_url"),
            org.get("linkedin_company_url"),
            org.get("linkedin"),
            lusha.get("Lusha LinkedIn URL"),
            default="",
        )
    )

    linkedin_id = first_nonempty(
        org.get("linkedin_uid"),
        org.get("linkedin_id"),
        org.get("linkedin_company_id"),
        lusha.get("Lusha LinkedIn ID"),
        default="",
    )

    if not linkedin_id:
        linkedin_id = (
            extract_linkedin_company_id(
                linkedin_url
            )
        )

    # --------------------------------------------------------
    # BOARDLINE
    # --------------------------------------------------------

    boardline = normalize_phone(
        first_nonempty(
            org.get("phone"),
            org.get("corporate_phone"),
            org.get("primary_phone"),
            lusha.get("Lusha Boardline"),
            default="",
        )
    )

    # If Apollo primary_phone is an object,
    # normalize_phone() handles it.
    if not boardline:

        primary_phone = org.get(
            "primary_phone"
        )

        boardline = normalize_phone(
            primary_phone
        )

    # --------------------------------------------------------
    # EMPLOYEE SIZE
    # --------------------------------------------------------

    employee_size = first_nonempty(
        org.get("estimated_num_employees"),
        org.get("num_employees"),
        org.get("employee_count"),
        org.get("employees"),
        default="",
    )

    if isinstance(
        employee_size,
        dict,
    ):

        employee_size = first_nonempty(
            employee_size.get("value"),
            employee_size.get("count"),
            employee_size.get("estimated"),
            default="",
        )

    # --------------------------------------------------------
    # LOCATION
    # --------------------------------------------------------

    country = first_nonempty(
        org.get("country"),
        org.get("country_name"),
        input_country,
        default="Not available",
    )

    city = first_nonempty(
        org.get("city"),
        default="Not available",
    )

    state = first_nonempty(
        org.get("state"),
        org.get("state_name"),
        default="Not available",
    )

    # --------------------------------------------------------
    # IDs
    # --------------------------------------------------------

    apollo_org_id = first_nonempty(
        org.get("id"),
        org.get("organization_id"),
        default="",
    )

    lusha_company_id = lusha.get(
        "Lusha Company ID",
        "",
    )

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    if apollo_json:

        status = "Enriched"

    elif lusha_company:

        status = "Lusha Match Only"

    else:

        status = "Not Enriched"

    return {
        "Input Company":
            input_company,

        "Country":
            country,

        "Company":
            company_name,

        "Domain":
            domain or "Not available",

        "Website":
            website or "Not available",

        "Boardline":
            boardline or "Not available",

        "Employee Size":
            employee_size
            if employee_size not in (
                None,
                "",
            )
            else "Not available",

        "LinkedIn Company URL":
            linkedin_url
            or "Not available",

        "LinkedIn Company ID":
            str(linkedin_id).strip()
            if linkedin_id
            else "Not available",

        "Apollo Organization ID":
            apollo_org_id
            or "Not available",

        "Lusha Company ID":
            lusha_company_id
            or "Not available",

        "City":
            city,

        "State / Province":
            state,

        "Status":
            status,

        "Error":
            "",
    }


# ============================================================
# SINGLE COMPANY PROCESSING
# ============================================================

def process_company(
    company_name,
    country,
    lusha_api_key,
    apollo_api_key,
    supplied_domain="",
    selected_lusha_company=None,
):
    """
    Company-only enrichment.

    NO contact/person API is called here.
    """

    supplied_domain = clean_domain(
        supplied_domain
    )

    # --------------------------------------------------------
    # LUSHA RESOLUTION
    # --------------------------------------------------------

    lusha_company = selected_lusha_company

    if lusha_company is None:

        matches = search_lusha_companies(
            lusha_api_key,
            company_name,
        )

        if matches:

            # Try to find exact match
            target = company_name.strip().lower()

            exact = next(
                (
                    x
                    for x in matches
                    if str(
                        x.get("name", "")
                    )
                    .strip()
                    .lower()
                    == target
                ),
                None,
            )

            if exact:

                lusha_company = exact

            else:

                # Best scored match
                lusha_company = max(
                    matches,
                    key=lambda x:
                        score_lusha_company(
                            x,
                            company_name,
                            supplied_domain,
                            country,
                        ),
                )

    # --------------------------------------------------------
    # DETERMINE DOMAIN
    # --------------------------------------------------------

    normalized_lusha = (
        normalize_lusha_company(
            lusha_company
        )
        if lusha_company
        else {}
    )

    domain = clean_domain(
        first_nonempty(
            supplied_domain,
            normalized_lusha.get(
                "Lusha Domain",
                "",
            ),
            default="",
        )
    )

    # --------------------------------------------------------
    # APOLLO
    # --------------------------------------------------------

    apollo_json = {}

    if apollo_api_key.strip():

        response = apollo_organization_enrich(
            apollo_api_key,
            domain=domain,
            company_name=company_name,
        )

        if response.status_code == 200:

            try:
                apollo_json = response.json()

            except ValueError:
                raise RuntimeError(
                    "Apollo returned invalid JSON."
                )

        else:

            try:
                error_body = response.json()

            except Exception:
                error_body = response.text[:1000]

            # We still return Lusha-level data if Apollo fails.
            result = extract_company_data(
                {},
                lusha_company,
                company_name,
                country,
                domain,
            )

            result["Status"] = "Apollo Failed"
            result["Error"] = (
                f"Apollo HTTP "
                f"{response.status_code}: "
                f"{error_body}"
            )

            return result

    else:

        # Apollo is optional for Lusha-only information.
        apollo_json = {}

    return extract_company_data(
        apollo_json,
        lusha_company,
        company_name,
        country,
        domain,
    )


# ============================================================
# BULK FILE READER
# ============================================================

def read_uploaded_file(uploaded_file):

    filename = (
        str(
            getattr(
                uploaded_file,
                "name",
                "",
            )
        )
        .lower()
    )

    if filename.endswith(
        ".csv"
    ):

        uploaded_file.seek(0)

        raw = uploaded_file.read()

        if not raw:
            raise ValueError(
                "Uploaded CSV is empty."
            )

        encodings = [
            "utf-8-sig",
            "utf-8",
            "cp1252",
            "latin1",
        ]

        df = None
        last_error = None

        for encoding in encodings:

            try:

                text = raw.decode(
                    encoding
                )

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
                f"Could not parse CSV: "
                f"{last_error}"
            )

    else:

        uploaded_file.seek(0)

        df = pd.read_excel(
            uploaded_file,
            dtype=str,
        )

    if df.empty:
        raise ValueError(
            "Uploaded file is empty."
        )

    df.columns = [
        str(c)
        .replace("\ufeff", "")
        .strip()
        for c in df.columns
    ]

    return df


# ============================================================
# BULK COLUMN DETECTION
# ============================================================

def find_column(
    columns,
    candidates,
):
    normalized = {
        re.sub(
            r"[\s_\-]+",
            " ",
            str(c).lower().strip(),
        ): c
        for c in columns
    }

    for candidate in candidates:

        if candidate in normalized:
            return normalized[candidate]

    for normalized_name, original in normalized.items():

        for candidate in candidates:

            if candidate in normalized_name:
                return original

    return None


def prepare_bulk_dataframe(
    uploaded_file,
):
    df = read_uploaded_file(
        uploaded_file
    )

    company_col = find_column(
        df.columns,
        [
            "company",
            "company name",
            "organization",
            "organization name",
            "account",
            "account name",
        ],
    )

    country_col = find_column(
        df.columns,
        [
            "country",
            "company country",
            "location country",
        ],
    )

    domain_col = find_column(
        df.columns,
        [
            "domain",
            "company domain",
            "website",
            "website domain",
            "url",
            "company url",
            "company website",
        ],
    )

    if company_col is None:
        raise ValueError(
            "A Company column is required."
        )

    work = pd.DataFrame()

    work["Input Company"] = (
        df[company_col]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    if country_col:

        work["Input Country"] = (
            df[country_col]
            .fillna("")
            .astype(str)
            .str.strip()
            .map(normalize_country)
        )

    else:

        work["Input Country"] = ""

    if domain_col:

        work["Input Domain"] = (
            df[domain_col]
            .fillna("")
            .astype(str)
            .map(clean_domain)
        )

    else:

        work["Input Domain"] = ""

    # Preserve extra columns
    for col in df.columns:

        if col in {
            company_col,
            country_col,
            domain_col,
        }:
            continue

        safe = (
            str(col)
            .replace("\ufeff", "")
            .strip()
        )

        if safe and safe not in work.columns:

            work[safe] = (
                df[col]
                .fillna("")
                .astype(str)
            )

    work = work[
        work["Input Company"].str.strip()
        != ""
    ].copy()

    # Dedupe
    work["_dedupe"] = work.apply(
        lambda row:
            (
                row["Input Domain"]
                or (
                    row["Input Company"]
                    .strip()
                    .lower()
                    + "|"
                    + row["Input Country"]
                    .strip()
                    .lower()
                )
            ),
        axis=1,
    )

    work = (
        work
        .drop_duplicates(
            "_dedupe",
            keep="first",
        )
        .drop(columns=["_dedupe"])
        .reset_index(drop=True)
    )

    return work


# ============================================================
# BULK PROCESSING
# ============================================================

def process_bulk(
    df,
    lusha_api_key,
    apollo_api_key,
    progress_callback=None,
):
    results = []

    total = len(df)

    for index, row in df.iterrows():

        company = str(
            row.get(
                "Input Company",
                "",
            )
            or ""
        ).strip()

        country = normalize_country(
            row.get(
                "Input Country",
                "",
            )
        )

        domain = clean_domain(
            row.get(
                "Input Domain",
                "",
            )
        )

        base = {
            col: row.get(
                col,
                "",
            )
            for col in df.columns
        }

        try:

            result = process_company(
                company_name=company,
                country=country,
                lusha_api_key=lusha_api_key,
                apollo_api_key=apollo_api_key,
                supplied_domain=domain,
            )

            result = {
                **base,
                **result,
            }

        except Exception as exc:

            result = {
                **base,

                "Company":
                    company,

                "Country":
                    country,

                "Domain":
                    domain
                    or "Not available",

                "Website":
                    "Not available",

                "Boardline":
                    "Not available",

                "Employee Size":
                    "Not available",

                "LinkedIn Company URL":
                    "Not available",

                "LinkedIn Company ID":
                    "Not available",

                "Apollo Organization ID":
                    "Not available",

                "Lusha Company ID":
                    "Not available",

                "Status":
                    "Failed",

                "Error":
                    str(exc),
            }

        results.append(
            result
        )

        if progress_callback:

            progress_callback(
                index + 1,
                total,
            )

    return pd.DataFrame(
        results
    )


# ============================================================
# EXPORT HELPERS
# ============================================================

def dataframe_to_excel(df):
    output = BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl",
    ) as writer:

        df.to_excel(
            writer,
            index=False,
            sheet_name="Company Data",
        )

    return output.getvalue()


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title(
    "🔑 API Configuration"
)

lusha_api_key = st.sidebar.text_input(
    "Lusha API Key",
    value=os.getenv(
        "LUSHA_API_KEY",
        "",
    ),
    type="password",
)

apollo_api_key = st.sidebar.text_input(
    "Apollo API Key",
    value=os.getenv(
        "APOLLO_API_KEY",
        "",
    ),
    type="password",
)

st.sidebar.divider()

st.sidebar.markdown(
    """
### Supported markets

- 🇮🇳 India
- 🇸🇬 Singapore
- 🇲🇾 Malaysia
- 🇻🇳 Vietnam
- 🇵🇭 Philippines
"""
)

st.sidebar.caption(
    "This application retrieves company-level data only. "
    "It does not perform contact/person enrichment."
)


# ============================================================
# MAIN
# ============================================================

st.title(
    "🏢 India & Southeast Asia Company Intelligence"
)

st.caption(
    "Company name → exact company resolution → "
    "website + boardline + LinkedIn + employee size"
)

st.info(
    "Company-level application only. "
    "No Lusha contact/person discovery is performed."
)


# ============================================================
# TABS
# ============================================================

single_tab, bulk_tab = st.tabs(
    [
        "🔎 Single Company",
        "📦 Bulk Companies",
    ]
)


# ============================================================
# SINGLE COMPANY
# ============================================================

with single_tab:

    st.subheader(
        "Company Search"
    )

    col1, col2 = st.columns(
        [2, 1]
    )

    with col1:

        single_company = st.text_input(
            "Company Name",
            placeholder=(
                "Example: Grab"
            ),
            key="single_company",
        )

    with col2:

        single_country = st.selectbox(
            "Country",
            list(
                SUPPORTED_COUNTRIES.keys()
            ),
            key="single_country",
        )

    single_domain = st.text_input(
        "Optional Company Domain",
        placeholder="example.com",
        key="single_domain",
        help=(
            "Providing the official domain makes "
            "company matching more precise."
        ),
    )

    search_button = st.button(
        "🔎 Find Company",
        type="primary",
        use_container_width=True,
    )

    if search_button:

        if not lusha_api_key.strip():

            st.error(
                "Enter your Lusha API key in the sidebar."
            )

        elif not single_company.strip():

            st.error(
                "Enter a company name."
            )

        else:

            with st.spinner(
                "Searching Lusha company records..."
            ):

                try:

                    matches = search_lusha_companies(
                        lusha_api_key,
                        single_company,
                    )

                    st.session_state[
                        "single_matches"
                    ] = matches

                    st.session_state[
                        "single_search_name"
                    ] = single_company

                except Exception as exc:

                    st.error(
                        str(exc)
                    )

    matches = st.session_state.get(
        "single_matches",
        [],
    )

    if matches:

        st.markdown(
            "### Select Exact Company"
        )

        labels = []

        for company in matches:

            normalized = (
                normalize_lusha_company(
                    company
                )
            )

            name = (
                normalized.get(
                    "Lusha Company Name"
                )
                or "Unknown"
            )

            domain = (
                normalized.get(
                    "Lusha Domain"
                )
                or "No domain"
            )

            linkedin = (
                normalized.get(
                    "Lusha LinkedIn URL"
                )
                or "No LinkedIn"
            )

            labels.append(
                f"{name} | "
                f"{domain} | "
                f"{linkedin}"
            )

        selected_index = st.radio(
            "Lusha company matches",
            range(len(labels)),
            format_func=lambda x:
                labels[x],
            key="single_company_selection",
        )

        selected_lusha_company = matches[
            selected_index
        ]

        selected_normalized = (
            normalize_lusha_company(
                selected_lusha_company
            )
        )

        st.markdown(
            "### Selected Company"
        )

        a, b, c, d = st.columns(4)

        a.metric(
            "Company",
            selected_normalized.get(
                "Lusha Company Name"
            )
            or "Not available",
        )

        b.metric(
            "Domain",
            selected_normalized.get(
                "Lusha Domain"
            )
            or "Not available",
        )

        c.metric(
            "Lusha Company ID",
            selected_normalized.get(
                "Lusha Company ID"
            )
            or "Not available",
        )

        d.metric(
            "LinkedIn",
            (
                "Available"
                if selected_normalized.get(
                    "Lusha LinkedIn URL"
                )
                else "Not available"
            ),
        )

        enrich_button = st.button(
            "🚀 Enrich Company",
            type="primary",
            use_container_width=True,
        )

        if enrich_button:

            if not apollo_api_key.strip():

                st.warning(
                    "Apollo API key is not configured. "
                    "Lusha company-level information will "
                    "still be displayed, but Apollo enrichment "
                    "cannot be performed."
                )

            with st.spinner(
                "Enriching company information..."
            ):

                try:

                    result = process_company(
                        company_name=(
                            selected_normalized.get(
                                "Lusha Company Name"
                            )
                            or single_company
                        ),
                        country=single_country,
                        lusha_api_key=(
                            lusha_api_key
                        ),
                        apollo_api_key=(
                            apollo_api_key
                        ),
                        supplied_domain=(
                            selected_normalized.get(
                                "Lusha Domain"
                            )
                            or single_domain
                        ),
                        selected_lusha_company=(
                            selected_lusha_company
                        ),
                    )

                    st.session_state[
                        "single_result"
                    ] = result

                except Exception as exc:

                    st.error(
                        f"Enrichment failed: {exc}"
                    )

    result = st.session_state.get(
        "single_result"
    )

    if isinstance(
        result,
        dict,
    ):

        st.divider()

        st.subheader(
            "📊 Company Intelligence"
        )

        # ----------------------------------------------------
        # MAIN METRICS
        # ----------------------------------------------------

        m1, m2, m3, m4 = st.columns(4)

        m1.metric(
            "Employee Size",
            safe_text(
                result.get(
                    "Employee Size"
                )
            ),
        )

        m2.metric(
            "Boardline",
            safe_text(
                result.get(
                    "Boardline"
                )
            ),
        )

        m3.metric(
            "Country",
            safe_text(
                result.get(
                    "Country"
                )
            ),
        )

        m4.metric(
            "Status",
            safe_text(
                result.get(
                    "Status"
                )
            ),
        )

        # ----------------------------------------------------
        # COMPANY IDENTIFIERS
        # ----------------------------------------------------

        st.markdown(
            "### 🔗 Company Identifiers"
        )

        identifier_df = pd.DataFrame(
            [
                {
                    "Field":
                        "Company",

                    "Value":
                        result.get(
                            "Company",
                            "Not available",
                        ),
                },

                {
                    "Field":
                        "Domain",

                    "Value":
                        result.get(
                            "Domain",
                            "Not available",
                        ),
                },

                {
                    "Field":
                        "Website",

                    "Value":
                        result.get(
                            "Website",
                            "Not available",
                        ),
                },

                {
                    "Field":
                        "LinkedIn Company URL",

                    "Value":
                        result.get(
                            "LinkedIn Company URL",
                            "Not available",
                        ),
                },

                {
                    "Field":
                        "LinkedIn Company ID",

                    "Value":
                        result.get(
                            "LinkedIn Company ID",
                            "Not available",
                        ),
                },

                {
                    "Field":
                        "Apollo Organization ID",

                    "Value":
                        result.get(
                            "Apollo Organization ID",
                            "Not available",
                        ),
                },

                {
                    "Field":
                        "Lusha Company ID",

                    "Value":
                        result.get(
                            "Lusha Company ID",
                            "Not available",
                        ),
                },
            ]
        )

        st.dataframe(
            identifier_df,
            use_container_width=True,
            hide_index=True,
        )

        # ----------------------------------------------------
        # LOCATION
        # ----------------------------------------------------

        st.markdown(
            "### 📍 Company Location"
        )

        location_df = pd.DataFrame(
            [
                {
                    "Country":
                        result.get(
                            "Country",
                            "Not available",
                        ),

                    "State / Province":
                        result.get(
                            "State / Province",
                            "Not available",
                        ),

                    "City":
                        result.get(
                            "City",
                            "Not available",
                        ),
                }
            ]
        )

        st.dataframe(
            location_df,
            use_container_width=True,
            hide_index=True,
        )

        # ----------------------------------------------------
        # FULL RECORD
        # ----------------------------------------------------

        with st.expander(
            "🔍 View complete normalized record"
        ):

            st.json(
                result
            )

        # ----------------------------------------------------
        # DOWNLOAD
        # ----------------------------------------------------

        result_df = pd.DataFrame(
            [result]
        )

        csv_bytes = (
            result_df
            .to_csv(
                index=False
            )
            .encode("utf-8")
        )

        st.download_button(
            "⬇️ Download Company CSV",
            csv_bytes,
            file_name=(
                "company_intelligence.csv"
            ),
            mime="text/csv",
            use_container_width=True,
        )


# ============================================================
# BULK MODE
# ============================================================

with bulk_tab:

    st.subheader(
        "Bulk Company Intelligence"
    )

    st.caption(
        "Upload Company + Country + optional Domain. "
        "The application resolves the company and returns "
        "company-level data only."
    )

    template = pd.DataFrame(
        {
            "Company": [
                "Example Company",
                "Another Company",
            ],

            "Country": [
                "India",
                "Singapore",
            ],

            "Domain": [
                "",
                "",
            ],
        }
    )

    st.download_button(
        "⬇️ Download CSV Template",
        template.to_csv(
            index=False
        ).encode("utf-8"),
        file_name=(
            "company_intelligence_template.csv"
        ),
        mime="text/csv",
    )

    uploaded = st.file_uploader(
        "Upload Company List",
        type=[
            "csv",
            "xlsx",
            "xls",
        ],
        key="company_bulk_upload",
    )

    if uploaded:

        try:

            bulk_df = prepare_bulk_dataframe(
                uploaded
            )

            st.success(
                f"Loaded {len(bulk_df):,} "
                f"unique companies."
            )

            st.dataframe(
                bulk_df.head(50),
                use_container_width=True,
                hide_index=True,
            )

            st.markdown(
                "### Processing Settings"
            )

            default_country = st.selectbox(
                "Default country for rows where Country is blank",
                list(
                    SUPPORTED_COUNTRIES.keys()
                ),
                key="bulk_default_country",
            )

            st.info(
                "Country should preferably be supplied in the "
                "file. The default country is used only when "
                "a row has no country."
            )

            process_button = st.button(
                "🚀 Process All Companies",
                type="primary",
                use_container_width=True,
            )

            if process_button:

                if not lusha_api_key.strip():

                    st.error(
                        "Enter your Lusha API key."
                    )

                else:

                    progress = st.progress(
                        0,
                        text="Starting...",
                    )

                    status_text = st.empty()

                    def update_progress(
                        completed,
                        total,
                    ):

                        percentage = (
                            int(
                                completed
                                / total
                                * 100
                            )
                            if total
                            else 100
                        )

                        progress.progress(
                            percentage,
                            text=(
                                f"Processing "
                                f"{completed:,} / "
                                f"{total:,}"
                            ),
                        )

                        status_text.caption(
                            f"Completed "
                            f"{completed:,} "
                            f"of "
                            f"{total:,}"
                        )

                    # Fill missing countries
                    working_df = bulk_df.copy()

                    working_df[
                        "Input Country"
                    ] = (
                        working_df[
                            "Input Country"
                        ]
                        .replace(
                            "",
                            default_country,
                        )
                        .map(
                            normalize_country
                        )
                    )

                    try:

                        results = process_bulk(
                            working_df,
                            lusha_api_key,
                            apollo_api_key,
                            progress_callback=(
                                update_progress
                            ),
                        )

                        st.session_state[
                            "bulk_company_results"
                        ] = results

                        progress.progress(
                            100,
                            text=(
                                "Completed"
                            ),
                        )

                        status_text.empty()

                        st.success(
                            "Bulk processing completed."
                        )

                    except Exception as exc:

                        progress.empty()

                        st.error(
                            f"Bulk processing failed: "
                            f"{exc}"
                        )

        except Exception as exc:

            st.error(
                f"Could not read uploaded file: "
                f"{exc}"
            )

    # ========================================================
    # BULK RESULTS
    # ========================================================

    bulk_results = st.session_state.get(
        "bulk_company_results"
    )

    if isinstance(
        bulk_results,
        pd.DataFrame,
    ) and not bulk_results.empty:

        st.divider()

        st.subheader(
            "📊 Company Intelligence Results"
        )

        total = len(
            bulk_results
        )

        enriched = (
            bulk_results[
                "Status"
            ]
            .astype(str)
            .isin(
                [
                    "Enriched",
                    "Lusha Match Only",
                ]
            )
            .sum()
        )

        failed = (
            bulk_results[
                "Status"
            ]
            .astype(str)
            .isin(
                [
                    "Failed",
                    "Apollo Failed",
                ]
            )
            .sum()
        )

        boardline_count = (
            bulk_results[
                "Boardline"
            ]
            .astype(str)
            .replace(
                "Not available",
                "",
            )
            .str.strip()
            .ne("")
            .sum()
        )

        linkedin_count = (
            bulk_results[
                "LinkedIn Company URL"
            ]
            .astype(str)
            .replace(
                "Not available",
                "",
            )
            .str.strip()
            .ne("")
            .sum()
        )

        website_count = (
            bulk_results[
                "Website"
            ]
            .astype(str)
            .replace(
                "Not available",
                "",
            )
            .str.strip()
            .ne("")
            .sum()
        )

        employee_count = (
            bulk_results[
                "Employee Size"
            ]
            .astype(str)
            .replace(
                "Not available",
                "",
            )
            .str.strip()
            .ne("")
            .sum()
        )

        a, b, c, d = st.columns(4)

        a.metric(
            "Companies",
            f"{total:,}",
        )

        b.metric(
            "Processed",
            f"{enriched:,}",
        )

        c.metric(
            "Boardlines",
            f"{boardline_count:,}",
        )

        d.metric(
            "LinkedIn",
            f"{linkedin_count:,}",
        )

        e, f, g, h = st.columns(4)

        e.metric(
            "Websites",
            f"{website_count:,}",
        )

        f.metric(
            "Employee Size",
            f"{employee_count:,}",
        )

        g.metric(
            "Failed",
            f"{failed:,}",
        )

        h.metric(
            "Countries",
            f"{bulk_results['Country'].nunique():,}",
        )

        st.dataframe(
            bulk_results,
            use_container_width=True,
            hide_index=True,
        )

        # ----------------------------------------------------
        # CSV
        # ----------------------------------------------------

        csv_bytes = (
            bulk_results
            .to_csv(
                index=False
            )
            .encode("utf-8")
        )

        st.download_button(
            "⬇️ Download CSV",
            csv_bytes,
            file_name=(
                "india_sea_company_intelligence.csv"
            ),
            mime="text/csv",
            use_container_width=True,
        )

        # ----------------------------------------------------
        # EXCEL
        # ----------------------------------------------------

        try:

            excel_bytes = dataframe_to_excel(
                bulk_results
            )

            st.download_button(
                "⬇️ Download Excel",
                excel_bytes,
                file_name=(
                    "india_sea_company_intelligence.xlsx"
                ),
                mime=(
                    "application/vnd.openxmlformats-"
                    "officedocument.spreadsheetml.sheet"
                ),
                use_container_width=True,
            )

        except Exception:

            st.caption(
                "Excel export unavailable. "
                "CSV export is available."
            )

        # ----------------------------------------------------
        # COUNTRY SUMMARY
        # ----------------------------------------------------

        st.markdown(
            "### 🌏 Country Summary"
        )

        country_summary = (
            bulk_results
            .groupby(
                "Country",
                dropna=False,
            )
            .agg(
                Companies=(
                    "Company",
                    "count",
                ),

                Boardlines=(
                    "Boardline",
                    lambda x:
                        x.astype(str)
                        .replace(
                            "Not available",
                            "",
                        )
                        .str.strip()
                        .ne("")
                        .sum(),
                ),

                Websites=(
                    "Website",
                    lambda x:
                        x.astype(str)
                        .replace(
                            "Not available",
                            "",
                        )
                        .str.strip()
                        .ne("")
                        .sum(),
                ),

                LinkedIn=(
                    "LinkedIn Company URL",
                    lambda x:
                        x.astype(str)
                        .replace(
                            "Not available",
                            "",
                        )
                        .str.strip()
                        .ne("")
                        .sum(),
                ),

                Employee_Size=(
                    "Employee Size",
                    lambda x:
                        x.astype(str)
                        .replace(
                            "Not available",
                            "",
                        )
                        .str.strip()
                        .ne("")
                        .sum(),
                ),
            )
            .reset_index()
        )

        st.dataframe(
            country_summary,
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "Company-level enrichment only • "
    "India • Singapore • Malaysia • Vietnam • Philippines"
)

st.caption(
    "No individual contact discovery or personal phone "
    "number enrichment is performed by this application."
)
