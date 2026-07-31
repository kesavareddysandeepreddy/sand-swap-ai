"""GitHub connector implementation using PAT authentication and repository sync."""

from __future__ import annotations

import base64
import binascii
import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import requests

from backend.knowledge_connectors.base import BaseConnector
from backend.knowledge_connectors.models import (
    ConnectorCapabilities,
    ConnectorConfiguration,
    ConnectorHealth,
    ConnectorMetadata,
    SyncJob,
)
from backend.rag.application.document_service import DocumentIngestionService


class GitHubConnector(BaseConnector):
    """Connector for indexing GitHub repositories into existing RAG pipeline."""

    _SUPPORTED_EXTENSIONS: set[str] = {
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".json",
        ".md",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
        ".xml",
        ".sql",
        ".sh",
        ".bash",
        ".ps1",
        ".go",
        ".rs",
        ".java",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".cs",
        ".rb",
        ".php",
        ".swift",
        ".kt",
        ".scala",
        ".txt",
        ".env",
        ".dockerfile",
    }
    _SUPPORTED_FILE_NAMES: set[str] = {
        "dockerfile",
        "makefile",
        "readme",
        "readme.md",
        "readme.txt",
        "license",
        "license.md",
        "pyproject.toml",
        "package.json",
        "tsconfig.json",
        "docker-compose.yml",
        "docker-compose.yaml",
    }

    def __init__(self, *, ingestion_service: DocumentIngestionService) -> None:
        super().__init__(
            metadata=ConnectorMetadata(
                key="github",
                display_name="GitHub",
                description="GitHub repository knowledge connector",
                tags=("github", "git", "scm"),
            ),
            capabilities=ConnectorCapabilities(
                supports_discovery=True,
                supports_incremental_sync=True,
                supports_search=True,
                supports_list_items=True,
            ),
            configuration=ConnectorConfiguration(
                required_fields=("token",),
                secret_fields=("token",),
                defaults={"base_url": "https://api.github.com"},
            ),
        )
        self._ingestion_service = ingestion_service
        self._connected = False
        self._status = "ready"
        self._connection_details: dict[str, Any] = {}
        self._logger = logging.getLogger(__name__)

    def connect(self, *, config: dict[str, Any]) -> bool:
        valid, errors = self.validate(config=config)
        if not valid:
            raise ValueError(", ".join(errors))
        token = str(config.get("token", "")).strip()
        if not token:
            raise ValueError("Missing required configuration field 'token'")
        try:
            self._connected = self._validate_token(
                token=token,
                base_url=str(config.get("base_url", "https://api.github.com")),
            )
        except requests.exceptions.RequestException as exc:
            self._logger.warning(
                "GitHub connector network error during connect(); marking authentication_failed: %s",
                exc,
            )
            self.mark_authentication_failed(detail=str(exc))
            return False
        self._status = "ok" if self._connected else "ready"
        self._connection_details = {
            "base_url": str(config.get("base_url", "https://api.github.com")),
            "connected_at": datetime.now(UTC).isoformat(),
        }
        return self._connected

    def disconnect(self) -> None:
        self._connected = False
        self._status = "ready"

    def mark_authentication_failed(self, *, detail: str = "") -> None:
        """Mark connector as requiring re-authentication without dropping config."""
        self._connected = False
        self._status = "authentication_failed"
        if detail:
            self._connection_details["auth_error"] = detail

    def validate(self, *, config: dict[str, Any]) -> tuple[bool, list[str]]:
        return self.configuration.validate(config)

    def discover(self, *, config: dict[str, Any]) -> list[dict[str, Any]]:
        self.connect(config=config)
        token = str(config.get("token", "")).strip()
        base_url = str(config.get("base_url", "https://api.github.com"))
        repositories = self._request_json(
            method="GET",
            url=f"{base_url.rstrip('/')}/user/repos",
            token=token,
            params={"per_page": 100, "sort": "updated"},
        )
        organizations = self._request_json(
            method="GET",
            url=f"{base_url.rstrip('/')}/user/orgs",
            token=token,
            params={"per_page": 100},
        )

        items: list[dict[str, Any]] = []
        for repo in repositories if isinstance(repositories, list) else []:
            default_branch = str(repo.get("default_branch", "main"))
            owner = repo.get("owner") or {}
            owner_login = str(owner.get("login", ""))
            repo_name = str(repo.get("name", ""))
            full_name = str(repo.get("full_name", f"{owner_login}/{repo_name}"))
            branch_items = self._list_branches(
                base_url=base_url,
                token=token,
                owner=owner_login,
                repo=repo_name,
            )
            items.append(
                {
                    "type": "repository",
                    "repository": full_name,
                    "name": repo_name,
                    "owner": owner_login,
                    "default_branch": default_branch,
                    "branches": branch_items,
                    "private": bool(repo.get("private", False)),
                    "updated_at": str(repo.get("updated_at", "")),
                }
            )

        return [
            {
                "organizations": [
                    {
                        "login": str(org.get("login", "")),
                        "id": org.get("id"),
                    }
                    for org in (
                        organizations if isinstance(organizations, list) else []
                    )
                ],
                "repositories": items,
            }
        ]

    def sync(self, *, config: dict[str, Any], source_id: str) -> SyncJob:
        job = SyncJob(
            connector_key=self.metadata.key, source_id=source_id, full_sync=True
        )
        job.mark_running()
        try:
            indexed = self._sync_selected_repositories(
                config=config, source_id=source_id
            )
            job.metadata = {"indexed_files": indexed}
            job.mark_success(items_processed=indexed)
        except Exception as exc:  # noqa: BLE001
            job.mark_failed(str(exc))
        return job

    def incremental_sync(
        self,
        *,
        config: dict[str, Any],
        source_id: str,
        cursor: str | None = None,
    ) -> SyncJob:
        job = SyncJob(
            connector_key=self.metadata.key,
            source_id=source_id,
            full_sync=False,
            metadata={"cursor": cursor or ""},
        )
        job.mark_running()
        try:
            indexed = self._sync_selected_repositories(
                config=config,
                source_id=source_id,
                incremental=True,
                cursor=cursor,
            )
            job.metadata.update({"indexed_files": indexed, "cursor": cursor or ""})
            job.mark_success(items_processed=indexed)
        except Exception as exc:  # noqa: BLE001
            job.mark_failed(str(exc))
        return job

    def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            status=self._status,
            connected=self._connected,
            last_checked_at=datetime.now(UTC),
            message="GitHub connector available",
            details=dict(self._connection_details),
        )

    def search(
        self,
        *,
        config: dict[str, Any],
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        self.connect(config=config)
        token = str(config.get("token", "")).strip()
        base_url = str(config.get("base_url", "https://api.github.com"))
        payload = self._request_json(
            method="GET",
            url=f"{base_url.rstrip('/')}/search/repositories",
            token=token,
            params={"q": query, "per_page": max(1, min(limit, 50))},
        )
        items = payload.get("items", []) if isinstance(payload, dict) else []
        return [
            {
                "repository": str(item.get("full_name", "")),
                "description": (
                    str(item.get("description", ""))
                    if item.get("description") is not None
                    else ""
                ),
                "updated_at": str(item.get("updated_at", "")),
            }
            for item in items
            if isinstance(item, dict)
        ]

    def list_items(
        self,
        *,
        config: dict[str, Any],
        page_size: int = 100,
        cursor: str | None = None,
    ) -> list[dict[str, Any]]:
        _ = cursor
        self.connect(config=config)
        token = str(config.get("token", "")).strip()
        base_url = str(config.get("base_url", "https://api.github.com"))
        repositories = self._request_json(
            method="GET",
            url=f"{base_url.rstrip('/')}/user/repos",
            token=token,
            params={"per_page": max(1, min(page_size, 100)), "sort": "updated"},
        )
        return [
            {
                "repository": str(repo.get("full_name", "")),
                "default_branch": str(repo.get("default_branch", "main")),
                "private": bool(repo.get("private", False)),
            }
            for repo in (repositories if isinstance(repositories, list) else [])
            if isinstance(repo, dict)
        ]

    def _sync_selected_repositories(
        self,
        *,
        config: dict[str, Any],
        source_id: str,
        incremental: bool = False,
        cursor: str | None = None,
    ) -> int:
        self.connect(config=config)
        token = str(config.get("token", "")).strip()
        base_url = str(config.get("base_url", "https://api.github.com"))
        selected = config.get("selected_repositories", [])
        if not isinstance(selected, list) or not selected:
            return 0

        self._logger.debug(
            "GITHUB_SYNC_START source_id=%s owner_id=%s workspace_id=%s project_id=%s repositories=%s",
            source_id,
            config.get("owner_id", ""),
            config.get("workspace_id", ""),
            config.get("project_id", ""),
            [item.get("repository") for item in selected if isinstance(item, dict)],
        )

        total_indexed = 0
        total_discovered = 0
        total_after_filter = 0
        total_skipped = 0
        total_ingest_errors = 0

        for item in selected:
            if not isinstance(item, dict):
                continue
            full_name = str(item.get("repository", "")).strip()
            if "/" not in full_name:
                continue
            owner, repo = full_name.split("/", 1)
            branch = (
                str(item.get("branch", item.get("default_branch", "main"))).strip()
                or "main"
            )
            commits = self._request_json(
                method="GET",
                url=f"{base_url.rstrip('/')}/repos/{owner}/{repo}/commits",
                token=token,
                params={"sha": branch, "per_page": 1},
            )
            commit_sha = ""
            if isinstance(commits, list) and commits:
                top = commits[0]
                if isinstance(top, dict):
                    commit_sha = str(top.get("sha", ""))
            if incremental and cursor and commit_sha and commit_sha == cursor:
                continue

            discovered_paths = self._discover_repository_blob_paths(
                base_url=base_url,
                token=token,
                owner=owner,
                repo=repo,
                branch=branch,
            )
            discovered_count = len(discovered_paths)
            total_discovered += discovered_count

            filtered_paths = [
                path
                for path in discovered_paths
                if self._is_supported_source_file(path)
            ]
            filtered_count = len(filtered_paths)
            total_after_filter += filtered_count
            skipped_for_filter = max(0, discovered_count - filtered_count)
            total_skipped += skipped_for_filter

            indexed_for_repo = 0
            skipped_for_repo = skipped_for_filter
            ingest_errors_for_repo = 0

            for path in filtered_paths:
                blob_payload = self._fetch_blob_by_path(
                    base_url=base_url,
                    token=token,
                    owner=owner,
                    repo=repo,
                    branch=branch,
                    path=path,
                )
                if not isinstance(blob_payload, dict):
                    skipped_for_repo += 1
                    continue

                content = str(blob_payload.get("content", ""))
                encoding = str(blob_payload.get("encoding", "base64"))
                if encoding != "base64" or not content:
                    skipped_for_repo += 1
                    continue

                try:
                    decoded = self._decode_base64(content)
                except (ValueError, binascii.Error):
                    skipped_for_repo += 1
                    continue

                if not decoded.strip():
                    skipped_for_repo += 1
                    continue

                filename = path.rsplit("/", 1)[-1] or path
                metadata = {
                    "connector_type": "GitHub",
                    "repository": f"{owner}/{repo}",
                    "branch": branch,
                    "file_path": path,
                    "commit_sha": commit_sha,
                    "language": self._language_for_path(path),
                    "last_modified": datetime.now(UTC).isoformat(),
                    "project": str(config.get("project_id", "default")),
                    "workspace_id": str(config.get("workspace_id", "default")),
                    "source_id": source_id,
                    "blob_sha": str(blob_payload.get("sha", "")),
                }
                try:
                    doc = self._ingestion_service.ingest_external_document(
                        name=filename,
                        content=decoded,
                        metadata=metadata,
                        owner_id=str(config.get("owner_id", "anonymous")),
                        workspace_id=str(config.get("workspace_id", "default")),
                        project=str(config.get("project_id", "default")),
                    )
                    self._logger.debug(
                        "INGEST_DOCUMENT document_id=%s owner_id=%s workspace_id=%s project_id=%s repository=%s path=%s",
                        doc.id,
                        doc.metadata.get("owner_id"),
                        doc.metadata.get("workspace_id"),
                        doc.metadata.get("project"),
                        f"{owner}/{repo}",
                        path,
                    )
                except Exception:  # noqa: BLE001
                    ingest_errors_for_repo += 1
                    skipped_for_repo += 1
                    self._logger.warning(
                        "GitHub ingest failed for %s@%s (%s)",
                        full_name,
                        branch,
                        path,
                        exc_info=True,
                    )
                    continue

                indexed_for_repo += 1

            total_indexed += indexed_for_repo
            total_skipped += max(0, skipped_for_repo - skipped_for_filter)
            total_ingest_errors += ingest_errors_for_repo
            self._logger.info(
                "GitHub ingestion stats for %s@%s: discovered=%d after_filter=%d skipped=%d indexed=%d ingest_errors=%d",
                full_name,
                branch,
                discovered_count,
                filtered_count,
                skipped_for_repo,
                indexed_for_repo,
                ingest_errors_for_repo,
            )

        self._logger.info(
            "GitHub ingestion totals: discovered=%d after_filter=%d skipped=%d indexed=%d ingest_errors=%d",
            total_discovered,
            total_after_filter,
            total_skipped,
            total_indexed,
            total_ingest_errors,
        )
        return total_indexed

    def _discover_repository_blob_paths(
        self,
        *,
        base_url: str,
        token: str,
        owner: str,
        repo: str,
        branch: str,
    ) -> list[str]:
        branch_payload = self._request_json(
            method="GET",
            url=f"{base_url.rstrip('/')}/repos/{owner}/{repo}/branches/{quote(branch, safe='')}",
            token=token,
            params=None,
        )
        tree_sha = ""
        if isinstance(branch_payload, dict):
            commit = branch_payload.get("commit", {})
            if isinstance(commit, dict):
                commit_data = commit.get("commit", {})
                if isinstance(commit_data, dict):
                    tree = commit_data.get("tree", {})
                    if isinstance(tree, dict):
                        tree_sha = str(tree.get("sha", "")).strip()
        if not tree_sha:
            raise ValueError(
                f"Unable to resolve tree SHA for branch '{branch}' in {owner}/{repo}"
            )

        tree_payload = self._request_json(
            method="GET",
            url=f"{base_url.rstrip('/')}/repos/{owner}/{repo}/git/trees/{tree_sha}",
            token=token,
            params={"recursive": "1"},
        )
        tree_items = (
            tree_payload.get("tree", []) if isinstance(tree_payload, dict) else []
        )
        blob_paths: list[str] = []
        for tree_item in tree_items if isinstance(tree_items, list) else []:
            if not isinstance(tree_item, dict):
                continue
            if str(tree_item.get("type", "")) != "blob":
                continue
            path = str(tree_item.get("path", "")).strip()
            if path:
                blob_paths.append(path)

        if isinstance(tree_payload, dict) and bool(
            tree_payload.get("truncated", False)
        ):
            self._logger.warning(
                "GitHub tree response truncated for %s/%s@%s; falling back to recursive contents traversal",
                owner,
                repo,
                branch,
            )
            return self._walk_repository_contents(
                base_url=base_url,
                token=token,
                owner=owner,
                repo=repo,
                branch=branch,
            )

        return blob_paths

    def _walk_repository_contents(
        self,
        *,
        base_url: str,
        token: str,
        owner: str,
        repo: str,
        branch: str,
    ) -> list[str]:
        discovered: list[str] = []
        queue: list[str] = [""]

        while queue:
            directory = queue.pop(0)
            if directory:
                encoded = quote(directory, safe="/")
                url = f"{base_url.rstrip('/')}/repos/{owner}/{repo}/contents/{encoded}"
            else:
                url = f"{base_url.rstrip('/')}/repos/{owner}/{repo}/contents"

            payload = self._request_json(
                method="GET",
                url=url,
                token=token,
                params={"ref": branch},
            )
            for entry in payload if isinstance(payload, list) else []:
                if not isinstance(entry, dict):
                    continue
                entry_type = str(entry.get("type", "")).strip()
                entry_path = str(entry.get("path", "")).strip()
                if not entry_path:
                    continue
                if entry_type == "file":
                    discovered.append(entry_path)
                elif entry_type == "dir":
                    queue.append(entry_path)

        return discovered

    def _fetch_blob_by_path(
        self,
        *,
        base_url: str,
        token: str,
        owner: str,
        repo: str,
        branch: str,
        path: str,
    ) -> Any:
        encoded_path = quote(path, safe="/")
        return self._request_json(
            method="GET",
            url=f"{base_url.rstrip('/')}/repos/{owner}/{repo}/contents/{encoded_path}",
            token=token,
            params={"ref": branch},
        )

    @classmethod
    def _is_supported_source_file(cls, path: str) -> bool:
        lowered = path.strip().lower()
        if not lowered:
            return False
        filename = lowered.rsplit("/", 1)[-1]
        if filename in cls._SUPPORTED_FILE_NAMES:
            return True
        for extension in cls._SUPPORTED_EXTENSIONS:
            if lowered.endswith(extension):
                return True
        return False

    def _validate_token(self, *, token: str, base_url: str) -> bool:
        payload = self._request_json(
            method="GET",
            url=f"{base_url.rstrip('/')}/user",
            token=token,
            params=None,
        )
        return isinstance(payload, dict) and bool(payload.get("login"))

    def _list_branches(
        self,
        *,
        base_url: str,
        token: str,
        owner: str,
        repo: str,
    ) -> list[str]:
        if not owner or not repo:
            return []
        payload = self._request_json(
            method="GET",
            url=f"{base_url.rstrip('/')}/repos/{owner}/{repo}/branches",
            token=token,
            params={"per_page": 100},
        )
        branches: list[str] = []
        for item in payload if isinstance(payload, list) else []:
            if isinstance(item, dict):
                branch_name = str(item.get("name", "")).strip()
                if branch_name:
                    branches.append(branch_name)
        return branches

    def _request_json(
        self,
        *,
        method: str,
        url: str,
        token: str,
        params: dict[str, Any] | None,
    ) -> Any:
        response = requests.request(
            method=method,
            url=url,
            params=params,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _language_for_path(path: str) -> str:
        suffix = path.rsplit(".", 1)[-1].lower() if "." in path else ""
        mapping = {
            "py": "python",
            "ts": "typescript",
            "tsx": "typescript",
            "js": "javascript",
            "jsx": "javascript",
            "md": "markdown",
            "json": "json",
            "yml": "yaml",
            "yaml": "yaml",
            "go": "go",
            "rs": "rust",
            "java": "java",
            "cs": "csharp",
            "cpp": "cpp",
            "c": "c",
        }
        return mapping.get(suffix, suffix or "text")

    @staticmethod
    def _decode_base64(payload: str) -> str:
        normalized = payload.replace("\n", "")
        raw = base64.b64decode(normalized)
        return raw.decode("utf-8", errors="ignore")
