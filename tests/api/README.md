# API foundation tests

Run with:

```sh
python -m pip install -r requirements-api.txt
python -m unittest discover -s tests/api -v
```

The readiness endpoint deliberately returns HTTP 503 until real database and
worker health checks are implemented. Process liveness is not deployment
readiness.
