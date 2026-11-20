import unittest

from fastapi.testclient import TestClient

from apps.api.main import app


class HealthEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_liveness_reports_process_only(self):
        response = self.client.get("/api/v1/health/live")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_readiness_stays_closed_until_dependencies_are_real(self):
        response = self.client.get("/api/v1/health/ready")
        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload["status"], "not_ready")
        self.assertEqual(payload["dependencies"]["database"], "not_configured_or_unavailable")
        self.assertEqual(payload["dependencies"]["worker"], "not_implemented")


if __name__ == "__main__":
    unittest.main()
