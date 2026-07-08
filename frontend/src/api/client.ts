import type {
  ApiErrorPayload,
  ChatRequest,
  ChatResponse,
  HealthResponse,
} from "../types/api";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export class ApiClient {
  private readonly baseUrl: string;

  constructor(baseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000") {
    this.baseUrl = baseUrl.replace(/\/$/, "");
  }

  async getHealth(): Promise<HealthResponse> {
    return this.request<HealthResponse>("/health", {
      method: "GET",
    });
  }

  async sendChatMessage(payload: ChatRequest): Promise<ChatResponse> {
    return this.request<ChatResponse>("/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
  }

  private async request<T>(path: string, init: RequestInit): Promise<T> {
    let response: Response;

    try {
      response = await fetch(`${this.baseUrl}${path}`, init);
    } catch {
      throw new ApiError("Unable to connect to the SandSwap API.", 0);
    }

    if (!response.ok) {
      let message = `Request failed (${response.status})`;
      try {
        const payload = (await response.json()) as ApiErrorPayload;
        if (payload.detail) {
          message = payload.detail;
        }
      } catch {
        message = response.statusText || message;
      }
      throw new ApiError(message, response.status);
    }

    return (await response.json()) as T;
  }
}

export const apiClient = new ApiClient();
