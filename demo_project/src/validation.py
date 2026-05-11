"""
Data validation utilities for user input.
"""

class ValidationError(Exception):
    """Raised when validation fails."""
    pass


def validate_email(email: str) -> bool:
    """Check if email is in valid format."""
    # Overly simple regex - should use proper validation
    if "@" not in email or "." not in email:
        return False
    return True


def validate_username(username: str) -> bool:
    """Check if username meets requirements."""
    if len(username) < 3:
        return False
    if len(username) > 20:
        return False
    # TODO: Add more comprehensive checks
    return True


def validate_password(password: str) -> bool:
    """Check if password meets security requirements."""
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters")
    if not any(c.isupper() for c in password):
        raise ValidationError("Password must contain uppercase letter")
    if not any(c.isdigit() for c in password):
        raise ValidationError("Password must contain a digit")
    return True


def sanitize_input(user_input: str) -> str:
    """Remove potentially dangerous characters from user input."""
    # TODO: Implement proper SQL injection prevention
    dangerous_chars = ["'", '"', ";", "--"]
    sanitized = user_input
    for char in dangerous_chars:
        sanitized = sanitized.replace(char, "")
    return sanitized
