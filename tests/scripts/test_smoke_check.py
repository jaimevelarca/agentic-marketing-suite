"""Offline unit tests for scripts/smoke_check.py."""
import json
import subprocess
import urllib.error
from unittest.mock import MagicMock, patch

import pytest
from scripts.smoke_check import (
    check_console_iap,
    main,
    run_orchestrator_smoke_job,
    verify_image_digests,
)


class TestConsoleIAPCheck:
    def test_iap_302_redirect_to_accounts_google_com_success(self):
        mock_response = MagicMock()
        mock_response.getcode.return_value = 302
        mock_response.headers = {"Location": "https://accounts.google.com/o/oauth2/v2/auth?client_id=..."}

        with patch("urllib.request.build_opener") as mock_opener_cls:
            mock_opener = MagicMock()
            mock_opener.open.return_value = mock_response
            mock_opener_cls.return_value = mock_opener

            assert check_console_iap("https://console-test.run.app") is True

    def test_iap_307_redirect_to_accounts_google_com_success(self):
        mock_response = MagicMock()
        mock_response.getcode.return_value = 307
        mock_response.headers = {"Location": "https://accounts.google.com/signin/v2"}

        with patch("urllib.request.build_opener") as mock_opener_cls:
            mock_opener = MagicMock()
            mock_opener.open.return_value = mock_response
            mock_opener_cls.return_value = mock_opener

            assert check_console_iap("console-test.run.app") is True

    def test_iap_http_error_302_caught(self):
        http_error = urllib.error.HTTPError(
            url="https://console-test.run.app",
            code=302,
            msg="Found",
            hdrs={"Location": "https://accounts.google.com/o/oauth2/auth"},
            fp=None,
        )

        with patch("urllib.request.build_opener") as mock_opener_cls:
            mock_opener = MagicMock()
            mock_opener.open.side_effect = http_error
            mock_opener_cls.return_value = mock_opener

            assert check_console_iap("https://console-test.run.app") is True

    def test_iap_200_ok_unprotected_fails(self):
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.headers = {}

        with patch("urllib.request.build_opener") as mock_opener_cls:
            mock_opener = MagicMock()
            mock_opener.open.return_value = mock_response
            mock_opener_cls.return_value = mock_opener

            assert check_console_iap("https://console-test.run.app") is False

    def test_iap_redirect_to_unknown_location_fails(self):
        mock_response = MagicMock()
        mock_response.getcode.return_value = 302
        mock_response.headers = {"Location": "https://attacker.com/login"}

        with patch("urllib.request.build_opener") as mock_opener_cls:
            mock_opener = MagicMock()
            mock_opener.open.return_value = mock_response
            mock_opener_cls.return_value = mock_opener

            assert check_console_iap("https://console-test.run.app") is False

    def test_iap_network_exception_fails(self):
        with patch("urllib.request.build_opener") as mock_opener_cls:
            mock_opener = MagicMock()
            mock_opener.open.side_effect = urllib.error.URLError("Connection refused")
            mock_opener_cls.return_value = mock_opener

            assert check_console_iap("https://console-test.run.app") is False


