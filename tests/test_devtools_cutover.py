import json
from urllib.request import Request

from src.devtools_cutover import BuildEvent, InfraiClient, ReleaseRequest, cut_over


class Response:
    status = 200

    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


def test_cutover_uses_zone_id_short_ttl_and_keeps_rollback_target():
    requests = []

    def opener(request: Request):
        requests.append(request)
        if request.method == "GET":
            return Response({"ok": True, "data": {"zone_id": "zone-42"}, "error": None, "metadata": {}})
        return Response({"ok": True, "data": {"record_id": "record-7"}, "error": None, "metadata": {}})

    release = ReleaseRequest(
        "devtools.example.org",
        "preview.example.net",
        "devtools-stable.example.net",
        BuildEvent("build-9", "abc123"),
    )
    result = cut_over(InfraiClient("test-key", opener), release)

    body = json.loads(requests[1].data.decode())
    assert result.ttl == 60
    assert result.rollback_content == "devtools-stable.example.net"
    assert body == {
        "zone_id": "zone-42",
        "record_type": "CNAME",
        "name": "devtools.example.org",
        "content": "preview.example.net",
        "ttl": 60,
        "metadata": {"request_id": body["metadata"]["request_id"]},
    }
    assert requests[0].method == "GET"
    assert requests[1].method == "PUT"
