SENSITIVE_LOG_KEYS = frozenset({
    'access_token',
    'api_key',
    'authorization',
    'key',
    'passphrase',
    'password',
    'private_key',
    'secret',
    'token',
})


def sanitize_dict(value):
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            if isinstance(key, str) and key.lower() in SENSITIVE_LOG_KEYS:
                sanitized[key] = '***REDACTED***'
            else:
                sanitized[key] = sanitize_dict(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_dict(item) for item in value]
    return value
