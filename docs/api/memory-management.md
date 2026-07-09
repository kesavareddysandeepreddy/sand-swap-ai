# Memory Management API

Memory management endpoints are exposed by the FastAPI runtime under the `/memory` prefix.

## Endpoints

### GET /memory

Returns paginated memory records sorted by newest first.

Query params:

- `page` (int, default: 1)
- `page_size` (int, default: 20, max: 100)
- `search` (string, optional; matches key/value/summary)
- `category` (string, optional)
- `min_importance` (float in [0, 1], optional)

Example response:

```json
{
  "items": [
    {
      "id": "...",
      "user_id": "user-1",
      "memory_type": "profile",
      "category": "identity",
      "key": "name",
      "value": "Sandeep",
      "summary": "",
      "importance": 0.9,
      "confidence": 1.0,
      "source": "chat",
      "created_at": "2026-01-01T00:00:00+00:00",
      "updated_at": "2026-01-01T00:00:00+00:00",
      "metadata": {},
      "tags": []
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

### GET /memory/{memory_id}

Returns one memory record.

### PATCH /memory/{memory_id}

Updates editable fields:

- `category` (string)
- `key` (string)
- `value` (string)
- `importance` (float in [0, 1])

### DELETE /memory/{memory_id}

Deletes a single memory record.

### DELETE /memory

Deletes all memory records and returns:

```json
{
  "deleted": 12
}
```

## Frontend Integration

The React frontend provides a Memory page at `/memory` that supports:

- Search and filtering
- Importance threshold slider
- Inline edit + save
- Single delete and delete-all
- Detail drawer view
