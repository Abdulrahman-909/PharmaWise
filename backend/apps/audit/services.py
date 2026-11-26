from .models import AuditLog


def client_ip(request):
    if request is None:
        return None
    # REMOTE_ADDR only: X-Forwarded-For can be forged unless a trusted proxy
    # sets it. Revisit when deploying behind a reverse proxy.
    return request.META.get("REMOTE_ADDR") or None


def record_audit(action, *, request=None, user=None, username="",
                 organization=None, target=None, details=None):
    user = user or (getattr(request, "user", None) if request else None)
    if user is not None and not getattr(user, "is_authenticated", False):
        user = None

    if organization is None and user is not None:
        organization = getattr(user, "organization", None)

    return AuditLog.objects.create(
        organization=organization,
        user=user,
        username=username or (user.get_username() if user else ""),
        action=action,
        target_type=target._meta.label if target is not None else "",
        target_id=str(target.pk) if target is not None else "",
        ip_address=client_ip(request),
        details=details or {},
    )
