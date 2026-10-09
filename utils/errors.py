class UserFacingError(RuntimeError):
    """Only raise with a fixed, credential-free message owned by this application."""
