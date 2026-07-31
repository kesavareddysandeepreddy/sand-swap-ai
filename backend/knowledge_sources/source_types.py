"""Knowledge source type definitions."""

from __future__ import annotations

from enum import StrEnum


class SourceType(StrEnum):
    """Supported knowledge source connector categories."""

    UPLOAD = "Upload"
    GITHUB = "GitHub"
    SHAREPOINT = "SharePoint"
    ONEDRIVE = "OneDrive"
    GOOGLE_DRIVE = "GoogleDrive"
    AZURE_DEVOPS = "AzureDevOps"
    JIRA = "Jira"
    CONFLUENCE = "Confluence"
    WEBSITE = "Website"
    DATABASE = "Database"
    CUSTOM = "Custom"
