/** User message bubble. */
interface UserMessageProps {
  text: string;
}

export default function UserMessage({ text }: UserMessageProps) {
  return (
    <div className="msg msg-user">
      <div className="msg-avatar">👤</div>
      <div className="msg-bubble">{text}</div>
    </div>
  );
}