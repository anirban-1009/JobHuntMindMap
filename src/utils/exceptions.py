class MindMapError(Exception):
    """Base exception for all Job Hunt Mindmap errors."""

    pass


class ResumeParsingError(MindMapError):
    """Raised when resume parsing fails due to invalid format or content."""

    pass


class LinkedInDataError(MindMapError):
    """Raised when LinkedIn data format is invalid or missing columns."""

    pass


class ConfigError(MindMapError):
    """Raised when configuration file is invalid or missing required keys."""

    pass
