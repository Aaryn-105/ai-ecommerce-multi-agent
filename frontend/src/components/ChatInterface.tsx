/** ChatInterface — main chat container with state management and API orchestration. */
import { useState, useCallback } from "react";
import MessageList from "./MessageList";
import InputBar from "./InputBar";
import { sendMessage } from "../api";
import type { ChatMessage } from "./MessageList";

export default function ChatInterface() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);

  const handleSend = useCallback(
    async (text: string) => {
      // Add user message
      const userMsg: ChatMessage = { role: "user", text };
      setMessages((prev) => [...prev, userMsg]);
      setLoading(true);

      try {
        const resp = await sendMessage(text, conversationId);

        // Update conversation ID from response
        if (resp.conversation_id) {
          setConversationId(resp.conversation_id);
        }

        // Add assistant message
        const assistantMsg: ChatMessage = {
          role: "assistant",
          text: resp.reply,
          sections: resp.sections ?? undefined,
          plan: resp.plan ?? undefined,
        };
        setMessages((prev) => [...prev, assistantMsg]);
      } catch (err) {
        const errorMsg: ChatMessage = {
          role: "assistant",
          text: "❌ 请求失败，请检查后端服务是否正常运行（http://localhost:8000）",
        };
        setMessages((prev) => [...prev, errorMsg]);
        console.error("Chat API error:", err);
      } finally {
        setLoading(false);
      }
    },
    [conversationId],
  );

  const handleNewChat = useCallback(() => {
    setMessages([]);
    setConversationId(null);
  }, []);

  return (
    <div className="chat-interface">
      <div className="chat-header">
        <h2>对话分析</h2>
        <button className="chat-header-btn" onClick={handleNewChat} disabled={loading}>
          新对话
        </button>
      </div>
      <MessageList messages={messages} loading={loading} />
      <InputBar onSend={handleSend} disabled={loading} />
    </div>
  );
}