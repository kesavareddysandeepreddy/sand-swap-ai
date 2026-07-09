import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "./components/layout/AppLayout";
import { ChatPage } from "./pages/ChatPage";
import { MemoryPage } from "./pages/MemoryPage";
import { useChat } from "./state/useChat";
import { useHealth } from "./state/useHealth";

const App = () => {
    const { health, isLoading: healthLoading, error: healthError } = useHealth();
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
    } = useChat();

    return (
        <Routes>
            <Route
                path="/"
                element={
                    <AppLayout
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
                            messages={activeConversation?.messages ?? []}
                            isSending={isSending}
                            error={error}
                            onSendMessage={sendMessage}
                        />
                    }
                />
                <Route path="memory" element={<MemoryPage />} />
            </Route>
        </Routes>
    );
};

export default App;
