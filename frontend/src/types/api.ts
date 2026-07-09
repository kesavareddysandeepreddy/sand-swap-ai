export interface HealthResponse {
    status: string;
    service: string;
    version: string;
}

export interface ChatRequest {
    user_id: string;
    message: string;
    conversation_id?: string;
}

export interface ChatResponse {
    conversation_id: string;
    response: string;
    memories_saved: number;
}

export interface ApiErrorPayload {
    detail?: string;
}

export interface MemoryRecord {
    id: string;
    user_id: string;
    memory_type: string;
    key: string;
    value: string;
    category: string;
    summary: string;
    importance: number;
    confidence: number;
    source: string;
    created_at: string;
    updated_at: string;
    metadata: Record<string, unknown>;
    tags: string[];
}

export interface MemoryListResponse {
    items: MemoryRecord[];
    total: number;
    page: number;
    page_size: number;
}

export interface MemoryUpdateRequest {
    category?: string;
    key?: string;
    value?: string;
    importance?: number;
}
