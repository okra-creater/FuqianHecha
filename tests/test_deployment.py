"""Static checks for deployment configuration and secret exclusions."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class DeploymentConfigurationTests(unittest.TestCase):
    def test_environment_files_remain_excluded(self) -> None:
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()

        self.assertIn(".env", gitignore)
        self.assertIn(".env.*", gitignore)
        self.assertIn("!.env.example", gitignore)
        self.assertIn(".env", dockerignore)
        self.assertIn(".env.*", dockerignore)
        self.assertIn("data", dockerignore)

    def test_container_uses_production_and_security_settings(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
        requirements = (ROOT / "requirements-deploy.txt").read_text(encoding="utf-8")

        self.assertIn("USER app", dockerfile)
        self.assertIn("HEALTHCHECK", dockerfile)
        self.assertIn("fuqianhecha.web:application", dockerfile)
        self.assertIn("--worker-tmp-dir=/tmp", dockerfile)
        self.assertIn("--no-control-socket", dockerfile)
        self.assertIn("gunicorn==26.2.0", requirements)
        self.assertIn("read_only: true", compose)
        self.assertIn("no-new-privileges:true", compose)


if __name__ == "__main__":
    unittest.main()
