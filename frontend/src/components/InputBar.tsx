/** Input bar — text input + send button. */
import { useState, useCallback, useRef, useEffect } from "react";

interface InputBarProps {
  onSend: (message: string) => void;
  disabled: boolean;
  placeholder?: string;
}

export default function InputBar({ onSend, disabled, placeholder }: InputBarProps) {
  const [text, setText] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
  }, [text, disabled, onSend]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  // Auto-resize textarea
  useEffect(() => {
    const el = inputRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 120) + "px";
    }
  }, [text]);

  return (
    <div className="input-bar">
      <textarea
        ref={inputRef}
        className="input-bar-textarea"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder ?? "请输入您的电商分析需求，例如：帮我分析电子产品类目的选品机会"}
        disabled={disabled}
        rows={1}
      />
      <button
        className="input-bar-btn"
        onClick={handleSend}
        disabled={disabled || !text.trim()}
      >
        {disabled ? "分析中…" : "发送"}
      </button>
    </div>
  );
}