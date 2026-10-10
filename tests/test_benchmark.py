import httpx
import pytest

from experiments.run_benchmark import MAX_CONNECTION_RETRIES, RetriesExhausted, request_attempt

MODEL = "gpt-oss-20b"
CONNECTION_ERROR = "APIConnectionError: Connection error. (cause: ConnectError: reset)"


def client_returning(*errors):
    replies = iter(errors)

    def handler(request):
        result = {"model_id": "m", "status": "success", "error_message": next(replies)}
        return httpx.Response(200, json={"prompt_version": "v", "results": {MODEL: result}})

    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test")


def test_connection_error_is_retried_and_counted():
    sleeps = []
    client = client_returning(CONNECTION_ERROR, CONNECTION_ERROR, None)
    body, _, retries = request_attempt(client, {}, MODEL, sleep=sleeps.append)
    assert retries == 2
    assert sleeps == [5, 5]
    assert body["results"][MODEL]["error_message"] is None


def test_connection_error_gives_up_after_max_retries():
    client = client_returning(*[CONNECTION_ERROR] * (MAX_CONNECTION_RETRIES + 1))
    with pytest.raises(RetriesExhausted, match="connection failed"):
        request_attempt(client, {}, MODEL, sleep=lambda _: None)


def test_model_errors_are_not_retried():
    client = client_returning("NotFoundError: model_not_found")
    body, _, retries = request_attempt(client, {}, MODEL, sleep=lambda _: None)
    assert retries == 0
    assert body["results"][MODEL]["error_message"].startswith("NotFoundError")
