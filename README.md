![MethodBond](assets/MethodBond_hero.jpg)

# MethodBond

> **Is a published method or model artifact properly licensed, independently reproducible, and certified against its declared behavior baseline?**

MethodBond is a local CLI gate that bundles three trust signals into one deterministic verdict:

1. **License** — validates a portable method-license metadata block (inspired by MLX).
2. **Reproducibility** — checks that independent build provenances agree on output hashes (inspired by ReproDossier).
3. **Certification** — compares a candidate artifact's behavior policy against its declared baseline (inspired by CertMesh).

## What it is not

- A general IP search engine or legal advisor.
- A model marketplace or CI/CD platform.
- It does not fetch, train, or run models.

It verifies only the declared trust bundle of **one submitted artifact**.

## Install

```bash
pip install -e .
```

No external runtime dependencies — Python 3.10+ stdlib only.

## CLI Triplet

```bash
# Emit a valid sample artifact descriptor
methodbond sample -o sample.json

# Evaluate the artifact and append a hash-chained ledger entry
methodbond evaluate sample.json

# Render a Markdown report
methodbond report sample.json -o report.md
```

## Verdict Scheme

- `certified` — license valid, reproducibility proven, baseline clean.
- `conditional` — license and reproducibility pass, but baseline has recoverable drift.
- `rejected` — invalid license, unreproducible build, or unacceptable baseline drift.

## Development

```bash
python -m unittest discover -s tests -v
```

## License

MIT License © 2026 sadpig70 (Jung Wook Yang)
