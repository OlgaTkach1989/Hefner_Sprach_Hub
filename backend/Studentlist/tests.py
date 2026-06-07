from django.test import TestCase, override_settings


class HealthEndpointTests(TestCase):
    def test_liveness_endpoint_returns_ok(self):
        response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["service"], "learning-hub-backend")

    def test_readiness_endpoint_returns_checks_payload(self):
        response = self.client.get("/api/health/ready/")

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["ready"])
        self.assertTrue(payload["checks"]["database"]["ok"])
        self.assertIn("features", payload)

    @override_settings(HEALTHCHECK_EXPOSE_DETAILS=False)
    def test_readiness_endpoint_redacts_operational_details_when_disabled(self):
        response = self.client.get("/api/health/ready/")

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["checks"]["database"]["ok"])
        self.assertNotIn("features", payload)
        self.assertNotIn("path", payload["checks"]["mediaRoot"])
