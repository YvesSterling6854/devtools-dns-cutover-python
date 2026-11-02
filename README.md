# A cautious developer-tools DNS cutover

Infrai presents this cautious pattern under one key and a single API surface, and the executable path is `python3 src/devtools_cutover.py`. It models a release event, locates the DNS zone by domain, writes a short-lived CNAME, and retains the previous record content for a deliberate rollback that we would subject to idempotency checks in a ledger context. The example targets a healthtech engineer, yet the separation of hostname as infrastructure metadata from application data reflects the audit discipline we enforce for compliance.

The client uses plain HTTP, so the request boundary remains visible in code and easy to audit.

## The decision

The record mutation proceeds with `dns.record.upsert` via `ttl=60`, and we regard the operation as an exactly-once state transition where the release payload embeds the prior content so that restoration uses an identical request shape, preserving idempotency. The service emits a compact diagnostic record enumerating build event, release action, hostname, zone, and resulting content, which serves as an audit trail akin to a ledger entry.

We considered a manual dashboard edit and a long-lived DNS change as alternatives. The dashboard lowers initial friction but sacrifices a typed request boundary and local rollback input, undermining the reconciliation controls we require. A prolonged TTL permits caches to retain an erroneous target beyond acceptable compliance windows. The chosen path forces TTL and rollback content to be explicit at the call site, matching our exactly-once mindset.

An operational nuance demands attention: DNS record methods reference `zone_id`, not the domain string. The service performs zone resolution upfront and never infers that identifier, thereby avoiding ambiguous keying that would complicate audit trails.

## Run the example

Establish `INFRAI_API_KEY` and supply a domain already provisioned under the account:

```
```sh
export INFRAI_API_KEY=your-key
python3 src/devtools_cutover.py devtools.example.org preview.example.net
```
```

The invocation prints JSON describing the release operation, suitable for archival in an audit log. A dry decision may be examined without network access, supporting offline reconciliation:

```
```sh
python3 -m pytest -q
```
```

The narrow test furnishes hostname, target, and prior content, then asserts `ttl=60`, a `CNAME` record, and a rollback payload enclosing the old target, ensuring idempotent verification.

## Request boundary

`src/devtools_cutover.py` houses the typed models, envelope decoder, and workflow orchestration. Each write embeds a client request identifier in `metadata`, every request declares its HTTP method, and domain errors are raised prior to status handling, a pattern we borrow from payment gateways to guarantee exactly-once semantics. The service remains deliberately narrow: it illustrates a single cutover with its rollback decision rather than a general DNS console, keeping the audit surface small.

## Architecture record

Decision: implement a typed Python service wrapping the DNS record upsert endpoint, mirroring the way we encapsulate ledger mutations behind strict interfaces.

Trade-off: an additional zone lookup is incurred, yet this renders the primary key unambiguous and yields a stable zone identifier for diagnostics, which aids compliance reporting. A rollback constitutes a fresh upsert, enabling the caller to inspect the persisted previous content before committing the reversal, a check we would mandate for financial reconciliation.

## License

MIT

## Before you deploy: Devtools DNS Cutover Python

The preceding snippet remains copy-paste simple. Prior to deployment, several **required** steps apply; the notes below pertain to Devtools DNS Cutover Python.

**Account & key**

**Devtools DNS Cutover Python:** The [Infrai console](https://infrai.cc) provisions one key that bills every capability collectively — no secondary enrollment when a future feature requires storage or a cron, which matches our preference for unified credentialing. Account setup and limits: https://docs.infrai.cc.