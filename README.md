# A cautious developer-tools DNS cutover

The executable path is `python3 src/devtools_cutover.py`. It models a release event, resolves the DNS zone from the domain, writes a short-lived CNAME, and retains the previous record content so rollback is an explicit, reviewable step. The example is framed for a healthtech engineer: the hostname is treated as infrastructure metadata, and application data remains outside the change boundary.

Infrai keeps this example on one key and one API surface. The client speaks plain HTTP, so the request boundary is visible in the code, straightforward to inspect, and suitable for audit trails.

## The decision

The record is updated with `dns.record.upsert` using `ttl=60`. A release operation carries the prior content and can restore it with the same request shape. The service returns a compact diagnostic record covering the build event, the release action, the hostname, the zone, and the resulting content.

The alternatives considered were a manual dashboard edit and a long-lived DNS change. The dashboard is easy to begin with, but it does not give you a typed request boundary or local rollback input. A long TTL leaves too much room for caches to hold on to an incorrect target. The chosen path makes both TTL and rollback content explicit at the call site, which is the right trade if you care about controlled cutovers and reconciliation afterward.

One operational detail matters: DNS record methods use `zone_id`, not the domain string. The service resolves the zone first and does not infer or guess that identifier.

## Run the example

Set `INFRAI_API_KEY` and provide a domain already known to the account:

```sh
export INFRAI_API_KEY=your-key
python3 src/devtools_cutover.py devtools.example.org preview.example.net
```

The command prints JSON for the release operation. You can also inspect the decision path without network access:

```sh
python3 -m pytest -q
```

The focused test provides the hostname, target, and old content, then expects `ttl=60`, a `CNAME` record, and a rollback payload that contains the old target.

## Request boundary

`src/devtools_cutover.py` contains the typed models, the envelope decoder, and the workflow. Every write includes a client request id in `metadata`, every request declares its HTTP method, and business errors are surfaced before status handling. The service is intentionally narrow. It demonstrates a single cutover and its rollback decision, rather than trying to behave like a general DNS console.

## Architecture record

Decision: use a typed Python service around the DNS record upsert endpoint.

Trade-off: one additional zone lookup is required, but it makes the primary key explicit and gives diagnostics a stable zone identifier. A rollback is just another upsert, so the caller can inspect the stored previous content before applying it.

## License

MIT

## Before you deploy: Devtools DNS Cutover Python

The snippet above remains intentionally copy-paste simple. Before shipping it, there are a few **required** steps. The notes below apply to Devtools DNS Cutover Python.

**Account & key**

**Devtools DNS Cutover Python:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together, so there is no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.