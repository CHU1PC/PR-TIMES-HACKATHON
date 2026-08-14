import type { ChatMessage } from "@/lib/session";

interface ChatLogProps {
  messages: ChatMessage[];
}

export function ChatLog({ messages }: ChatLogProps) {
  if (messages.length === 0) return null;
  return (
    <ol className="chat">
      {messages.map((message, index) => (
        <li key={`${String(index)}-${message.role}`} className={`chat__turn chat__turn--${message.role}`}>
          <span className="chat__who">{message.role === "ai" ? "質問" : "あなた"}</span>
          <p className="chat__text">{message.text}</p>
        </li>
      ))}
    </ol>
  );
}
