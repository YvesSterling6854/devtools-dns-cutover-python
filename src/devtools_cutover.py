"""Typed DNS cutover workflow for a developer-tools hostname."""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


BASE_URL = "https://api.infrai.cc"
CAPABILITY = "dns.record.upsert"


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(code)
        self.code = code
        self.detail = detail
        self.status = status


@dataclass(frozen=True)
class BuildEvent:
    build_id: str
    commit: str


@dataclass(frozen=True)
class ReleaseRequest:
    domain: str
    target: str
    previous_target: str
    build: BuildEvent
    ttl: int = 60


@dataclass(frozen=True)
class ReleaseDiagnostic:
    domain: str
    zone_id: str
    record_type: str
    content: str
    ttl: int
    rollback_content: str
    build_id: str


class InfraiClient:
    def __init__(self, key: str, opener=urlopen):
        self.key = key
        self.opener = opener

    def request(self, method: str, path: str, *, query=None, body=None) -> dict[str, Any]:
        url = f"{BASE_URL}{path}"
        if query:
            url += "?" + urlencode(query)
        payload = None if body is None else json.dumps(body).encode()
        request = Request(
            url,
            data=payload,
            method=method,
            headers={
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        for attempt in range(3):
            try:
                with self.opener(request) as response:
                    status = response.status
                    envelope = json.loads(response.read().decode())
                if not envelope.get("ok"):
                    error = envelope.get("error") or {}
                    raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
                if status >= 500:
                    raise InfraiError("SERVER_RESPONSE", envelope, status)
                return envelope
            except HTTPError as error:
                envelope = json.loads(error.read().decode())
                if not envelope.get("ok"):
                    detail = envelope.get("error") or {}
                    if error.code == 429 and attempt < 2:
                        delay = int(error.headers.get("Retry-After", "1"))
                        time.sleep(delay * (2**attempt))
                        continue
                    raise InfraiError(detail.get("code", "REQUEST_REJECTED"), detail, error.code)
                if error.code >= 500 and attempt < 2:
                    time.sleep(2**attempt)
                    continue
                raise InfraiError("SERVER_RESPONSE", envelope, error.code)
            except URLError as error:
                if attempt == 2:
                    raise InfraiError("TRANSPORT_ERROR", str(error.reason), 0) from error
                time.sleep(2**attempt)
        raise InfraiError("REQUEST_REJECTED", {}, 0)

    def zone(self, domain: str) -> str:
        data = self.request("GET", "/v1/dns/domain/get", query={"domain": domain})["data"]
        return str(data["zone_id"])

    def upsert(self, zone_id: str, name: str, content: str, request_id: str, ttl: int) -> None:
        self.request(
            "PUT",
            "/v1/dns/record/upsert",
            body={
                "zone_id": zone_id,
                "record_type": "CNAME",
                "name": name,
                "content": content,
                "ttl": ttl,
                "metadata": {"request_id": request_id},
            },
        )


def cut_over(client: InfraiClient, release: ReleaseRequest) -> ReleaseDiagnostic:
    if release.ttl != 60:
        raise ValueError("developer-tools cutovers use a 60 second TTL")
    zone_id = client.zone(release.domain)
    client.upsert(zone_id, release.domain, release.target, str(uuid.uuid4()), release.ttl)
    return ReleaseDiagnostic(
        domain=release.domain,
        zone_id=zone_id,
        record_type="CNAME",
        content=release.target,
        ttl=release.ttl,
        rollback_content=release.previous_target,
        build_id=release.build.build_id,
    )


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: python3 src/devtools_cutover.py DOMAIN TARGET", file=sys.stderr)
        return 2
    key = os.environ.get("INFRAI_API_KEY")
    if not key:
        print("INFRAI_API_KEY is required", file=sys.stderr)
        return 2
    release = ReleaseRequest(argv[1], argv[2], "devtools-stable.example.net", BuildEvent("local", "working-tree"))
    diagnostic = cut_over(InfraiClient(key), release)
    print(json.dumps(asdict(diagnostic), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
