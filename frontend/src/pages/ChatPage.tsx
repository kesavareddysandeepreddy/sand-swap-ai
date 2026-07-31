import type { ChangeEvent, DragEvent } from "react";
import { useEffect, useRef, useState } from "react";

import { documentsApi } from "../api/documents";
import { ChatWindow } from "../components/chat/ChatWindow";
import { MessageComposer } from "../components/chat/MessageComposer";
import { ExecutionTimeline } from "../components/execution/ExecutionTimeline";
import { useExecution } from "../hooks/useExecution";
import type {
    ExecutionTraceSummary,
    ProjectRecord,
    WorkspaceRecord,
} from "../types/api";
import type { ReturnTypeUseAuth } from "../types/auth";
import type { ChatMessage } from "../types/chat";

const GUEST_WELCOME_SESSION_KEY = "sand-swap-chat-guest-welcome-shown-v1";

interface ChatPageProps {
    auth: ReturnTypeUseAuth;
    workspaceScopeId: string;
    messages: ChatMessage[];
    isSending: boolean;
    error: string | null;
    availableModels: string[];
    selectedModel: string | null;
    onSelectModel: (model: string | null) => void;
    onSendMessage: (message: string) => Promise<void>;
}

export const ChatPage = ({
    auth,
    workspaceScopeId,
    messages,
    isSending,
    error,
    availableModels,
    selectedModel,
    onSelectModel,
    onSendMessage,
}: ChatPageProps) => {
    const [showGuestWelcome, setShowGuestWelcome] = useState(false);
    const [uploadSuccessMessage, setUploadSuccessMessage] = useState<string | null>(null);
    const [uploadError, setUploadError] = useState<string | null>(null);
    const [isUploading, setIsUploading] = useState(false);
    const [isDragOver, setIsDragOver] = useState(false);
    const fileInputRef = useRef<HTMLInputElement | null>(null);
    const {
        recent,
        selectedTrace,
        isLoadingRecent,
        isLoadingTrace,
        recentError,
        traceError,
        hasLoadedRecent,
        selectTrace,
        ensureFirstTraceLoaded,
        refreshAfterChatCompletion,
    } = useExecution();

    const [isTimelineExpanded, setIsTimelineExpanded] = useState(false);
    const [isPlanExpanded, setIsPlanExpanded] = useState(false);

    const activeWorkspaceName =
        auth.workspaces.find((workspace: WorkspaceRecord) => workspace.id === auth.activeWorkspaceId)?.name
        ?? "Workspace";
    const activeProjectName =
        auth.projects.find((project: ProjectRecord) => project.id === auth.activeProjectId)?.name
        ?? "Project";

    useEffect(() => {
        if (auth.isAuthenticated) {
            setShowGuestWelcome(false);
            return;
        }
        const shown = window.sessionStorage.getItem(GUEST_WELCOME_SESSION_KEY);
        if (!shown) {
            setShowGuestWelcome(true);
        }
    }, [auth.isAuthenticated]);

    useEffect(() => {
        setUploadSuccessMessage(null);
        setUploadError(null);
    }, [workspaceScopeId]);

    const dismissGuestWelcome = () => {
        window.sessionStorage.setItem(GUEST_WELCOME_SESSION_KEY, "1");
        setShowGuestWelcome(false);
    };

    const onSignInWithGoogle = async () => {
        await auth.signInWithGooglePopup();
        dismissGuestWelcome();
    };

    const uploadFile = async (file: File) => {
        setIsUploading(true);
        setUploadError(null);
        setUploadSuccessMessage(null);
        try {
            await documentsApi.upload({ file });
            setUploadSuccessMessage(
                "Document indexed successfully. You can now ask questions about it."
            );
        } catch (err) {
            setUploadError(err instanceof Error ? err.message : "Upload failed.");
        } finally {
            setIsUploading(false);
        }
    };

    const onPickFile = async (event: ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) {
            return;
        }
        await uploadFile(file);
        event.target.value = "";
    };

    const onDropFile = async (event: DragEvent<HTMLDivElement>) => {
        event.preventDefault();
        setIsDragOver(false);
        const file = event.dataTransfer.files?.[0];
        if (!file) {
            return;
        }
        await uploadFile(file);
    };

    const handleSendMessage = async (message: string) => {
        await onSendMessage(message);
        await refreshAfterChatCompletion();
    };

    const handleTimelineToggle = async () => {
        const nextExpanded = !isTimelineExpanded;
        setIsTimelineExpanded(nextExpanded);
        if (nextExpanded) {
            await ensureFirstTraceLoaded();
        }
    };

    const handlePlanToggle = async () => {
        const nextExpanded = !isPlanExpanded;
        setIsPlanExpanded(nextExpanded);
        if (nextExpanded) {
            await ensureFirstTraceLoaded();
        }
    };

    const handleSelectTrace = async (trace: ExecutionTraceSummary) => {
        await selectTrace(trace.trace_id);
    };

    return (
        <div
            className={`chat-page ${isDragOver ? "chat-page--drag-over" : ""}`}
            onDragOver={(event) => {
                event.preventDefault();
                setIsDragOver(true);
            }}
            onDragLeave={() => setIsDragOver(false)}
            onDrop={(event) => {
                void onDropFile(event);
            }}
        >
            {showGuestWelcome ? (
                <div className="chat-welcome-modal-backdrop" role="presentation">
                    <section className="chat-welcome-modal" role="dialog" aria-modal="true" aria-label="Welcome to SandSwap AI">
                        <h2>Welcome to SandSwap AI</h2>
                        <p>Choose how you want to start chatting.</p>
                        <div className="chat-welcome-grid">
                            <article className="chat-welcome-card">
                                <h3>Continue as Guest</h3>
                                <ul>
                                    <li>Temporary chat</li>
                                    <li>Temporary memory</li>
                                    <li>Temporary documents</li>
                                </ul>
                            </article>
                            <article className="chat-welcome-card">
                                <h3>Sign in with Google</h3>
                                <ul>
                                    <li>Persistent chat history</li>
                                    <li>Long-term memory</li>
                                    <li>Multiple Workspaces</li>
                                    <li>Multiple Projects</li>
                                    <li>Private document library</li>
                                    <li>Future AI agents</li>
                                </ul>
                            </article>
                        </div>
                        <div className="chat-welcome-actions">
                            <button type="button" className="memory-button" onClick={dismissGuestWelcome}>
                                Continue as Guest
                            </button>
                            <button type="button" className="google-signin-button" onClick={() => void onSignInWithGoogle()}>
                                Sign in with Google
                            </button>
                        </div>
                    </section>
                </div>
            ) : null}

            <section className="chat-controls" aria-label="Chat controls">
                <div className="chat-controls-row">
                    <div className="chat-controls-left">
                        {auth.isAuthenticated ? (
                            <>
                                <label className="chat-control">
                                    <span>Workspace</span>
                                    <select
                                        className="workspace-select"
                                        value={auth.activeWorkspaceId ?? ""}
                                        disabled={auth.isWorkspaceLoading || auth.workspaces.length === 0}
                                        onChange={(event) => {
                                            void auth.switchWorkspace(event.target.value);
                                        }}
                                    >
                                        {auth.workspaces.map((workspace) => (
                                            <option key={workspace.id} value={workspace.id}>
                                                {workspace.name}
                                            </option>
                                        ))}
                                    </select>
                                    <div className="chat-entity-actions">
                                        <button
                                            type="button"
                                            className="memory-button"
                                            onClick={() => {
                                                const name = window.prompt("New workspace name");
                                                if (!name || !name.trim()) {
                                                    return;
                                                }
                                                void auth.createWorkspace(name.trim());
                                            }}
                                        >
                                            New
                                        </button>
                                        <button
                                            type="button"
                                            className="memory-button"
                                            disabled={!auth.activeWorkspaceId}
                                            onClick={() => {
                                                if (!auth.activeWorkspaceId) {
                                                    return;
                                                }
                                                const name = window.prompt("Rename workspace", activeWorkspaceName);
                                                if (!name || !name.trim()) {
                                                    return;
                                                }
                                                void auth.renameWorkspace(auth.activeWorkspaceId, name.trim());
                                            }}
                                        >
                                            Rename
                                        </button>
                                        <button
                                            type="button"
                                            className="memory-button memory-button--danger"
                                            disabled={!auth.activeWorkspaceId || auth.workspaces.length <= 1}
                                            onClick={() => {
                                                if (!auth.activeWorkspaceId) {
                                                    return;
                                                }
                                                const confirmed = window.confirm(
                                                    `Delete workspace "${activeWorkspaceName}"?`
                                                );
                                                if (!confirmed) {
                                                    return;
                                                }
                                                void auth.deleteWorkspace(auth.activeWorkspaceId);
                                            }}
                                        >
                                            Delete
                                        </button>
                                    </div>
                                </label>
                                <label className="chat-control">
                                    <span>Project</span>
                                    <select
                                        className="workspace-select"
                                        value={auth.activeProjectId ?? ""}
                                        disabled={auth.isProjectLoading || auth.projects.length === 0}
                                        onChange={(event) => {
                                            void auth.switchProject(event.target.value);
                                        }}
                                    >
                                        {auth.projects.map((project) => (
                                            <option key={project.id} value={project.id}>
                                                {project.name}
                                            </option>
                                        ))}
                                    </select>
                                    <div className="chat-entity-actions">
                                        <button
                                            type="button"
                                            className="memory-button"
                                            onClick={() => {
                                                const name = window.prompt("New project name");
                                                if (!name || !name.trim()) {
                                                    return;
                                                }
                                                void auth.createProject(name.trim());
                                            }}
                                        >
                                            New
                                        </button>
                                        <button
                                            type="button"
                                            className="memory-button"
                                            disabled={!auth.activeProjectId}
                                            onClick={() => {
                                                if (!auth.activeProjectId) {
                                                    return;
                                                }
                                                const name = window.prompt("Rename project", activeProjectName);
                                                if (!name || !name.trim()) {
                                                    return;
                                                }
                                                void auth.renameProject(auth.activeProjectId, name.trim());
                                            }}
                                        >
                                            Rename
                                        </button>
                                        <button
                                            type="button"
                                            className="memory-button memory-button--danger"
                                            disabled={!auth.activeProjectId || auth.projects.length <= 1}
                                            onClick={() => {
                                                if (!auth.activeProjectId) {
                                                    return;
                                                }
                                                const confirmed = window.confirm(
                                                    `Delete project "${activeProjectName}"?`
                                                );
                                                if (!confirmed) {
                                                    return;
                                                }
                                                void auth.deleteProject(auth.activeProjectId);
                                            }}
                                        >
                                            Delete
                                        </button>
                                    </div>
                                </label>
                            </>
                        ) : null}
                    </div>
                    <div className="chat-controls-right">
                        <label className="chat-control chat-control-model">
                            <span>Model</span>
                            <select
                                className="workspace-select"
                                value={selectedModel ?? ""}
                                disabled={availableModels.length === 0}
                                onChange={(event) => {
                                    onSelectModel(event.target.value || null);
                                }}
                            >
                                {availableModels.map((model) => (
                                    <option key={model} value={model}>
                                        {model}
                                    </option>
                                ))}
                            </select>
                        </label>
                    </div>
                </div>
                <div className="chat-controls-row chat-controls-row--meta">
                    {auth.isAuthenticated ? (
                        <span className="workspace-active-chip" title={workspaceScopeId}>
                            {activeWorkspaceName} / {activeProjectName}
                        </span>
                    ) : (
                        <button
                            type="button"
                            className="google-signin-button"
                            onClick={() => void auth.signInWithGooglePopup()}
                        >
                            Sign in with Google
                        </button>
                    )}
                </div>
            </section>

            {error ? (
                <p className="error-banner" role="alert">
                    <span className="error-icon" aria-hidden="true">!</span>
                    {error}
                </p>
            ) : null}
            {uploadError ? (
                <p className="error-banner" role="alert">
                    <span className="error-icon" aria-hidden="true">!</span>
                    {uploadError}
                </p>
            ) : null}
            {uploadSuccessMessage ? (
                <p className="memory-status">{uploadSuccessMessage}</p>
            ) : null}

            <ExecutionTimeline
                recent={recent}
                selectedTrace={selectedTrace}
                isLoadingRecent={isLoadingRecent}
                isLoadingTrace={isLoadingTrace}
                recentError={recentError}
                traceError={traceError}
                hasLoadedRecent={hasLoadedRecent}
                isTimelineExpanded={isTimelineExpanded}
                onTimelineToggle={() => {
                    void handleTimelineToggle();
                }}
                isPlanExpanded={isPlanExpanded}
                onPlanToggle={() => {
                    void handlePlanToggle();
                }}
                onSelectTrace={(trace) => {
                    void handleSelectTrace(trace);
                }}
            />

            <ChatWindow messages={messages} isSending={isSending} />
            <MessageComposer
                isSending={isSending || isUploading}
                onSendMessage={handleSendMessage}
                onUploadClick={() => fileInputRef.current?.click()}
                isUploading={isUploading}
            />
            <input
                ref={fileInputRef}
                type="file"
                className="chat-upload-input"
                onChange={(event) => {
                    void onPickFile(event);
                }}
                disabled={isUploading}
                aria-label="Upload document from chat"
            />
        </div>
    );
};
