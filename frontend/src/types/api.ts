export interface HealthResponse {
    status: string;
    service: string;
    version: string;
}

export interface ChatRequest {
    user_id: string;
    message: string;
    conversation_id?: string;
    model?: string;
}

export interface ChatResponse {
    conversation_id: string;
    response: string;
    memories_saved: number;
}

export interface ChatModelsResponse {
    models: string[];
}

export interface ChatConversationMessage {
    id: string;
    role: "user" | "assistant";
    content: string;
    created_at: string;
}

export interface ChatConversationRecord {
    id: string;
    title: string;
    updated_at: string;
    messages: ChatConversationMessage[];
}

export interface ChatConversationListResponse {
    items: ChatConversationRecord[];
}

export interface ChatConversationDeleteResponse {
    conversation_id: string;
    deleted: boolean;
    database_deleted: boolean;
    cache_deleted: boolean;
    memory_deleted: boolean;
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
    workspace_id?: string | null;
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

export interface ProjectRecord {
    id: string;
    workspace_id: string;
    name: string;
    description: string;
    created_at: string;
    is_active: boolean;
}

export interface CreateProjectRequest {
    name: string;
    description?: string;
    set_active?: boolean;
}

export interface RenameProjectRequest {
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

export type KnowledgeSourceType =
    | "Upload"
    | "GitHub"
    | "SharePoint"
    | "OneDrive"
    | "GoogleDrive"
    | "AzureDevOps"
    | "Jira"
    | "Confluence"
    | "Website"
    | "Database"
    | "Custom";

export interface KnowledgeSourceRecord {
    id: string;
    project_id: string;
    name: string;
    source_type: KnowledgeSourceType;
    connection_config: Record<string, unknown>;
    enabled: boolean;
    status: string;
    file_count: number;
    chunk_count: number;
    embedding_count: number;
    last_sync: string | null;
    created_at: string;
    updated_at: string;
    metadata: Record<string, unknown>;
}

export interface AgentRecord {
    id: string;
    name: string;
    description: string;
    instructions: string;
    system_prompt: string;
    role: string;
    goal: string;
    expected_output: string;
    temperature: number;
    model: string;
    enabled: boolean;
    color: string;
    icon: string;
    capabilities: string[];
    agent_memory_enabled: boolean;
    project_memory_enabled: boolean;
    long_term_memory_enabled: boolean;
    conversation_memory_enabled: boolean;
    memory_importance: number;
    memory_scope: string;
    knowledge_source_ids: string[];
    document_library_ids: string[];
    github_repositories: string[];
    sharepoint_sites: string[];
    uploaded_document_ids: string[];
    project_knowledge_enabled: boolean;
    tools_allowed: string[];
    tool_permissions: Record<string, boolean>;
    connectors_allowed: string[];
    execution_mode: "sequential" | "parallel";
    approval_required: boolean;
    max_iterations: number;
    timeout: number;
    retry_count: number;
    retry_policy: Record<string, unknown>;
    tags: string[];
    connected_agent_ids: string[];
    owner_id: string;
    workspace_id: string;
    project_id: string;
    created_at: string;
    updated_at: string;
    objective?: string;
    short_term_enabled?: boolean;
    long_term_enabled?: boolean;
}

export interface AgentCreateRequest {
    name: string;
    description?: string;
    instructions?: string;
    role: string;
    objective?: string;
    system_prompt: string;
    goal?: string;
    expected_output?: string;
    temperature?: number;
    model?: string;
    enabled?: boolean;
    short_term_enabled?: boolean;
    long_term_enabled?: boolean;
    color?: string;
    icon?: string;
    capabilities?: string[];
    agent_memory_enabled?: boolean;
    project_memory_enabled?: boolean;
    long_term_memory_enabled?: boolean;
    conversation_memory_enabled?: boolean;
    memory_importance?: number;
    memory_scope?: string;
    knowledge_source_ids?: string[];
    document_library_ids?: string[];
    github_repositories?: string[];
    sharepoint_sites?: string[];
    uploaded_document_ids?: string[];
    project_knowledge_enabled?: boolean;
    tools_allowed?: string[];
    tool_permissions?: Record<string, boolean>;
    connectors_allowed?: string[];
    execution_mode?: "sequential" | "parallel";
    approval_required?: boolean;
    max_iterations?: number;
    timeout?: number;
    retry_count?: number;
    retry_policy?: Record<string, unknown>;
    tags?: string[];
    connected_agent_ids?: string[];
}

export interface AgentUpdateRequest {
    name?: string;
    description?: string | null;
    instructions?: string | null;
    role?: string;
    objective?: string | null;
    system_prompt?: string;
    goal?: string | null;
    expected_output?: string | null;
    temperature?: number;
    model?: string | null;
    enabled?: boolean;
    short_term_enabled?: boolean;
    long_term_enabled?: boolean;
    color?: string | null;
    icon?: string | null;
    capabilities?: string[];
    agent_memory_enabled?: boolean;
    project_memory_enabled?: boolean;
    long_term_memory_enabled?: boolean;
    conversation_memory_enabled?: boolean;
    memory_importance?: number;
    memory_scope?: string | null;
    knowledge_source_ids?: string[];
    document_library_ids?: string[];
    github_repositories?: string[];
    sharepoint_sites?: string[];
    uploaded_document_ids?: string[];
    project_knowledge_enabled?: boolean;
    tools_allowed?: string[];
    tool_permissions?: Record<string, boolean>;
    connectors_allowed?: string[];
    execution_mode?: "sequential" | "parallel";
    approval_required?: boolean;
    max_iterations?: number;
    timeout?: number;
    retry_count?: number;
    retry_policy?: Record<string, unknown>;
    tags?: string[];
    connected_agent_ids?: string[];
}

export interface AgentVersionResponse {
    id: string;
    agent_id: string;
    version_number: number;
    change_summary: string;
    snapshot: Record<string, unknown>;
    created_at: string;
}

export interface AgentVersionCompareItem {
    field: string;
    before: unknown;
    after: unknown;
}

export interface AgentVersionCompareResponse {
    agent_id: string;
    left_version: number;
    right_version: number;
    differences: AgentVersionCompareItem[];
}

export interface AgentToolCallResponse {
    tool_name: string;
    input: Record<string, unknown>;
    success: boolean;
    output: Record<string, unknown>;
    duration_ms: number;
    error: string | null;
}

export interface AgentExecutionStepResponse {
    step_name: string;
    tool_name: string;
    output: Record<string, unknown>;
    duration_ms: number;
}

export interface AgentTestRequest {
    prompt: string;
}

export interface AgentTestRunResponse {
    id: string;
    agent_id: string;
    prompt: string;
    reasoning: string;
    tool_calls: AgentToolCallResponse[];
    execution: AgentExecutionStepResponse[];
    final_answer: string;
    success: boolean;
    error: string | null;
    timing_ms: number;
    created_at: string;
}

export interface AgentDashboardResponse {
    agent_id: string;
    status: string;
    last_run_at: string | null;
    success_rate: number;
    average_runtime_ms: number;
    memory_usage: string;
    knowledge_source_count: number;
    connected_agent_count: number;
    total_versions: number;
}

export interface CreateKnowledgeSourceRequest {
    project_id: string;
    name: string;
    source_type: KnowledgeSourceType;
    connection_config?: Record<string, unknown>;
    metadata?: Record<string, unknown>;
}

export interface DeleteKnowledgeSourceResponse {
    deleted: boolean;
}

export interface KnowledgeSourcesHealthResponse {
    status: string;
    connectors_total: number;
    connectors: Record<string, string>;
}

export interface ConnectorOperationResponse {
    source_id: string;
    status: string;
    detail: string;
    metadata: Record<string, unknown>;
}

export interface ConnectorDiscoveryResponse {
    source_id: string;
    items: Array<Record<string, unknown>>;
}

export interface UploadSessionRecord {
    id: string;
    project_id: string;
    source_id: string;
    status: string;
    total_files: number;
    processed_files: number;
    failed_files: number;
    skipped_files: number;
    started_at: string;
    completed_at: string | null;
    current_file: string | null;
    metadata: Record<string, unknown>;
}

export interface UploadJobRecord {
    id: string;
    session_id: string;
    file_name: string;
    file_size: number;
    mime_type: string;
    parser: string;
    status: string;
    chunks_created: number;
    embeddings_created: number;
    started_at: string | null;
    completed_at: string | null;
    error: string | null;
}

export interface UploadProgressRecord {
    session_id: string;
    status: string;
    total_files: number;
    processed_files: number;
    remaining_files: number;
    failed_files: number;
    skipped_files: number;
    progress_percent: number;
    current_file: string | null;
    eta: string | null;
}

export interface UploadSummaryRecord {
    session_id: string;
    status: string;
    processed_files: number;
    remaining_files: number;
    failed_files: number;
    skipped_files: number;
    current_file: string | null;
}

export interface CreateUploadSessionRequest {
    project_id: string;
    source_id: string;
    total_files?: number;
    metadata?: Record<string, unknown>;
}

export interface EnqueueUploadFilesRequest {
    files: Array<{
        file_name: string;
        file_size: number;
        mime_type: string;
        parser: string;
    }>;
}

export interface ExecutionTraceSummary {
    trace_id: string;
    worker_name: string;
    request_id: string | null;
    started_at: string;
    completed_at: string | null;
    total_duration_ms: number;
}

export interface ExecutionStep {
    id: string;
    stage: string;
    status: string;
    started_at: string | null;
    completed_at: string | null;
    duration_ms: number;
    metadata: Record<string, unknown>;
}

export type ExecutionState = "planning" | "executing" | "completed" | "failed";

export interface TaskPlanStep {
    step_id: string;
    order: number;
    title: string;
    action: string;
    target: string;
    capabilities: string[];
    estimated_cost: number;
    complexity: string;
}

export interface TaskPlanDependency {
    predecessor_step_id: string;
    successor_step_id: string;
    reason: string;
}

export interface TaskPlanGoal {
    original_request: string;
    actions: string[];
    targets: string[];
    constraints: string[];
    expected_outputs: string[];
}

export interface TaskPlan {
    goal: TaskPlanGoal;
    steps: TaskPlanStep[];
    dependencies: TaskPlanDependency[];
    inferred_capabilities: string[];
    estimated_total_cost: number;
    overall_complexity: string;
}

export interface ExecutionTraceDetail extends ExecutionTraceSummary {
    metadata: Record<string, unknown>;
    steps: ExecutionStep[];
}
