import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError } from "../api/client";
import { uploadsApi } from "../api/uploads";
import type {
    UploadJobRecord,
    UploadProgressRecord,
    UploadSessionRecord,
    UploadSummaryRecord,
} from "../types/api";

interface MockFileDraft {
    file_name: string;
    file_size: number;
    mime_type: string;
    parser: string;
}

export const useUploads = (projectId: string) => {
    const [session, setSession] = useState<UploadSessionRecord | null>(null);
    const [jobs, setJobs] = useState<UploadJobRecord[]>([]);
    const [progress, setProgress] = useState<UploadProgressRecord | null>(null);
    const [summary, setSummary] = useState<UploadSummaryRecord | null>(null);
    const [health, setHealth] = useState<{ status: string; sessions: number; queued_jobs: number } | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [isMutating, setIsMutating] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const refresh = useCallback(async () => {
        if (!session) {
            try {
                const healthPayload = await uploadsApi.health();
                setHealth(healthPayload);
            } catch (err) {
                setError(err instanceof ApiError ? err.message : "Failed to load uploads.");
            }
            return;
        }

        setIsLoading(true);
        setError(null);
        try {
            const [sessionPayload, jobsPayload, progressPayload, summaryPayload, healthPayload] = await Promise.all([
                uploadsApi.getSession(session.id),
                uploadsApi.listJobs(session.id),
                uploadsApi.progress(session.id),
                uploadsApi.summary(session.id),
                uploadsApi.health(),
            ]);
            setSession(sessionPayload);
            setJobs(jobsPayload);
            setProgress(progressPayload);
            setSummary(summaryPayload);
            setHealth(healthPayload);
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "Failed to load upload session.");
        } finally {
            setIsLoading(false);
        }
    }, [session]);

    useEffect(() => {
        void refresh();
    }, [refresh]);

    useEffect(() => {
        setSession(null);
        setJobs([]);
        setProgress(null);
        setSummary(null);
        setError(null);
    }, [projectId]);

    const createSession = useCallback(async (sourceId: string) => {
        setIsMutating(true);
        setError(null);
        try {
            const created = await uploadsApi.createSession({
                project_id: projectId,
                source_id: sourceId,
                total_files: 0,
                metadata: { origin: "frontend" },
            });
            setSession(created);
            setJobs([]);
            return created;
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "Failed to create upload session.");
            throw err;
        } finally {
            setIsMutating(false);
        }
    }, [projectId]);

    const enqueueMockFiles = useCallback(async (files: MockFileDraft[]) => {
        if (!session) {
            throw new Error("No upload session selected.");
        }
        setIsMutating(true);
        setError(null);
        try {
            const created = await uploadsApi.enqueue(session.id, { files });
            setJobs(created);
            await refresh();
            return created;
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "Failed to enqueue upload files.");
            throw err;
        } finally {
            setIsMutating(false);
        }
    }, [refresh, session]);

    const cancel = useCallback(async () => {
        if (!session) {
            return;
        }
        setIsMutating(true);
        setError(null);
        try {
            await uploadsApi.cancel(session.id);
            await refresh();
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "Failed to cancel upload session.");
            throw err;
        } finally {
            setIsMutating(false);
        }
    }, [refresh, session]);

    const resume = useCallback(async () => {
        if (!session) {
            return;
        }
        setIsMutating(true);
        setError(null);
        try {
            await uploadsApi.resume(session.id);
            await refresh();
        } catch (err) {
            setError(err instanceof ApiError ? err.message : "Failed to resume upload session.");
            throw err;
        } finally {
            setIsMutating(false);
        }
    }, [refresh, session]);

    const remaining = useMemo(
        () => progress?.remaining_files ?? session?.total_files ?? 0,
        [progress?.remaining_files, session?.total_files]
    );

    return {
        session,
        jobs,
        progress,
        summary,
        health,
        remaining,
        isLoading,
        isMutating,
        error,
        refresh,
        createSession,
        enqueueMockFiles,
        cancel,
        resume,
    };
};
