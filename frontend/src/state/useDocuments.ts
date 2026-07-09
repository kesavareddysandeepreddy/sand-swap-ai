import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError } from "../api/client";
import { documentsApi, type UploadDocumentParams } from "../api/documents";
import type { DocumentRecord, RetrievedChunk } from "../types/api";

export const useDocuments = () => {
    const [documents, setDocuments] = useState<DocumentRecord[]>([]);
    const [selectedDocument, setSelectedDocument] = useState<DocumentRecord | null>(null);
    const [selectedChunks, setSelectedChunks] = useState<RetrievedChunk[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const refresh = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const items = await documentsApi.list();
            setDocuments(items);
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "Failed to load documents.");
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        void refresh();
    }, [refresh]);

    const upload = useCallback(async (params: UploadDocumentParams) => {
        setIsUploading(true);
        setError(null);
        try {
            const document = await documentsApi.upload(params);
            setDocuments((previous) => [document, ...previous]);
            return document;
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "Failed to upload document.");
            throw err;
        } finally {
            setIsUploading(false);
        }
    }, []);

    const selectDocument = useCallback(async (document: DocumentRecord | null) => {
        setSelectedDocument(document);
        setSelectedChunks([]);
        if (!document) {
            return;
        }

        try {
            const chunks = await documentsApi.listChunks(document.id);
            setSelectedChunks(chunks);
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "Failed to load document chunks.");
        }
    }, []);

    const deleteOne = useCallback(async (id: string) => {
        setError(null);
        try {
            await documentsApi.deleteOne(id);
            setDocuments((previous) => previous.filter((document) => document.id !== id));
            setSelectedDocument((previous) => (previous?.id === id ? null : previous));
            setSelectedChunks((previous) =>
                previous.filter((chunk) => chunk.document_id !== id)
            );
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "Failed to delete document.");
            throw err;
        }
    }, []);

    const deleteAll = useCallback(async () => {
        setError(null);
        try {
            await documentsApi.deleteAll();
            setDocuments([]);
            setSelectedDocument(null);
            setSelectedChunks([]);
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "Failed to delete documents.");
            throw err;
        }
    }, []);

    const categories = useMemo(
        () => Array.from(new Set(documents.map((document) => document.metadata.category as string))).filter(Boolean),
        [documents]
    );

    return {
        documents,
        selectedDocument,
        selectedChunks,
        categories,
        isLoading,
        isUploading,
        error,
        refresh,
        upload,
        selectDocument,
        deleteOne,
        deleteAll,
    };
};
