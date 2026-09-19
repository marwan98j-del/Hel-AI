import hashlib
import re
from datetime import date, datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


APPLICANT_INDIVIDUAL = "individual"
APPLICANT_ORGANIZATION = "organization/institution"
APPLICANT_COMPANY = "company/business"
APPLICANT_GOVERNMENT = "government entity"
APPLICANT_UNIVERSITY = "university/research institution"
APPLICANT_NGO = "NGO/nonprofit"
APPLICANT_MIXED = "mixed/both/unknown"

RECORD_KIND_APPLICATION = "application_opportunity"
RECORD_KIND_INFORMATIONAL = "informational"
RECORD_KIND_ROUNDUP = "roundup"
RECORD_KIND_UNKNOWN = "unknown"

KNOWN_RECORD_KINDS = {
    RECORD_KIND_APPLICATION,
    RECORD_KIND_INFORMATIONAL,
    RECORD_KIND_ROUNDUP,
    RECORD_KIND_UNKNOWN,
}

KNOWN_APPLICANT_TYPES = {
    APPLICANT_INDIVIDUAL,
    APPLICANT_ORGANIZATION,
    APPLICANT_COMPANY,
    APPLICANT_GOVERNMENT,
    APPLICANT_UNIVERSITY,
    APPLICANT_NGO,
    APPLICANT_MIXED,
}

ENTITY_APPLICANT_TYPES = {
    APPLICANT_ORGANIZATION,
    APPLICANT_COMPANY,
    APPLICANT_GOVERNMENT,
    APPLICANT_UNIVERSITY,
    APPLICANT_NGO,
}


def clean_text(value):
    if value is None:
        return ""

    return " ".join(str(value).split()).strip()


def normalize_record_kind(value):
    normalized = clean_text(value).lower()
    if normalized in KNOWN_RECORD_KINDS:
        return normalized
    return RECORD_KIND_UNKNOWN


def record_kind_is_non_actionable(value):
    return normalize_record_kind(value) in {
        RECORD_KIND_INFORMATIONAL,
        RECORD_KIND_ROUNDUP,
    }


def normalize_status(value):
    value = clean_text(value)
    lowered = value.lower()

    aliases = {
        "forecasted": "Upcoming",
        "forecast": "Upcoming",
        "forecast opportunity": "Upcoming",
        "upcoming": "Upcoming",
        "planned": "Upcoming",
        "posted": "Open",
        "active": "Open",
        "open": "Open",
        "closed": "Closed",
        "expired": "Closed",
        "archived": "Closed",
    }

    return aliases.get(lowered, "Unknown")


def effective_status(opportunity, today=None):
    """Return actionable status after applying an inclusive deadline.

    Production uses ``date.today()``, matching the project's existing
    server-local calendar-date convention. Tests and audits can inject an
    explicit ``date`` through ``today``. Missing or invalid deadline values do
    not override the normalized stored status.
    """
    stored_status = normalize_status((opportunity or {}).get("status"))
    if stored_status != "Open":
        return stored_status

    deadline_value = (opportunity or {}).get("deadline")
    deadline = None
    if isinstance(deadline_value, datetime):
        deadline = deadline_value.date()
    elif isinstance(deadline_value, date):
        deadline = deadline_value
    else:
        exact = _date_from_exact_value(deadline_value)
        if exact:
            try:
                deadline = date.fromisoformat(exact)
            except ValueError:
                deadline = None

    if deadline is None:
        return stored_status

    reference_date = today
    if isinstance(reference_date, datetime):
        reference_date = reference_date.date()
    if reference_date is None:
        reference_date = date.today()
    if not isinstance(reference_date, date):
        try:
            reference_date = date.fromisoformat(str(reference_date))
        except (TypeError, ValueError):
            raise ValueError("today must be a date or ISO YYYY-MM-DD value")

    return "Closed" if deadline < reference_date else "Open"


