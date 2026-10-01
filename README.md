# Solana RPC Snapshot

A small Python tool that turns three read-only RPC queries into an easy-to-read HTML report and a structured JSON record. Useful for checking whether a public Solana endpoint is answering expected requests before debugging an integration.

Built as a first portfolio project with Codex assistance. This is a learning project and does not claim professional production deployment.

## Run

Requires Python 3.10 or newer. No package installation, wallet or API key is needed.

```bash
python monitor.py
```

Open `reports/report.html` in a browser. The matching raw record is `reports/report.json`.

```bash
python monitor.py --clusters devnet --timeout 10
python -m unittest -v
```

The default checks devnet, testnet and mainnet-beta once each, using nine requests in total. There is no automatic polling or retry loop. Exit code `0` means every check passed; `1` means at least one check failed. Each run replaces the two reports in the output directory. Optional `--output my-reports` writes elsewhere.

## What the report shows

| Method | Observation |
| --- | --- |
| `getHealth` | Whether the queried node reports `ok` |
| `getSlot` | The slot at `finalized` commitment |
| `getVersion` | The node's reported Solana core version |

Every call records elapsed time and explicit errors. HTTP failures, timeouts, RPC errors and malformed results remain failures rather than becoming successful observations. HTML output escapes response text.

## Scope

- One observation from the executing machine; not an uptime monitor or a network-wide health guarantee.
- Elapsed time includes connection setup. It is not an RPC performance benchmark.
- Devnet, testnet and mainnet are different networks; their slot values are not directly comparable.
- Public endpoints may rate-limit requests. A failed request can reflect local connectivity, rate limiting or endpoint behavior.
- Uses only Python's standard library and the documented public endpoints. Does not query personal accounts, sign transactions or move funds.

## Files

- `monitor.py`: request validation, data collection and HTML rendering.
- `test_monitor.py`: offline checks for response validation, rate limiting, timeouts, malformed JSON and HTML escaping.
- `reports/`: timestamped observations from a real run; values will change on the next run.

## Official references

- [Solana clusters and public endpoints](https://solana.com/docs/references/clusters)
- [getHealth](https://solana.com/docs/rpc/http/gethealth)
- [getSlot](https://solana.com/docs/rpc/http/getslot)
- [getVersion](https://solana.com/docs/rpc/http/getversion)

## License

MIT. See `LICENSE`.
