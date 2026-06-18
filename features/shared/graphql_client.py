import os
import warnings
from typing import Any
import httpx
import google.auth
import google.auth.transport.requests

# Silence noisy end-user credentials warning for local development
warnings.filterwarnings(
    "ignore",
    message=".*Your application has authenticated using end user credentials.*"
)

from features.shared.observability import BackendObservability, trace_performance

# Global AsyncClient instance for connection reuse
_client: httpx.AsyncClient | None = None

def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient()
    return _client


async def execute_graphql_operation(
    operation_name: str, variables: dict[str, Any]
) -> dict[str, Any]:
    """Executes a GraphQL query or mutation against the Firebase SQL Connect service.

    Always targets the production endpoint using Google Application Default Credentials.

    Args:
        operation_name: The query or mutation name defined in queries.gql or mutations.gql.
        variables: Parameter dict to pass to the operation.

    Returns:
        Parsed JSON response from SQL Connect.

    Raises:
        RuntimeError: If the HTTP request fails or returns a non-200 status.
    """
    # Predefined queries list to route execution requests correctly between Query and Mutation
    queries = {
        "ListListings",
        "ListCityListings",
        "ListListingsMissingEmbedding",
        "GetListing",
        "ListUpcomingEvents",
        "GetEvent",
        "SearchListings",
        "SemanticSearchListings",
        "ListPendingReports",
        "ListRecentScans",
        "ListScansSince",
        "ListRecentListings",
        "ListUnverifiedListings",
        "ListListingsMissingSocial",
        "ListCitySocialUrls",
        "GetSocialPostTracker",
        "ListCategories",
        "ListAdminListings",
        "ListAllListings",
        "ListAllReviews",
        "ListAllEvents",
        "ListAllAgentScanLogs",
    }


    project_id = os.getenv("GCP_PROJECT", "fina-au")
    method_name = "impersonateQuery" if operation_name in queries else "impersonateMutation"

    url = (
        f"https://firebasedataconnect.googleapis.com/v1/projects/{project_id}"
        "/locations/australia-southeast1/services/fina-au-service"
        f"/connectors/admin:{method_name}"
    )

    try:
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        if not credentials.valid:
            credentials.refresh(google.auth.transport.requests.Request())
        token = credentials.token
    except Exception as exc:
        BackendObservability.error(
            "Failed to retrieve Google Application Default Credentials for production SQL Connect.",
            exception=exc
        )
        raise RuntimeError(f"Authentication Error: {exc}") from exc

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    body: dict[str, Any] = {
        "operationName": operation_name,
        "variables": variables,
    }

    # Inject the impersonate claim context to satisfy SQL Connect auth policies
    body["extensions"] = {
        "impersonate": {
            "authClaims": {
                "sub": "local-agent-admin",
                "email": os.getenv("AGENT_IMPERSONATE_EMAIL", "deriveraryan@gmail.com")
            }
        }
    }

    BackendObservability.trace(f"Executing GraphQL Operation: {operation_name}")

    client = _get_client()
    with trace_performance("execute_graphql_operation", budget=2.0):
        response = await client.post(
            url, json=body, headers=headers, timeout=30.0
        )

    if response.status_code != 200:
        BackendObservability.error(
            f"GraphQL execution failed ({response.status_code}): {response.text}"
        )
        raise RuntimeError(f"GraphQL Execution Error: {response.text}")

    res_json = response.json()
    if "errors" in res_json and res_json["errors"]:
        BackendObservability.error(
            f"GraphQL returned execution errors: {res_json['errors']}"
        )
        raise RuntimeError(f"GraphQL Execution Error: {res_json['errors']}")

    return res_json