def normalize_url(value):
    value = clean_text(value)

    if not value:
        return ""

    parsed = urlsplit(value)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")

    query_items = [
        (key, item_value)
        for key, item_value in parse_qsl(
            parsed.query,
            keep_blank_values=True,
        )
        if not key.lower().startswith("utm_")
    ]

    query = urlencode(query_items)

    return urlunsplit(
        (
            scheme,
            netloc,
            path,
            query,
            "",
        )
    )


def create_fingerprint(title, source_url="", external_id=""):
    raw_value = (
        f"{clean_text(title).lower()}|"
        f"{normalize_url(source_url).lower()}|"
        f"{clean_text(external_id).lower()}"
    )

    return hashlib.sha256(
        raw_value.encode("utf-8")
    ).hexdigest()


def _date_from_exact_value(value):
    value = clean_text(value)

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value

    return None


def _date_after_label(text, labels):
    if not text:
        return None

    for label in labels:
        pattern = (
            rf"{label}\s*[:\-]?\s*"
            rf"([0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}})"
        )
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match:
            return match.group(1)

    return None


def normalize_deadline(value, source_text=""):
    exact = _date_from_exact_value(value)

    if exact:
        return exact

    combined = "\n".join(
        part
        for part in [
            clean_text(value),
            clean_text(source_text),
        ]
        if part
    )

    if re.search(
        r"\b(start|starting|open date|opens|opening date|available from)\b",
        clean_text(value).lower(),
    ):
        return None

    return _date_after_label(
        combined,
        [
            "application deadline",
            "closing date",
            "close date",
            "deadline",
            "due date",
            "submit by",
            "applications close",
            "closing",
        ],
    )


def normalize_open_date(value, source_text=""):
    exact = _date_from_exact_value(value)

    if exact:
        return exact

    combined = "\n".join(
        part
        for part in [
            clean_text(value),
            clean_text(source_text),
        ]
        if part
    )

    return _date_after_label(
        combined,
        [
            "open date",
            "opening date",
            "applications open",
            "applications accepted anytime starting",
            "starting",
            "start date",
            "available from",
        ],
    )


def normalize_applicant_types(value):
    if isinstance(value, str):
        raw_items = re.split(r"[,;/|]", value)
    elif isinstance(value, list):
        raw_items = value
    else:
        return []

    applicant_types = []

    for item in raw_items:
        lowered = clean_text(item).lower()

        if not lowered:
            continue

        if lowered in {
            "individual",
            "person",
            "student",
            "researcher",
            "applicant",
        }:
            normalized = APPLICANT_INDIVIDUAL
        elif lowered in {
            "organization",
            "organisation",
            "institution",
            "organization/institution",
            "organisation/institution",
        }:
            normalized = APPLICANT_ORGANIZATION
        elif lowered in {
            "company",
            "business",
            "sme",
            "small business",
            "company/business",
        }:
            normalized = APPLICANT_COMPANY
        elif lowered in {
            "government",
            "government entity",
            "state government",
            "territorial government",
            "tribal government",
        }:
            normalized = APPLICANT_GOVERNMENT
        elif lowered in {
            "university",
            "research institution",
            "research organisation",
            "research organization",
            "higher education institution",
            "university/research institution",
        }:
            normalized = APPLICANT_UNIVERSITY
        elif lowered in {
            "ngo",
            "nonprofit",
            "non-profit",
            "not-for-profit",
            "ngo/nonprofit",
        }:
            normalized = APPLICANT_NGO
        elif lowered in {
            "mixed",
            "both",
            "unknown",
            "mixed/both/unknown",
        }:
            normalized = APPLICANT_MIXED
        else:
            continue

        if normalized not in applicant_types:
            applicant_types.append(normalized)

    return applicant_types


