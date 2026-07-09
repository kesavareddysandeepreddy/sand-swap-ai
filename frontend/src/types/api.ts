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

export interface DocumentRecord {
    id: string;
    name: string;
    original_filename: string;
    stored_path: string;
    file_type: string;
    size_bytes: number;
    chunk_count: number;
    embedding_status: string;
    index_status: string;
    metadata: Record<string, unknown>;
    created_at: string;
    updated_at: string;
}

export interface RetrievedChunk {
    chunk_id: string;
    document_id: string;
    document_name: string;
    text: string;
    score: number;
    metadata: Record<string, unknown>;
}

export interface RetrievalResponse {
    chunks: RetrievedChunk[];
    citations: string[];
}
