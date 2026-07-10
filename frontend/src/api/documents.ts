import type {
    DocumentRecord,
    RetrievalResponse,
    RetrievedChunk,
} from "../types/api";
import { ApiError } from "./client";

const getBaseUrl = (): string => {
    const raw = (import.meta.env.VITE_API_BASE_URL ?? "").trim().replace(/\/$/, "");
    if (!raw) {
        throw new ApiError("VITE_API_BASE_URL is not configured.", 0);
    }
    const isAbsolute = /^https?:\/\//i.test(raw);
    const isRelative = raw.startsWith("/");

    if (!isAbsolute && !isRelative) {
        throw new ApiError(
            "VITE_API_BASE_URL must be an absolute URL or '/api'.",
            0,
        );
    }
    return raw;
};

const request = async <T>(path: string, init: RequestInit): Promise<T> => {
    const endpoint = `${getBaseUrl()}${path}`;
    let response: Response;

    try {
        response = await fetch(endpoint, init);
    } catch {
        throw new ApiError("Unable to connect to the SandSwap API.", 0);
    }

    if (!response.ok) {
        let message = `Request failed (${response.status})`;
        try {
            const payload = (await response.json()) as { detail?: string };
            if (payload.detail) {
                message = payload.detail;
            }
        } catch {
            message = response.statusText || message;
        }
        throw new ApiError(message, response.status);
    }

    if (response.status === 204) {
        return undefined as T;
    }

    return (await response.json()) as T;
};

export interface UploadDocumentParams {
    file: File;
    project?: string;
    tags?: string[];
    chunkSize?: number;
    overlap?: number;
}

export interface RetrieveChunksParams {
    query: string;
    topK?: number;
    documentId?: string;
    fileType?: string;
    category?: string;
}

export const documentsApi = {
    upload: async (params: UploadDocumentParams): Promise<DocumentRecord> => {
        const form = new FormData();
        form.append("file", params.file);
        if (params.project) {
            form.append("project", params.project);
        }
        if (params.tags && params.tags.length > 0) {
            form.append("tags", params.tags.join(","));
        }
        if (typeof params.chunkSize === "number") {
            form.append("chunk_size", String(params.chunkSize));
        }
        if (typeof params.overlap === "number") {
            form.append("overlap", String(params.overlap));
        }

        return request<DocumentRecord>("/documents/upload", {
            method: "POST",
            body: form,
        });
    },

    list: () =>
        request<DocumentRecord[]>("/documents", {
            method: "GET",
        }),

    getById: (id: string) =>
        request<DocumentRecord>(`/documents/${id}`, {
            method: "GET",
        }),

    listChunks: (id: string) =>
        request<RetrievedChunk[]>(`/documents/${id}/chunks`, {
            method: "GET",
        }),

    retrieve: (params: RetrieveChunksParams) =>
        request<RetrievalResponse>("/documents/retrieve", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                query: params.query,
                top_k: params.topK ?? 5,
                document_id: params.documentId,
                file_type: params.fileType,
                category: params.category,
            }),
        }),

    deleteOne: (id: string) =>
        request<void>(`/documents/${id}`, {
            method: "DELETE",
        }),

    deleteAll: () =>
        request<{ deleted: number }>("/documents", {
            method: "DELETE",
        }),
};
