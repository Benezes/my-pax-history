from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.main import app


class ValidationLocaleTests(unittest.TestCase):
    def test_long_action_is_portuguese(self):
        with TestClient(app) as client:
            created = client.post(
                "/api/games",
                json={"difficulty": "medio", "provider": "mock", "name": "Limite"},
            )
            self.assertEqual(created.status_code, 200, created.text)
            game_id = created.json()["id"]
            too_long = "plano " * 2500
            response = client.post(f"/api/games/{game_id}/actions", json={"text": too_long})
            self.assertEqual(response.status_code, 422)
            detail = response.json()["detail"]
            self.assertIsInstance(detail, str)
            self.assertNotIn("String should", detail)
            self.assertIn("caracteres", detail)
            self.assertIn("12000", detail)

    def test_action_12000_is_accepted(self):
        with TestClient(app) as client:
            created = client.post(
                "/api/games",
                json={"difficulty": "medio", "provider": "mock", "name": "Limite ok"},
            )
            game_id = created.json()["id"]
            text = ("agenda fiscal " * 800)[:12000]
            response = client.post(f"/api/games/{game_id}/actions", json={"text": text})
            self.assertEqual(response.status_code, 200, response.text)

    def test_what_if_reports_answered_by(self):
        with TestClient(app) as client:
            created = client.post(
                "/api/games",
                json={"difficulty": "medio", "provider": "mock", "name": "Modelo"},
            )
            game_id = created.json()["id"]
            response = client.post(
                f"/api/games/{game_id}/what-if",
                json={"text": "Proponho uma reforma tributaria ampla"},
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["answered_by"], "simulação offline")


if __name__ == "__main__":
    unittest.main()
