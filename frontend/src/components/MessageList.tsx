/** MessageList — scrollable message container with auto-scroll. */
import { useRef, useEffect } from "react";
import UserMessage from "./UserMessage";
import AgentMessage from "./AgentMessage";

export interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  sections?: Record<string, unknown>;
  plan?: Record<string, unknown>[];
}

interface MessageListProps {
  messages: ChatMessage[];
  loading: boolean;
}

export default function MessageList({ messages, loading }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  return (
    <div className="message-list">
      {messages.length === 0 && !loading && (
        <div className="message-list-empty">
          <div className="empty-icon">💬</div>
          <h3>电商多智能体分析系统</h3>
          <p>
            输入您的电商分析需求，系统将通过多个智能体协作完成选品分析、
            趋势预测、竞品对比、营销文案生成、库存补货建议、定价策略和促销方案策划。
          </p>
          <div className="empty-hints">
            <div className="hint-item">🔍 帮我分析电子产品类目的选品机会</div>
            <div className="hint-item">📈 预测未来30天这款背包的销量趋势</div>
            <div className="hint-item">💰 女装类目的定价策略应该怎么定</div>
            <div className="hint-item">📦 库存不够了，给个补货建议</div>
          </div>
        </div>
      )}

      {messages.map((msg, i) =>
        msg.role === "user" ? (
          <UserMessage key={i} text={msg.text} />
        ) : (
          <AgentMessage
            key={i}
            reply={msg.text}
            sections={msg.sections}
            plan={msg.plan}
          />
        ),
      )}

      {loading && (
        <div className="msg msg-agent">
          <div className="msg-avatar">🤖</div>
          <div className="msg-bubble msg-bubble-agent">
            <div className="msg-loading">
              <span className="loading-dot" />
              <span className="loading-dot" />
              <span className="loading-dot" />
              <span className="loading-text">多个智能体正在协作分析中…</span>
            </div>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}