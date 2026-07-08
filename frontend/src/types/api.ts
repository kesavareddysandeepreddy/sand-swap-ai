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
