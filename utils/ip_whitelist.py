from functools import lru_cache
import os
from flask import request, abort


@lru_cache(maxsize=1)
def get_whitelisted_ips():
    return set(os.environ.get("WHITELISTED_IPS", "").split(","))


# Decorator to restrict access to whitelisted IPs only
def whitelist_ip(func):
    def wrapper(*args, **kwargs):
        # Get whitelisted IP addresses from environment variable
        whitelisted_ips = get_whitelisted_ips()
        real_ip = (
            (str(request.headers.get("X-Forwarded-For", request.remote_addr)))
            .split(",")[0]
            .strip()
        )
        if real_ip not in whitelisted_ips:
            message = f"Access denied: Your IP {real_ip} is not allowed."
            abort(403, description=message)
        return func(*args, **kwargs)

    return wrapper
