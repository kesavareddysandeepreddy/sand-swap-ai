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

export interface AuthLoginRequest {
    email: string;
    password: string;
}

export interface AuthTokenPair {
    access_token: string;
    refresh_token: string;
    token_type: string;
}

export interface RefreshTokenRequest {
    refresh_token: string;
}

export interface LogoutRequest {
    refresh_token: string | null;
}

export interface GoogleOAuthExchangeRequest {
    code: string;
    redirect_uri: string;
}

export interface AuthUserProfile {
    user_id: string;
    email: string;
    display_name: string;
    project_id?: string | null;
    avatar_url?: string | null;
    auth_provider?: string | null;
    google_subject_id?: string | null;
}

export interface WorkspaceRecord {
    id: string;
    name: string;
    description: string;
    created_at: string;
    is_active: boolean;
}

export interface CreateWorkspaceRequest {
    name: string;
    description?: string;
    set_active?: boolean;
}

export interface RenameWorkspaceRequest {
    name: string;
    description?: string | null;
}

export interface GoogleOAuthStartResponse {
    provider: string;
    authorization_url: string;
    state: string;
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
