# Contract tests

Run locally:

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests/contracts -v
```

The suite validates the schema against JSON Schema Draft 2020-12 and exercises
representative valid and invalid payloads for event envelopes, run status,
provider connection separation, and Council run limits.

These tests validate the internal Browser Council schema only. They do not
claim conformance to the external `yj64.council-api.v1` contract; that requires
the authoritative external OpenAPI/schema fixture and is tracked separately.
