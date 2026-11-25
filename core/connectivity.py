"""Recognize transport failures without treating API/key/audio errors as offline."""
import errno
import socket


def connection_failure(error):
    if isinstance(error, BaseExceptionGroup):
        return any(connection_failure(child) for child in error.exceptions)
    if isinstance(error, (ConnectionError, socket.gaierror)):
        return True
    if isinstance(error, OSError) and (
            error.errno in {errno.ENETDOWN, errno.ENETUNREACH, errno.EHOSTUNREACH,
                            errno.ECONNRESET, errno.ECONNREFUSED, errno.ECONNABORTED}
            or getattr(error, 'winerror', None) in {10050, 10051, 10053, 10054, 10060, 10061, 10065, 11001}):
        return True
    # httpx/httpcore wrap socket failures. Do not import either SDK at UI startup.
    return (type(error).__module__.split('.')[0] in {'httpx', 'httpcore'}
            and type(error).__name__ in {'ConnectError', 'NetworkError', 'ReadError', 'WriteError'})
