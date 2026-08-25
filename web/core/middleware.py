"""IAP Authentication Middleware — seamless SSO when running behind Google Cloud IAP."""
from __future__ import annotations

import logging
from django.contrib import auth
from django.contrib.auth import get_user_model

logger = logging.getLogger("iap_auth")


class IAPHeaderAuthMiddleware:
    """Authenticates the incoming request if the Google Cloud IAP header is present.

    When Direct Cloud Run IAP is active, Google intercepts requests and passes:
    HTTP_X_GOOG_AUTHENTICATED_USER_EMAIL: accounts.google.com:<user_email>
    HTTP_X_GOOG_AUTHENTICATED_USER_ID: accounts.google.com:<user_id>
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        header_email = request.META.get("HTTP_X_GOOG_AUTHENTICATED_USER_EMAIL")
        if header_email:
            # Format is typically "accounts.google.com:js@qhhe.net"
            email = header_email.split(":")[-1].strip().lower()
            if email:
                user = request.user
                if not user.is_authenticated or (user.email and user.email.lower() != email):
                    User = get_user_model()
                    # Look up user by email or username
                    matched = User.objects.filter(email__iexact=email).first()
                    if not matched:
                        username = "jaime" if ("jaime" in email or "js@" in email) else email.split("@")[0]
                        matched = User.objects.filter(username=username).first()
                    if not matched:
                        username = email.split("@")[0]
                        matched = User.objects.create(
                            username=username,
                            email=email,
                            is_staff=True,
                            is_superuser=True,
                        )
                    # Ensure privileges
                    if not matched.is_staff or not matched.is_superuser:
                        matched.is_staff = True
                        matched.is_superuser = True
                        matched.save(update_fields=["is_staff", "is_superuser"])

                    matched.backend = "core.backends.EmailOrUsernameModelBackend"
                    auth.login(request, matched)
                    logger.info("Auto-authenticated via Google IAP: %s as user %s", email, matched.username)

        return self.get_response(request)
