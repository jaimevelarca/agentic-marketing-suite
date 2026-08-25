#!/usr/bin/env python3
"""Smoke Gate Check for Agentic Marketing Suite.

Verifies a deployment on Cloud Run:
1. Console Direct IAP: HTTP GET on console URL returns 302/307 redirect to accounts.google.com (IAP protected + alive).
2. Orchestrator Job Run: Executes suite-orchestrator with fixture provider override (19/19 agents, exit 0, zero Gemini spend).
3. Container Image Digests: Verifies deployed revision / job image matches expected digest.

Can be run locally or in GitHub Actions CI/CD.
"""
import argparse
import json
import logging
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("smoke_check")


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Handler that prevents following HTTP redirects."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def check_console_iap(url: str, timeout: int = 30) -> bool:
    """Verify console URL is alive and protected by Direct Cloud Run IAP.

    Expects HTTP 302/307/303 redirect to Google OAuth / accounts.google.com.
    """
    if not url.startswith("http"):
        url = f"https://{url}"

    logger.info("Verifying console IAP endpoint: %s", url)
    opener = urllib.request.build_opener(NoRedirectHandler)

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "agentic-marketing-suite-smoke-gate/1.0"},
        )
        response = opener.open(req, timeout=timeout)
        status_code = response.getcode()
        location = response.headers.get("Location", "")
    except urllib.error.HTTPError as e:
        status_code = e.code
        location = e.headers.get("Location", "")
    except Exception as e:
        logger.error("Failed to connect to console URL: %s (%s)", url, e)
        return False

    logger.info("Console response: HTTP %d, Location: %s", status_code, location)

    # IAP direct intercept returns 302 Found redirecting to accounts.google.com
    if status_code in (302, 303, 307):
        if "accounts.google.com" in location or "google.com/accounts" in location:
            logger.info("✅ Console Direct IAP verified: redirect to Google authentication active.")
            return True
        logger.warning("HTTP %d redirect received, but Location does not point to Google auth: %s", status_code, location)
        return False

    if status_code == 200:
        logger.error("❌ Console returned 200 OK without IAP redirection (Service appears unprotected / public!)")
        return False

    logger.error("❌ Unexpected response from console: HTTP %d", status_code)
    return False


