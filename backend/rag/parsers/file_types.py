"""File-type registry for parser and chunker factories."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class FileTypeSpec:
    """Parser/chunker routing information for a file signature."""

    key: str
    parser: str
    chunker: str
    category: str


FILE_TYPE_SPECS: dict[str, FileTypeSpec] = {
    # Documents
    ".pdf": FileTypeSpec("pdf", "pdf", "pdf", "document"),
    ".docx": FileTypeSpec("docx", "word", "word", "document"),
    ".doc": FileTypeSpec("doc", "word", "word", "document"),
    ".txt": FileTypeSpec("txt", "text", "paragraph", "document"),
    ".md": FileTypeSpec("md", "markdown", "markdown", "document"),
    ".rtf": FileTypeSpec("rtf", "text", "paragraph", "document"),
    ".log": FileTypeSpec("log", "text", "paragraph", "document"),
    ".odt": FileTypeSpec("odt", "word", "word", "document"),
    ".zip": FileTypeSpec("zip", "zip", "paragraph", "archive"),
    # Spreadsheets
    ".csv": FileTypeSpec("csv", "csv", "csv", "spreadsheet"),
    ".tsv": FileTypeSpec("tsv", "csv", "csv", "spreadsheet"),
    ".xlsx": FileTypeSpec("xlsx", "excel", "excel", "spreadsheet"),
    ".xls": FileTypeSpec("xls", "excel", "excel", "spreadsheet"),
    ".ods": FileTypeSpec("ods", "excel", "excel", "spreadsheet"),
    # Presentations
    ".pptx": FileTypeSpec("pptx", "powerpoint", "powerpoint", "presentation"),
    ".ppt": FileTypeSpec("ppt", "powerpoint", "powerpoint", "presentation"),
    ".odp": FileTypeSpec("odp", "powerpoint", "powerpoint", "presentation"),
    # Structured
    ".json": FileTypeSpec("json", "json", "json", "structured"),
    ".xml": FileTypeSpec("xml", "xml", "xml", "structured"),
    ".yaml": FileTypeSpec("yaml", "yaml", "paragraph", "structured"),
    ".yml": FileTypeSpec("yml", "yaml", "paragraph", "structured"),
    ".conf": FileTypeSpec("conf", "config", "paragraph", "structured"),
    ".cfg": FileTypeSpec("cfg", "config", "paragraph", "structured"),
    ".properties": FileTypeSpec("properties", "config", "paragraph", "structured"),
    ".toml": FileTypeSpec("toml", "config", "paragraph", "structured"),
    ".ini": FileTypeSpec("ini", "config", "paragraph", "structured"),
    ".env": FileTypeSpec("env", "config", "paragraph", "structured"),
    # Programming
    ".py": FileTypeSpec("python", "code", "code", "code"),
    ".java": FileTypeSpec("java", "code", "code", "code"),
    ".js": FileTypeSpec("javascript", "code", "code", "code"),
    ".ts": FileTypeSpec("typescript", "code", "code", "code"),
    ".tsx": FileTypeSpec("tsx", "code", "code", "code"),
    ".jsx": FileTypeSpec("jsx", "code", "code", "code"),
    ".cs": FileTypeSpec("csharp", "code", "code", "code"),
    ".vb": FileTypeSpec("vb", "code", "code", "code"),
    ".c": FileTypeSpec("c", "code", "code", "code"),
    ".cpp": FileTypeSpec("cpp", "code", "code", "code"),
    ".h": FileTypeSpec("c_header", "code", "code", "code"),
    ".hpp": FileTypeSpec("hpp", "code", "code", "code"),
    ".go": FileTypeSpec("go", "code", "code", "code"),
    ".rs": FileTypeSpec("rust", "code", "code", "code"),
    ".kt": FileTypeSpec("kotlin", "code", "code", "code"),
    ".swift": FileTypeSpec("swift", "code", "code", "code"),
    ".php": FileTypeSpec("php", "code", "code", "code"),
    ".rb": FileTypeSpec("ruby", "code", "code", "code"),
    ".scala": FileTypeSpec("scala", "code", "code", "code"),
    ".sql": FileTypeSpec("sql", "code", "code", "code"),
    ".ps1": FileTypeSpec("powershell", "code", "code", "code"),
    ".sh": FileTypeSpec("shell", "code", "code", "code"),
    ".bash": FileTypeSpec("bash", "code", "code", "code"),
    ".bat": FileTypeSpec("batch", "code", "code", "code"),
    # Infra/config engineering
    ".tf": FileTypeSpec("terraform", "config", "paragraph", "config"),
    ".bicep": FileTypeSpec("bicep", "config", "paragraph", "config"),
    # Images
    ".png": FileTypeSpec("png", "image", "image", "image"),
    ".jpeg": FileTypeSpec("jpeg", "image", "image", "image"),
    ".jpg": FileTypeSpec("jpg", "image", "image", "image"),
    ".tiff": FileTypeSpec("tiff", "image", "image", "image"),
    ".tif": FileTypeSpec("tif", "image", "image", "image"),
    ".gif": FileTypeSpec("gif", "image", "image", "image"),
    ".webp": FileTypeSpec("webp", "image", "image", "image"),
    ".bmp": FileTypeSpec("bmp", "image", "image", "image"),
    ".svg": FileTypeSpec("svg", "image", "image", "image"),
    # Email/web
    ".eml": FileTypeSpec("eml", "email", "email", "email"),
    ".msg": FileTypeSpec("msg", "email", "email", "email"),
    ".html": FileTypeSpec("html", "html", "paragraph", "web"),
    ".htm": FileTypeSpec("html", "html", "paragraph", "web"),
    # Engineering docs
    ".fds": FileTypeSpec("fds", "engineering", "engineering", "engineering"),
    ".urs": FileTypeSpec("urs", "engineering", "engineering", "engineering"),
    ".sds": FileTypeSpec("sds", "engineering", "engineering", "engineering"),
    ".pid": FileTypeSpec("pid", "engineering", "engineering", "engineering"),
}

FILE_NAME_SPECS: dict[str, FileTypeSpec] = {
    "dockerfile": FileTypeSpec("dockerfile", "config", "paragraph", "config"),
    "docker-compose.yml": FileTypeSpec(
        "docker_compose", "config", "paragraph", "config"
    ),
    "docker-compose.yaml": FileTypeSpec(
        "docker_compose", "config", "paragraph", "config"
    ),
    "chart.yaml": FileTypeSpec("helm", "config", "paragraph", "config"),
    "template.yaml": FileTypeSpec("cloudformation", "config", "paragraph", "config"),
    "azure-pipelines.yml": FileTypeSpec(
        "azure_pipeline", "config", "paragraph", "config"
    ),
    "azure-pipelines.yaml": FileTypeSpec(
        "azure_pipeline", "config", "paragraph", "config"
    ),
    "main.bicep": FileTypeSpec("bicep", "config", "paragraph", "config"),
    "template.bicep": FileTypeSpec("bicep", "config", "paragraph", "config"),
    "terraform.tf": FileTypeSpec("terraform", "config", "paragraph", "config"),
    "action.yml": FileTypeSpec("github_actions", "config", "paragraph", "config"),
    "action.yaml": FileTypeSpec("github_actions", "config", "paragraph", "config"),
    "gitlab-ci.yml": FileTypeSpec("gitlab_ci", "config", "paragraph", "config"),
    "gitlab-ci.yaml": FileTypeSpec("gitlab_ci", "config", "paragraph", "config"),
}


def detect_file_spec(file_name: str) -> FileTypeSpec:
    """Resolve parser/chunker routing metadata for a filename."""
    lowered = file_name.lower()
    if lowered in FILE_NAME_SPECS:
        return FILE_NAME_SPECS[lowered]

    extension = Path(lowered).suffix
    if extension and extension in FILE_TYPE_SPECS:
        return FILE_TYPE_SPECS[extension]

    return FileTypeSpec("unknown", "text", "paragraph", "document")
