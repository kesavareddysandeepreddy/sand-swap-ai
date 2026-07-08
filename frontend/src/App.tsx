import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "./components/layout/AppLayout";
import { ChatPage } from "./pages/ChatPage";
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
      </Route>
    </Routes>
  );
};

export default App;
