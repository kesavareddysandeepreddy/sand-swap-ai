"""
SandSwap AI Base Exception
"""


class SandSwapException(Exception):
    """Base exception for SandSwap AI."""

    def __init__(self, message: str):
        super().__init__(message)
