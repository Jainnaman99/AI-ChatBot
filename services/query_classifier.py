LIST_KEYWORDS = [
    "list",
    "all",
    "schemes",
    "services",
    "programs",
    "initiatives"
]

LOCATION_KEYWORDS = [
    "where",
    "location",
    "located",
    "situated",
    "kahan"
]


def get_query_type(query):

    lower = query.lower()

    # List query
    if any(word in lower for word in LIST_KEYWORDS):
        return "list"

    # Location query
    if any(word in lower for word in LOCATION_KEYWORDS):
        return "location"

    return "general"