"""SharePoint connector implementation using Microsoft Graph APIs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

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


class SharePointConnector(BaseConnector):
    """Connector for indexing SharePoint libraries and folders via Graph."""

    def __init__(self, *, ingestion_service: DocumentIngestionService) -> None:
        super().__init__(
            metadata=ConnectorMetadata(
                key="sharepoint",
                display_name="SharePoint",
                description="Microsoft SharePoint knowledge connector",
                tags=("sharepoint", "microsoft", "graph"),
            ),
            capabilities=ConnectorCapabilities(
                supports_discovery=True,
                supports_incremental_sync=True,
                supports_search=True,
                supports_list_items=True,
            ),
            configuration=ConnectorConfiguration(
                required_fields=("access_token", "tenant_id"),
                secret_fields=("access_token",),
                defaults={"graph_base_url": "https://graph.microsoft.com/v1.0"},
            ),
        )
        self._ingestion_service = ingestion_service
        self._connected = False
        self._connection_details: dict[str, Any] = {}

    def connect(self, *, config: dict[str, Any]) -> bool:
        valid, errors = self.validate(config=config)
        if not valid:
            raise ValueError(", ".join(errors))
        token = str(config.get("access_token", "")).strip()
        base_url = str(config.get("graph_base_url", "https://graph.microsoft.com/v1.0"))
        self._connected = self._validate_token(token=token, base_url=base_url)
        self._connection_details = {
            "tenant_id": str(config.get("tenant_id", "")),
            "connected_at": datetime.now(UTC).isoformat(),
        }
        return self._connected

    def disconnect(self) -> None:
        self._connected = False

    def validate(self, *, config: dict[str, Any]) -> tuple[bool, list[str]]:
        return self.configuration.validate(config)

    def discover(self, *, config: dict[str, Any]) -> list[dict[str, Any]]:
        self.connect(config=config)
        token = str(config.get("access_token", "")).strip()
        base_url = str(config.get("graph_base_url", "https://graph.microsoft.com/v1.0"))

        sites_payload = self._request_json(
            url=f"{base_url.rstrip('/')}/sites",
            token=token,
            params={"search": "*", "$top": 50},
        )
        sites = (
            sites_payload.get("value", []) if isinstance(sites_payload, dict) else []
        )

        site_items: list[dict[str, Any]] = []
        for site in sites:
            if not isinstance(site, dict):
                continue
            site_id = str(site.get("id", "")).strip()
            if not site_id:
                continue
            drives_payload = self._request_json(
                url=f"{base_url.rstrip('/')}/sites/{site_id}/drives",
                token=token,
                params={"$top": 50},
            )
            drives = (
                drives_payload.get("value", [])
                if isinstance(drives_payload, dict)
                else []
            )
            libraries: list[dict[str, Any]] = []
            for drive in drives:
                if not isinstance(drive, dict):
                    continue
                drive_id = str(drive.get("id", "")).strip()
                if not drive_id:
                    continue
                root_children_payload = self._request_json(
                    url=f"{base_url.rstrip('/')}/drives/{drive_id}/root/children",
                    token=token,
                    params={"$top": 100},
                )
                children = (
                    root_children_payload.get("value", [])
                    if isinstance(root_children_payload, dict)
                    else []
                )
                folders = [
                    {
                        "id": str(child.get("id", "")),
                        "name": str(child.get("name", "")),
                        "path": str(child.get("parentReference", {}).get("path", "")),
                    }
                    for child in children
                    if isinstance(child, dict) and isinstance(child.get("folder"), dict)
                ]
                libraries.append(
                    {
                        "id": drive_id,
                        "name": str(drive.get("name", "")),
                        "folders": folders,
                    }
                )
            site_items.append(
                {
                    "site_id": site_id,
                    "name": str(site.get("name", "")),
                    "web_url": str(site.get("webUrl", "")),
                    "libraries": libraries,
                }
            )

        return [{"sites": site_items}]

    def sync(self, *, config: dict[str, Any], source_id: str) -> SyncJob:
        job = SyncJob(
            connector_key=self.metadata.key, source_id=source_id, full_sync=True
        )
        job.mark_running()
        try:
            indexed = self._sync_selected_folders(config=config, source_id=source_id)
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
            indexed = self._sync_selected_folders(
                config=config,
                source_id=source_id,
                incremental=True,
                cursor=cursor,
            )
            job.metadata.update({"indexed_files": indexed})
            job.mark_success(items_processed=indexed)
        except Exception as exc:  # noqa: BLE001
            job.mark_failed(str(exc))
        return job

    def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            status="ok" if self._connected else "ready",
            connected=self._connected,
            last_checked_at=datetime.now(UTC),
            message="SharePoint connector available",
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
        token = str(config.get("access_token", "")).strip()
        base_url = str(config.get("graph_base_url", "https://graph.microsoft.com/v1.0"))
        payload = self._request_json(
            url=f"{base_url.rstrip('/')}/search/query",
            token=token,
            params=None,
            json_payload={
                "requests": [
                    {
                        "entityTypes": ["driveItem"],
                        "query": {"queryString": query},
                        "size": max(1, min(limit, 50)),
                    }
                ]
            },
            method="POST",
        )
        responses = payload.get("value", []) if isinstance(payload, dict) else []
        items: list[dict[str, Any]] = []
        for response in responses:
            if not isinstance(response, dict):
                continue
            hits_containers = response.get("hitsContainers", [])
            for container in (
                hits_containers if isinstance(hits_containers, list) else []
            ):
                for hit in (
                    container.get("hits", []) if isinstance(container, dict) else []
                ):
                    resource = hit.get("resource", {}) if isinstance(hit, dict) else {}
                    if not isinstance(resource, dict):
                        continue
                    items.append(
                        {
                            "name": str(resource.get("name", "")),
                            "web_url": str(resource.get("webUrl", "")),
                            "last_modified": str(
                                resource.get("lastModifiedDateTime", "")
                            ),
                        }
                    )
                    if len(items) >= limit:
                        return items
        return items

    def list_items(
        self,
        *,
        config: dict[str, Any],
        page_size: int = 100,
        cursor: str | None = None,
    ) -> list[dict[str, Any]]:
        _ = cursor
        discovered = self.discover(config=config)
        if not discovered:
            return []
        sites = (
            discovered[0].get("sites", []) if isinstance(discovered[0], dict) else []
        )
        flattened: list[dict[str, Any]] = []
        for site in sites if isinstance(sites, list) else []:
            if not isinstance(site, dict):
                continue
            libraries = site.get("libraries", [])
            for library in libraries if isinstance(libraries, list) else []:
                if not isinstance(library, dict):
                    continue
                flattened.append(
                    {
                        "site_id": str(site.get("site_id", "")),
                        "site_name": str(site.get("name", "")),
                        "library_id": str(library.get("id", "")),
                        "library_name": str(library.get("name", "")),
                    }
                )
                if len(flattened) >= max(1, min(page_size, 500)):
                    return flattened
        return flattened

    def _sync_selected_folders(
        self,
        *,
        config: dict[str, Any],
        source_id: str,
        incremental: bool = False,
        cursor: str | None = None,
    ) -> int:
        self.connect(config=config)
        token = str(config.get("access_token", "")).strip()
        base_url = str(config.get("graph_base_url", "https://graph.microsoft.com/v1.0"))
        selections = config.get("selected_folders", [])
        if not isinstance(selections, list) or not selections:
            return 0

        total_indexed = 0
        for selection in selections:
            if not isinstance(selection, dict):
                continue
            site_id = str(selection.get("site_id", "")).strip()
            drive_id = str(selection.get("library_id", "")).strip()
            folder_path = str(selection.get("folder_path", "")).strip()
            if not site_id or not drive_id:
                continue

            endpoint = f"{base_url.rstrip('/')}/drives/{drive_id}/root/children"
            if folder_path:
                endpoint = f"{base_url.rstrip('/')}/drives/{drive_id}/root:/{folder_path}:/children"

            children_payload = self._request_json(
                url=endpoint,
                token=token,
                params={"$top": 200},
            )
            children = (
                children_payload.get("value", [])
                if isinstance(children_payload, dict)
                else []
            )
            for child in children:
                if not isinstance(child, dict):
                    continue
                if isinstance(child.get("folder"), dict):
                    continue
                last_modified = str(child.get("lastModifiedDateTime", ""))
                if incremental and cursor and last_modified and last_modified <= cursor:
                    continue
                item_id = str(child.get("id", "")).strip()
                if not item_id:
                    continue
                content_response = requests.get(
                    f"{base_url.rstrip('/')}/drives/{drive_id}/items/{item_id}/content",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=30,
                )
                content_response.raise_for_status()
                content = content_response.content.decode("utf-8", errors="ignore")
                if not content.strip():
                    continue
                file_name = str(child.get("name", "file"))
                metadata = {
                    "connector_type": "SharePoint",
                    "site": str(selection.get("site_name", site_id)),
                    "library": str(selection.get("library_name", drive_id)),
                    "folder": folder_path,
                    "file_path": f"{folder_path}/{file_name}".strip("/"),
                    "version": str(child.get("eTag", "")),
                    "last_modified": last_modified,
                    "project": str(config.get("project_id", "default")),
                    "workspace_id": str(config.get("workspace_id", "default")),
                    "source_id": source_id,
                }
                self._ingestion_service.ingest_external_document(
                    name=file_name,
                    content=content,
                    metadata=metadata,
                    owner_id=str(config.get("owner_id", "anonymous")),
                    workspace_id=str(config.get("workspace_id", "default")),
                    project=str(config.get("project_id", "default")),
                )
                total_indexed += 1
        return total_indexed

    def _validate_token(self, *, token: str, base_url: str) -> bool:
        payload = self._request_json(
            url=f"{base_url.rstrip('/')}/me",
            token=token,
            params=None,
        )
        return isinstance(payload, dict) and bool(payload.get("id"))

    def _request_json(
        self,
        *,
        url: str,
        token: str,
        params: dict[str, Any] | None,
        method: str = "GET",
        json_payload: dict[str, Any] | None = None,
    ) -> Any:
        response = requests.request(
            method=method,
            url=url,
            params=params,
            json=json_payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json() if response.text else {}
