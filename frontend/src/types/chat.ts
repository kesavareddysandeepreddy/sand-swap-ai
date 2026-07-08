export type MessageRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  createdAt: string;
}

export interface ConversationState {
  id: string;
  title: string;
  messages: ChatMessage[];
  updatedAt: string;
}
