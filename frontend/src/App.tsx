import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "./components/layout/AppLayout";
import { AgentStudioPage } from "./pages/AgentStudioPage";
import { ChatPage } from "./pages/ChatPage";
import { DocumentsPage } from "./pages/DocumentsPage";
import { KnowledgeSourcesPage } from "./pages/KnowledgeSourcesPage";
import { MemoryPage } from "./pages/MemoryPage";
import { RetrievalInspectorPage } from "./pages/RetrievalInspectorPage";
import { UploadsPage } from "./pages/UploadsPage";
import { useAuth } from "./state/useAuth";
import { useChat } from "./state/useChat";
import { useHealth } from "./state/useHealth";

const App = () => {
    const auth = useAuth();
    const { health, isLoading: healthLoading, error: healthError } = useHealth();
    const effectiveUserId = auth.effectiveUserId;
    const workspaceScopeId = `${effectiveUserId}:${auth.activeWorkspaceId ?? "default"}:${auth.activeProjectId ?? "default"}`;
    const {
        availableModels,
        selectedModel,
        setSelectedModel,
        conversations,
        activeConversation,
        activeConversationId,
        setActiveConversationId,
        isSending,
        error,
        sendMessage,
        startNewConversation,
        renameConversation,
        deleteConversation,
    } = useChat(effectiveUserId, workspaceScopeId);

    return (
        <Routes>
            <Route
                path="/"
                element={
                    <AppLayout
                        auth={auth}
                        health={health}
                        healthLoading={healthLoading}
                        healthError={healthError}
                        conversations={conversations}
                        activeConversationId={activeConversationId}
                        onSelectConversation={setActiveConversationId}
                        onNewConversation={startNewConversation}
                        onRenameConversation={renameConversation}
                        onDeleteConversation={deleteConversation}
                    />
                }
            >
                <Route index element={<Navigate to="chat" replace />} />
                <Route
                    path="chat"
                    element={
                        <ChatPage
                            auth={auth}
                            workspaceScopeId={workspaceScopeId}
                            messages={activeConversation?.messages ?? []}
                            isSending={isSending}
                            error={error}
                            availableModels={availableModels}
                            selectedModel={selectedModel}
                            onSelectModel={setSelectedModel}
                            onSendMessage={sendMessage}
                        />
                    }
                />
                <Route path="agent-studio">
                    <Route index element={<AgentStudioPage auth={auth} />} />
                    <Route path=":agentId" element={<AgentStudioPage auth={auth} />} />
                </Route>
                <Route path="memory" element={<MemoryPage ownerId={workspaceScopeId} />} />
                <Route path="documents" element={<DocumentsPage ownerId={workspaceScopeId} />} />
                <Route path="uploads" element={<UploadsPage projectId={auth.activeProjectId ?? "default"} />} />
                <Route
                    path="knowledge-sources"
                    element={<KnowledgeSourcesPage projectId={auth.activeProjectId ?? "default"} />}
                />
                <Route path="inspector" element={<RetrievalInspectorPage ownerId={workspaceScopeId} />} />
            </Route>
            <Route path="*" element={<Navigate to="/chat" replace />} />
        </Routes>
    );
};

export default App;
