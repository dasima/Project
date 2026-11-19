from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings


@override_settings(API_TOKEN="test-api-token", DEMO_PROVIDER_TOKEN="private-provider-token")
class ApiAccessTests(TestCase):
    def test_unauthenticated_requests_cannot_list_customers(self):
        response = self.client.get("/api/cases/")
        self.assertEqual(response.status_code, 401)

    def test_bearer_token_lists_empty_collection_without_exposing_secrets(self):
        response = self.client.get("/api/channels/", HTTP_AUTHORIZATION="Bearer test-api-token")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"results": [], "count": 0})
        self.assertNotContains(response, "private-provider-token")

    def test_empty_configured_token_does_not_authenticate(self):
        with override_settings(API_TOKEN=""):
            response = self.client.get("/api/cases/", HTTP_AUTHORIZATION="Bearer ")
        self.assertEqual(response.status_code, 401)

    def test_non_staff_session_cannot_view_customer_records(self):
        user = get_user_model().objects.create_user(username="customer", password="example-only")
        self.client.force_login(user)
        self.assertEqual(self.client.get("/api/cases/").status_code, 403)

    def test_staff_session_can_query_but_not_mutate_api(self):
        user = get_user_model().objects.create_user(username="operator", is_staff=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get("/api/cases/").status_code, 200)
        self.assertEqual(self.client.post("/api/cases/", {}).status_code, 405)

    def test_health_is_public_without_customer_data(self):
        response = self.client.get("/healthz/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
