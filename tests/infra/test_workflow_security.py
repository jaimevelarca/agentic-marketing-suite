"""Offline security and policy tests for CI/CD workflows and IaC definitions."""
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
INFRA_DIR = REPO_ROOT / "infra"


class TestWorkflowSecurity:
    def test_workflow_files_exist(self):
        expected_workflows = ["pr-check.yml", "ci-dev.yml", "promote-prod.yml"]
        for name in expected_workflows:
            wf_path = WORKFLOWS_DIR / name
            assert wf_path.exists(), f"Workflow file missing: {name}"

    def test_zero_static_secrets_in_workflows(self):
        """Ensure no long-lived service account keys or secrets are referenced."""
        forbidden_patterns = [
            "GCP_SA_KEY",
            "GOOGLE_APPLICATION_CREDENTIALS",
            "GCP_CREDENTIALS",
            "SERVICE_ACCOUNT_KEY",
        ]
        for wf_path in WORKFLOWS_DIR.glob("*.yml"):
            content = wf_path.read_text()
            for pattern in forbidden_patterns:
                assert pattern not in content, (
                    f"Forbidden pattern '{pattern}' found in {wf_path.name}! "
                    "Use Workload Identity Federation (WIF) only."
                )

    def test_wif_permissions_declared(self):
        """All workflows must declare id-token: write and contents: read for OIDC."""
        for wf_path in WORKFLOWS_DIR.glob("*.yml"):
            content = yaml.safe_load(wf_path.read_text())
            perms = content.get("permissions", {})
            assert perms.get("id-token") == "write", f"{wf_path.name} missing id-token: write permission"
            assert perms.get("contents") == "read", f"{wf_path.name} missing contents: read permission"

    def test_prod_workflow_trigger_restricted_to_version_tags(self):
        """Promote to prod workflow must only trigger on git tags v*."""
        prod_wf = WORKFLOWS_DIR / "promote-prod.yml"
        content = yaml.safe_load(prod_wf.read_text())

        # Trigger check
        on_block = content.get(True) or content.get("on")  # yaml parses 'on' as True in YAML 1.1 if not quoted
        assert "push" in on_block, "promote-prod.yml must trigger on push"
        push_block = on_block["push"]
        assert "tags" in push_block, "promote-prod.yml must only trigger on tags"
        assert "branches" not in push_block, "promote-prod.yml must NOT trigger on branches directly"
        assert "v*" in push_block["tags"], "promote-prod.yml must trigger on v* tags"

    def test_no_latest_tags_in_infra_images(self):
        """Ensure infra/__main__.py does not hardcode :latest container image tags."""
        main_py = (INFRA_DIR / "__main__.py").read_text()
        assert ":latest" not in main_py, (
            "Found ':latest' tag in infra/__main__.py! Use stack configuration images or commit SHAs."
        )

    def test_no_latest_tags_in_cloudbuild(self):
        """Ensure deploy and web cloudbuild files do not tag :latest."""
        for cb_path in [REPO_ROOT / "deploy" / "cloudbuild.yaml", REPO_ROOT / "web" / "cloudbuild.yaml"]:
            content = cb_path.read_text()
            assert ":latest" not in content, f"Found ':latest' in {cb_path}"

    def test_prod_stack_yaml_exists_and_configured(self):
        prod_yaml = INFRA_DIR / "Pulumi.prod.yaml"
        assert prod_yaml.exists(), "Pulumi.prod.yaml missing"
        content = yaml.safe_load(prod_yaml.read_text())
        assert content["config"]["gcp:project"] == "agentic-marketing-suite-prod"
        assert content["config"]["agentic-marketing-suite-infra:isArtifactHost"] == "false"
        assert content["config"]["agentic-marketing-suite-infra:artifactHostProject"] == "agentic-marketing-suite"