def primary_applicant_type(applicant_types):
    """Return a compact primary type while preserving unknown as None."""
    values = normalize_applicant_types(applicant_types)
    if not values:
        return None
    value_set = set(values)
    if APPLICANT_MIXED in value_set or (
        APPLICANT_INDIVIDUAL in value_set
        and bool(value_set & ENTITY_APPLICANT_TYPES)
    ):
        return "mixed"
    if value_set == {APPLICANT_INDIVIDUAL}:
        return APPLICANT_INDIVIDUAL
    if len(value_set) == 1:
        return values[0]
    return APPLICANT_ORGANIZATION


def infer_applicant_types_from_text(text):
    lowered = clean_text(text).lower()

    if not lowered:
        return []

    applicant_types = []

    def add(applicant_type):
        if applicant_type not in applicant_types:
            applicant_types.append(applicant_type)

    entity_patterns = [
        (
            APPLICANT_UNIVERSITY,
            [
                r"\bapplicants? must be based at (?:an? )?(?:uk )?research organi[sz]ation eligible for [^.\n]{0,120}\bfunding\b",
                r"\bapplicants? must be [^.\n]{0,160}\bbased at (?:an? )?(?:uk )?research organi[sz]ation eligible for [^.\n]{0,120}\bfunding\b",
                r"\bapplicants? must be [^.\n]{0,160}\bemployed by (?:an? )?(?:eligible )?(?:uk )?research organi[sz]ations?\b",
                r"\bapplicants? must be based at (?:an? )?eligible (?:research )?(?:organi[sz]ation|institution)\b",
                r"\bresearch organisations? eligible to apply\b",
                r"\bresearch organizations? eligible to apply\b",
                r"\beligible research organisations?\b",
                r"\beligible research organizations?\b",
                r"\beligible (?:submitters?|proposers?) (?:include|are)[^.\n]{0,200}\binstitutions?\b",
                r"\beligible applicants? (?:include|are) (?:universities|institutions|higher education institutions|research institutions)\b",
                r"\beligible institutions? include\b",
                r"\bopen to [^.\n]{0,200}\bacademic institutions?\b",
                r"\byour organisation must be [^.\n]{0,200}\bacademic institutions?\b",
                r"\byour organization must be [^.\n]{0,200}\bacademic institutions?\b",
                r"\buniversities are eligible\b",
                r"\buniversity may apply\b",
                r"\bopen to [^.\n]{0,200}\bresearch and technology organisations?\b",
                r"\bopen to [^.\n]{0,200}\bresearch and technology organizations?\b",
                r"\byour organisation must be [^.\n]{0,200}\bresearch and technology organisations?\b",
                r"\byour organization must be [^.\n]{0,200}\bresearch and technology organizations?\b",
            ],
        ),
        (
            APPLICANT_GOVERNMENT,
            [
                r"\beligible (?:applicants?|organizations?|organisations?|entities|submitters?) (?:include|are)[^.\n]{0,200}\b(?:state|territorial|tribal) (?:governments?|organizations?)\b",
                r"\b(?:state|territorial|tribal) governments? (?:are )?eligible(?: to apply)?\b",
                r"\bgovernment (?:entities|agencies) (?:are )?eligible(?: to apply)?\b",
                r"\b(?:programs?|opportunit(?:y|ies)|funding) (?:is )?for (?:state, )?territorial, and tribal organizations?\b",
                r"\bopen to [^.\n]{0,200}\bpublic sector organisations?\b",
                r"\bopen to [^.\n]{0,200}\bpublic sector organizations?\b",
                r"\byour organisation must be [^.\n]{0,200}\bpublic sector organisations?\b",
                r"\byour organization must be [^.\n]{0,200}\bpublic sector organizations?\b",
            ],
        ),
        (
            APPLICANT_COMPANY,
            [
                r"\bto be considered[^.\n]{0,160}\bstartups? must meet (?:the )?(?:following )?(?:criteria|requirements)\b",
                r"\beligibility\b[^\n]{0,600}\bthe compan(?:y|ies) must\b",
                r"\beligible (?:applicants?|organizations?|organisations?|entities|submitters?) (?:include|are)[^.\n]{0,200}\b(?:small businesses?|smes?|companies)\b",
                r"\bcompanies are eligible\b",
                r"\bbusinesses? may apply\b",
                r"\bopen to [^.\n]{0,200}\b(?:startups?|companies|businesses)\b",
                r"\bopen to [^.\n]{0,200}\buk-registered businesses?\b",
                r"\bopen to [^.\n]{0,200}\buk registered businesses?\b",
                r"\byour organisation must be a uk registered business\b",
                r"\byour organization must be a uk registered business\b",
                r"\byour organisation must be [^.\n]{0,200}\bbusiness\b",
                r"\byour organization must be [^.\n]{0,200}\bbusiness\b",
                r"\bfor-profit organizations? (?:are )?eligible(?: to apply)?\b",
            ],
        ),
        (
            APPLICANT_NGO,
            [
                r"\bnonprofits? may apply\b",
                r"\bnon-profits? may apply\b",
                r"\bnot-for-profit organizations? may apply\b",
                r"\bnot-for-profit organisations? may apply\b",
                r"\bopen to .*not-for-profit organisations?\b",
                r"\bopen to .*not-for-profit organizations?\b",
                r"\byour organisation must be .*not for profit\b",
                r"\byour organization must be .*not for profit\b",
                r"\bopen to .*charities\b",
                r"\byour organisation must be .*charity\b",
                r"\byour organization must be .*charity\b",
                r"\bngos? may apply\b",
            ],
        ),
        (
            APPLICANT_ORGANIZATION,
            [
                r"\bopen to [^.\n]{0,200}\b(?:organizations?|organisations?)\b",
                r"\borganizations? may apply\b",
                r"\borganisations? may apply\b",
                r"\binstitutions? may apply\b",
                r"\beligible applicants are organizations?\b",
                r"\beligible applicants are organisations?\b",
                r"\bmust be an organization\b",
                r"\bmust be an organisation\b",
                r"\byour organisation must be\b",
                r"\byour organization must be\b",
                r"\bentity applicants?\b",
                r"\bunaffiliated individuals? are not eligible(?: to apply)?\b",
                r"\bindividuals? are not eligible to apply\b",
                r"\beligible submitters? include [^.\n]{0,200}\binstitutions?\b",
                r"\beligible organi[sz]ations? include\b",
                r"\beligible institutions? include\b",
                r"\bproposals? (?:may|must) be submitted by [^.\n]{0,120}\b(?:institutions?|organi[sz]ations?)\b",
                r"\bapplications? must be submitted by [^.\n]{0,120}\b(?:institutions?|organi[sz]ations?)\b",
                r"\bsubmitting organi[sz]ation(?:'s)?\b",
                r"\bapplicant organi[sz]ation\b",
                r"\bapplicant institution\b",
                r"\bproposals? submitted on behalf of (?:an? )?(?:institution|organi[sz]ation)\b",
                r"\b(?:institution|organi[sz]ation)s? must (?:first )?be registered [^.\n]{0,120}\b(?:to apply|to submit|application|proposal)\b",
                r"\b(?:proposal|application|submission)[^.\n]{0,200}\bauthorized organi[sz]ational representative\b",
                r"\bauthorized organi[sz]ational representative[^.\n]{0,200}\b(?:submit|proposal|application)\b",
                r"\b(?:proposal|application|submission)[^.\n]{0,120}\baor\b",
            ],
        ),
    ]

    individual_patterns = [
        r"\bindividuals? may apply\b",
        r"\bindividuals? and (?:organi[sz]ations?|institutions?) may apply\b",
        r"\bindividual applicants?\b",
        r"\bstudents? may apply\b",
        r"\bfor students?\b",
        r"\bfor individuals?\b",
        r"\bapplicants must be individuals?\b",
        r"\beligible applicants? include [^.\n]{0,160}\b(?:students?|undergraduates?|graduates?|degree holders?|individuals?)\b",
        r"\beligible applicants? are [^.\n]{0,120}\b(?:women|men|people|persons|scientists|researchers|students|professionals)\b",
        r"\bfellowships? (?:is |are )?offered to (?:the )?individuals?\b",
        r"\bapplications? from individuals?\b",
        r"\bopen to [^.\n]{0,200}\b(?:anyone|young people|individual activists?|journalists?|media practitioners?|storytellers?|students?|researchers?|scientists?|professionals?|entrepreneurs?|founders?|innovators?|educators?|teachers?|lawyers?|leaders?|women|youth)\b",
        r"\bapplicants? must be [^.\n]{0,180}\b(?:women|men|people|persons|journalists?|students?|researchers?|scientists?|professionals?|entrepreneurs?|founders?|educators?|teachers?|lawyers?|leaders?|citizens?|nationals?|refugees?)\b",
        r"\bapplicants? must be (?:aged?|age)\s*(?:between\s*)?\d+\b",
        r"\bapplicants? must (?:have|hold|possess)[^.\n]{0,160}\b(?:ph\.?d|doctorate|master'?s?|bachelor'?s?|degree|diploma)\b",
        r"\bapplicants? must be [^.\n]{0,120}\b(?:citizens?|nationals?|residents?)\b",
        r"\bapplications? (?:are )?invited (?:from|for) [^.\n]{0,160}\b(?:individuals?|people|students?|researchers?|professionals?|journalists?|entrepreneurs?|founders?|women|youth)\b",
    ]

    for applicant_type, patterns in entity_patterns:
        if any(
            re.search(pattern, lowered)
            for pattern in patterns
        ):
            add(applicant_type)

    individual_detected = any(
        re.search(pattern, lowered)
        for pattern in individual_patterns
    )
    institutional_affiliation_required = bool(
        re.search(
            r"\bapplicants? must be [^.\n]{0,200}\b(?:based at|employed by) "
            r"(?:an? )?(?:eligible )?(?:uk )?(?:research )?"
            r"(?:organi[sz]ation|institution)s?"
            r"(?:[^.\n]{0,120}\beligible for\b)?",
            lowered,
        )
    )
    direct_individual_permission = bool(
        re.search(
            r"\b(?:individuals? may apply|applications? from individuals?|"
            r"open to [^.\n]{0,120}\bindividuals?)\b",
            lowered,
        )
    )

    if individual_detected and (
        not institutional_affiliation_required
        or direct_individual_permission
    ):
        add(APPLICANT_INDIVIDUAL)

    if (
        APPLICANT_INDIVIDUAL in applicant_types
        and any(
            applicant_type in ENTITY_APPLICANT_TYPES
            for applicant_type in applicant_types
        )
    ):
        add(APPLICANT_MIXED)

    return applicant_types


def get_eligible_applicant_types(opportunity):
    structured = normalize_applicant_types(
        opportunity.get("eligible_applicant_types")
        or opportunity.get("applicant_type")
    )

    if structured:
        return structured

    text_parts = [
        opportunity.get("title"),
        opportunity.get("organization"),
        opportunity.get("type"),
        opportunity.get("notes"),
        opportunity.get("summary_en"),
        opportunity.get("original_text"),
    ]

    return infer_applicant_types_from_text(
        "\n".join(
            clean_text(part)
            for part in text_parts
            if clean_text(part)
        )
    )


def applicant_types_are_entity_only(applicant_types):
    applicant_types = set(applicant_types or [])

    if not applicant_types:
        return False

    if APPLICANT_MIXED in applicant_types:
        return False

    if APPLICANT_INDIVIDUAL in applicant_types:
        return False

    return bool(
        applicant_types & ENTITY_APPLICANT_TYPES
    )