class TestOrchestratorJobExecution:
    def test_job_execution_ready_condition_success(self):
        output_json = json.dumps({
            "status": {
                "conditions": [
                    {"type": "Ready", "status": "True"}
                ],
                "succeededCount": 1,
                "failedCount": 0,
            }
        })
        mock_res = subprocess.CompletedProcess(
            args=["gcloud"],
            returncode=0,
            stdout=output_json,
            stderr="",
        )
        with patch("subprocess.run", return_value=mock_res):
            assert run_orchestrator_smoke_job("agentic-marketing-suite", "us-central1") is True

    def test_job_execution_completed_condition_success(self):
        output_json = json.dumps({
            "status": {
                "conditions": [
                    {"type": "Completed", "status": "True"}
                ],
                "succeededCount": 1,
                "failedCount": 0,
            }
        })
        mock_res = subprocess.CompletedProcess(
            args=["gcloud"],
            returncode=0,
            stdout=output_json,
            stderr="",
        )
        with patch("subprocess.run", return_value=mock_res):
            assert run_orchestrator_smoke_job("agentic-marketing-suite", "us-central1") is True

    def test_job_execution_non_zero_exit_fails(self):
        mock_res = subprocess.CompletedProcess(
            args=["gcloud"],
            returncode=1,
            stdout="",
            stderr="ERROR: Job execution failed",
        )
        with patch("subprocess.run", return_value=mock_res):
            assert run_orchestrator_smoke_job("agentic-marketing-suite", "us-central1") is False

    def test_job_execution_failed_status_fails(self):
        output_json = json.dumps({
            "status": {
                "conditions": [
                    {"type": "Ready", "status": "False", "message": "Container crashed"}
                ],
                "succeededCount": 0,
                "failedCount": 1,
            }
        })
        mock_res = subprocess.CompletedProcess(
            args=["gcloud"],
            returncode=0,
            stdout=output_json,
            stderr="",
        )
        with patch("subprocess.run", return_value=mock_res):
            assert run_orchestrator_smoke_job("agentic-marketing-suite", "us-central1") is False

    def test_job_execution_timeout_fails(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="gcloud", timeout=300)):
            assert run_orchestrator_smoke_job("agentic-marketing-suite", "us-central1") is False


class TestImageDigestVerification:
    def test_matching_console_and_orchestrator_images(self):
        service_json = json.dumps({
            "spec": {
                "template": {
                    "spec": {
                        "containers": [{"image": "us-central1-docker.pkg.dev/agentic-marketing-suite/suite/console@sha256:abc1234"}]
                    }
                }
            }
        })
        job_json = json.dumps({
            "spec": {
                "template": {
                    "spec": {
                        "template": {
                            "spec": {
                                "containers": [{"image": "us-central1-docker.pkg.dev/agentic-marketing-suite/suite/orchestrator@sha256:def5678"}]
                            }
                        }
                    }
                }
            }
        })

        def fake_run(cmd, *args, **kwargs):
            if "services" in cmd:
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=service_json, stderr="")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=job_json, stderr="")

        with patch("subprocess.run", side_effect=fake_run):
            ok = verify_image_digests(
                project="agentic-marketing-suite",
                region="us-central1",
                expected_console_image="sha256:abc1234",
                expected_orchestrator_image="sha256:def5678",
            )
            assert ok is True

    def test_mismatched_image_fails(self):
        service_json = json.dumps({
            "spec": {
                "template": {
                    "spec": {
                        "containers": [{"image": "us-central1-docker.pkg.dev/agentic-marketing-suite/suite/console@sha256:oldimage"}]
                    }
                }
            }
        })
        with patch("subprocess.run", return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout=service_json, stderr="")):
            ok = verify_image_digests(
                project="agentic-marketing-suite",
                region="us-central1",
                expected_console_image="sha256:newimage",
            )
            assert ok is False


class TestMainCLI:
    def test_main_cli_all_checks_pass(self):
        with patch("scripts.smoke_check.check_console_iap", return_value=True), \
             patch("scripts.smoke_check.run_orchestrator_smoke_job", return_value=True), \
             patch("sys.argv", ["smoke_check.py", "--project=agentic-marketing-suite", "--console-url=https://test.run.app"]):
            assert main() == 0

    def test_main_cli_iap_fails_exits_1(self):
        with patch("scripts.smoke_check.check_console_iap", return_value=False), \
             patch("sys.argv", ["smoke_check.py", "--project=agentic-marketing-suite", "--console-url=https://test.run.app"]):
            assert main() == 1

    def test_main_cli_job_fails_exits_1(self):
        with patch("scripts.smoke_check.check_console_iap", return_value=True), \
             patch("scripts.smoke_check.run_orchestrator_smoke_job", return_value=False), \
             patch("sys.argv", ["smoke_check.py", "--project=agentic-marketing-suite", "--console-url=https://test.run.app"]):
            assert main() == 1
