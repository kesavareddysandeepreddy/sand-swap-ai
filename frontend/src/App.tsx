import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "./components/layout/AppLayout";
import { ChatPage } from "./pages/ChatPage";
import { DocumentsPage } from "./pages/DocumentsPage";
import { MemoryPage } from "./pages/MemoryPage";
import { RetrievalInspectorPage } from "./pages/RetrievalInspectorPage";
import { useAuth } from "./state/useAuth";
import { useChat } from "./state/useChat";
import { useHealth } from "./state/useHealth";

const App = () => {
    const auth = useAuth();
    const { health, isLoading: healthLoading, error: healthError } = useHealth();
    const effectiveUserId = auth.effectiveUserId;
    const workspaceScopeId = `${effectiveUserId}:${auth.activeWorkspaceId ?? "default"}:${auth.activeProjectId ?? "default"}`;
    const {
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
                        workspaceScopeId={workspaceScopeId}
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
                            messages={activeConversation?.messages ?? []}
                            isSending={isSending}
                            error={error}
                            onSendMessage={sendMessage}
                        />
                    }
                />
                <Route path="memory" element={<MemoryPage ownerId={workspaceScopeId} />} />
                <Route path="documents" element={<DocumentsPage ownerId={workspaceScopeId} />} />
                <Route path="inspector" element={<RetrievalInspectorPage ownerId={workspaceScopeId} />} />
            </Route>
            <Route path="*" element={<Navigate to="/chat" replace />} />
        </Routes>
    );
};

export default App;
