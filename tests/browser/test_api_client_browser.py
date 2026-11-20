"""Exercise the shared frontend client through Chromium and the running API.
Verify that a caller can send an authorization header alongside the JSON default.
"""


def test_request_json_forwards_authorization_header(page, live_server):
    page.goto(f"{live_server}/app/")

    with page.expect_response(f"{live_server}/health") as observed:
        result = page.evaluate("""async () => {
            const { requestJson } = await import('/app/api-client.js');
            return requestJson('/health', {
                headers: { Authorization: 'Bearer test-session' },
            });
        }""")

    assert result == {"ok": True, "status": 200, "body": {"status": "ok"}}
    assert observed.value.request.header_value("authorization") == "Bearer test-session"
    assert observed.value.request.header_value("accept") == "application/json"
