"""Platform-wide environment constants shared by the api-spec-sync scripts.

Every tenant sits behind the same three Base URLs, just prefixed by its own YARP gateway route.
This is not part of OpenAPI (info/paths carry no notion of "environment"), so it lives here
rather than being derived from a tenant's document. Edit this if the platform's environments
ever change - it is the one piece of content in this skill that is not sourced from the
OpenAPI document.
"""

ENVIRONMENTS = [
    ("Development", "DEV",
     "Development environment (DEV) is set up to allow third parties to develop their "
     "integrations with the provided API. The development environment contains a small subset "
     "of production data (that may be obsolete by the time of testing) and may contain some "
     "artificial records created by developers to cover various use cases to be programmed and "
     "tested. The environment can be accessed using the base URL as per below. The DEV is "
     "hosted in MS Azure cloud South Africa North region and is controlled by dotGov Solutions "
     "LLC DevOps team.\n\nThe full Endpoint URL is a result of concatenation of BaseURL and "
     "Endpoint Address.",
     "https://api.test.gsb.gov.zm"),
    ("Staging", "STG",
     "The staging environment (STG) is set up to allow third parties to test their "
     "integrations with the provided API in the environment that closely resembles the "
     "production environment, since it is one of the last safe places to find and fix "
     "environment-related bugs, before moving into production. The staging environment "
     "contains a subset of production data, which is periodically refreshed from the live "
     "production database. The STG is hosted in MS Azure cloud South Africa North region and "
     "is controlled by SMART Zambia DevOps team.",
     "https://api.stage.gsb.gov.zm"),
    ("Production", "PRD",
     "The production (PRD) is hosted on-premises at Infratel (former ZNDC) Datacenter and is "
     "controlled by SMART Zambia DevOps team.",
     "https://api.gsb.gov.zm"),
]


def openapi_servers():
    """ENVIRONMENTS rendered as an OpenAPI `servers` array."""
    return [{"url": url, "description": f"{name} ({code})"} for name, code, _, url in ENVIRONMENTS]
