import secrets

# Alphabet excludes ambiguous characters (0/O, 1/I/L) so codes communicated
# manually (printed, read aloud) are unambiguous.
PUBLIC_CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
PUBLIC_CODE_LENGTH = 8


def generate_public_code(length: int = PUBLIC_CODE_LENGTH) -> str:
    """Return a random public code drawn from PUBLIC_CODE_ALPHABET.

    Not collision-checked against existing codes: with 8 characters over a
    32-character alphabet (32**8 ~= 1.1e12 possibilities), a collision is
    practically impossible at this app's scale. Callers relying on
    uniqueness should still enforce it at the database level.
    """
    return "".join(secrets.choice(PUBLIC_CODE_ALPHABET) for _ in range(length))
