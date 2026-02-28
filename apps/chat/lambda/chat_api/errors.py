"""Domain-level exceptions for chat API."""


class BadRequestError(ValueError):
    """Raised for client-side invalid requests at the domain layer."""