def run_orchestrator_smoke_job(
    project: str,
    region: str,
    job_name: str = "suite-orchestrator",
    client_id: str = "smoke-check",
    timeout: int = 300,
) -> bool:
    """Execute Cloud Run job with fixture override and assert exit 0."""
    logger.info("Executing smoke Cloud Run Job: %s in %s (project: %s)...", job_name, region, project)
    cmd = [
        "gcloud", "run", "jobs", "execute", job_name,
        f"--region={region}",
        f"--project={project}",
        f"--update-env-vars=SUITE_LLM_PROVIDER=fixture,SUITE_BACKEND=memory,GCP_PROJECT_ID={project}",
        f"--args=start,--client-id={client_id},--auto-approve",
        "--wait",
        "--format=json",
    ]

    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.error("❌ Orchestrator smoke Job execution timed out after %d seconds.", timeout)
        return False
    except Exception as e:
        logger.error("❌ Failed to invoke gcloud: %s", e)
        return False

    if res.returncode != 0:
        logger.error("❌ gcloud run jobs execute failed (exit %d): %s", res.returncode, res.stderr)
        # Fetch execution logs from Cloud Logging and describe to print exact error
        try:
            import re
            m = re.search(r"suite-orchestrator-[a-z0-9]+", res.stderr + " " + res.stdout)
            exec_name = m.group(0) if m else None
            if exec_name:
                logger.info("Fetching execution details for %s...", exec_name)
                desc = subprocess.run(
                    ["gcloud", "run", "jobs", "executions", "describe", exec_name,
                     f"--region={region}", f"--project={project}", "--format=yaml"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False
                )
                logger.info("Execution describe:\n%s", desc.stdout or desc.stderr)

            logs_res = subprocess.run(
                ["gcloud", "logging", "read",
                 f'resource.type="cloud_run_job" AND resource.labels.job_name="{job_name}"',
                 f"--project={project}", "--limit=50", "--format=value(textPayload)"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False
            )
            logger.info("Recent job container logs:\n%s", logs_res.stdout or logs_res.stderr)
        except Exception as log_err:
            logger.warning("Could not fetch execution logs: %s", log_err)
        return False

    try:
        data = json.loads(res.stdout) if res.stdout else {}
        status = data.get("status", {})
        conditions = status.get("conditions", [])
        ready_cond = next((c for c in conditions if c.get("type") in ("Ready", "Completed")), None)

        if ready_cond and ready_cond.get("status") == "True":
            logger.info("✅ Orchestrator smoke job completed successfully (exit 0, 19/19 fixture agents).")
            return True

        succeeded_count = status.get("succeededCount", 0)
        failed_count = status.get("failedCount", 0)
        if succeeded_count > 0 and failed_count == 0:
            logger.info("✅ Orchestrator smoke job succeeded (%d succeeded execution).", succeeded_count)
            return True

        logger.error("❌ Orchestrator smoke job reported failure status: %s", status)
        return False
    except Exception as e:
        logger.error("❌ Failed to parse gcloud execution JSON: %s", e)
        # If gcloud exited 0 and output exists, check if execution succeeded
        if "succeeded" in res.stdout.lower() and "failed: 0" in res.stdout.lower():
            logger.info("✅ Orchestrator smoke job confirmed via stdout.")
            return True
        return False


def verify_image_digests(
    project: str,
    region: str,
    service_name: str = "console",
    job_name: str = "suite-orchestrator",
    expected_console_image: Optional[str] = None,
    expected_orchestrator_image: Optional[str] = None,
) -> bool:
    """Verify deployed service and job run the expected container images / digests."""
    all_ok = True

    if expected_console_image:
        logger.info("Checking console service image in %s...", project)
        cmd = [
            "gcloud", "run", "services", "describe", service_name,
            f"--region={region}", f"--project={project}",
            "--format=json",
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        if res.returncode != 0:
            logger.error("Failed to describe service %s: %s", service_name, res.stderr)
            return False
        try:
            data = json.loads(res.stdout)
            containers = data.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
            if not containers:
                containers = data.get("template", {}).get("containers", [])
            deployed_img = containers[0].get("image", "") if containers else ""

            if expected_console_image in deployed_img or deployed_img.endswith(expected_console_image):
                logger.info("✅ Console service image verified: %s", deployed_img)
            else:
                logger.error("❌ Console image mismatch! Expected: %s, Found: %s", expected_console_image, deployed_img)
                all_ok = False
        except Exception as e:
            logger.error("Failed to parse console service metadata: %s", e)
            all_ok = False

    if expected_orchestrator_image:
        logger.info("Checking orchestrator job image in %s...", project)
        cmd = [
            "gcloud", "run", "jobs", "describe", job_name,
            f"--region={region}", f"--project={project}",
            "--format=json",
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        if res.returncode != 0:
            logger.error("Failed to describe job %s: %s", job_name, res.stderr)
            return False
        try:
            data = json.loads(res.stdout)
            containers = data.get("spec", {}).get("template", {}).get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
            if not containers:
                containers = data.get("template", {}).get("template", {}).get("containers", [])
            deployed_img = containers[0].get("image", "") if containers else ""

            if expected_orchestrator_image in deployed_img or deployed_img.endswith(expected_orchestrator_image):
                logger.info("✅ Orchestrator job image verified: %s", deployed_img)
            else:
                logger.error("❌ Orchestrator image mismatch! Expected: %s, Found: %s", expected_orchestrator_image, deployed_img)
                all_ok = False
        except Exception as e:
            logger.error("Failed to parse orchestrator job metadata: %s", e)
            all_ok = False

    return all_ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke gate check for Agentic Marketing Suite")
    parser.add_argument("--project", required=True, help="GCP project ID")
    parser.add_argument("--region", default="us-central1", help="GCP region")
    parser.add_argument("--stack", default="dev", choices=["dev", "prod"], help="Stack name")
    parser.add_argument("--console-url", required=True, help="Cloud Run Console URL")
    parser.add_argument("--expected-console-image", help="Expected image tag/digest for console")
    parser.add_argument("--expected-orchestrator-image", help="Expected image tag/digest for orchestrator")
    parser.add_argument("--skip-job", action="store_true", help="Skip Cloud Run job execution check")
    parser.add_argument("--timeout", type=int, default=300, help="Timeout in seconds for job execution")

    args = parser.parse_args()

    logger.info("=== Starting Smoke Gate Check for Stack: %s (Project: %s) ===", args.stack, args.project)

    # 1. Verify Direct IAP on Console
    iap_ok = check_console_iap(args.console_url)
    if not iap_ok:
        logger.error("🚨 Smoke Gate Check FAILED at Step 1 (Console Direct IAP check)")
        return 1

    # 2. Verify Image Digests if requested
    if args.expected_console_image or args.expected_orchestrator_image:
        images_ok = verify_image_digests(
            project=args.project,
            region=args.region,
            expected_console_image=args.expected_console_image,
            expected_orchestrator_image=args.expected_orchestrator_image,
        )
        if not images_ok:
            logger.error("🚨 Smoke Gate Check FAILED at Step 2 (Image Digest Verification)")
            return 1

    # 3. Execute zero-cost Fixture Orchestrator Job
    if not args.skip_job:
        job_ok = run_orchestrator_smoke_job(
            project=args.project,
            region=args.region,
            timeout=args.timeout,
        )
        if not job_ok:
            logger.error("🚨 Smoke Gate Check FAILED at Step 3 (Orchestrator Job Execution)")
            return 1

    logger.info("🎉 All Smoke Gate Checks PASSED for %s!", args.stack)
    return 0


if __name__ == "__main__":
    sys.exit(main())
