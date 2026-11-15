"""HTTP transport mocks verify the real connector boundary; no live Salesforce org is claimed."""

import httpx, pytest
from backend.app.integrations import SalesforceAdapter, ConnectorError


@pytest.fixture()
def sf(monkeypatch):
    monkeypatch.setenv("SALESFORCE_INSTANCE_URL", "https://synthetic.my.salesforce.com")
    monkeypatch.setenv("SALESFORCE_CLIENT_ID", "synthetic-client")
    monkeypatch.setenv("SALESFORCE_CLIENT_SECRET", "synthetic-secret")
    adapter = SalesforceAdapter()
    yield adapter
    adapter.close()


def mock(sf, handler):
    sf.client.close()
    sf.client = httpx.Client(transport=httpx.MockTransport(handler))


def test_oauth_and_permission_limited_query(sf):
    calls = []

    def handle(request):
        calls.append(request)
        if request.url.path.endswith("/token"):
            assert "client_secret=synthetic-secret" in request.content.decode()
            return httpx.Response(200, json={"access_token": "synthetic-test-token"})
        assert request.headers["Authorization"] == "Bearer synthetic-test-token"
        return httpx.Response(
            200,
            json={
                "done": True,
                "records": [
                    {"Id": "SYNTHETIC1234567", "Name": "Mocked unit-test record"}
                ],
            },
        )

    mock(sf, handle)
    assert len(sf.campaigns()) == 1 and len(calls) == 2


def test_auth_failure_sanitized(sf):
    mock(sf, lambda r: httpx.Response(400, json={"secret": "must not escape"}))
    with pytest.raises(ConnectorError) as error:
        sf.authenticate()
    assert "must not escape" not in str(error.value)


def test_rate_limit(sf):
    sf.token = "synthetic"
    mock(
        sf,
        lambda r: httpx.Response(403, json=[{"errorCode": "REQUEST_LIMIT_EXCEEDED"}]),
    )
    with pytest.raises(ConnectorError, match="rate limit"):
        sf.campaigns()


def test_timeout(sf):
    sf.token = "synthetic"

    def handle(r):
        raise httpx.ReadTimeout("synthetic timeout")

    mock(sf, handle)
    with pytest.raises(ConnectorError, match="timed out"):
        sf.campaigns()


def test_identifier_validation(sf):
    with pytest.raises(ConnectorError, match="identifier"):
        sf.members("x' OR 1=1")


def test_missing_or_untrusted_host(monkeypatch):
    monkeypatch.setenv("SALESFORCE_INSTANCE_URL", "https://untrusted.invalid")
    with pytest.raises(ConnectorError, match="HTTPS Salesforce"):
        SalesforceAdapter()


def test_import_cannot_mix_synthetic(client, monkeypatch):
    monkeypatch.setenv("APP_MODE", "connected")
    assert (
        client.post("/api/integrations/salesforce/import/SYNTHETIC1234567").status_code
        == 409
    )
