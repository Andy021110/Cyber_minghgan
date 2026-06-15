import { useState, useEffect, useRef } from 'react';
import { dispatch } from '../../eventbus';
import { useAuth } from '../../contexts/AuthContext';
import { chatStream } from '../../api/client';
import './DialoguePanel.css';

interface Message {
  id:           string;
  role:         'user' | 'npc';
  text:         string;
  timestamp:    string;
  isReflection: boolean;
}

export interface DialoguePanelProps {
  npcId:   string;
  npcName: string;
  onClose: () => void;
}

export function DialoguePanel({ npcId, npcName, onClose }: DialoguePanelProps) {
  const { privateKey } = useAuth();
  const [messages,  setMessages]  = useState<Message[]>([]);
  const [streaming, setStreaming]  = useState('');
  const [input,     setInput]     = useState('');
  const [expanded,  setExpanded]  = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [lastReflection, setLastReflection] = useState(false);
  const cancelRef  = useRef<(() => void) | null>(null);
  const historyRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    dispatch('cyber:panel:opened', { panelId: 'dialogue' });
    return () => {
      cancelRef.current?.();
      dispatch('cyber:panel:closed', { panelId: 'dialogue' });
    };
  }, []);

  useEffect(() => {
    if (historyRef.current) {
      historyRef.current.scrollTop = historyRef.current.scrollHeight;
    }
  }, [messages, streaming]);

  const sendMessage = () => {
    const text = input.trim();
    if (!text || isSending) return;
    setInput('');
    setIsSending(true);
    setStreaming('');
    setLastReflection(false);

    const userMsg: Message = {
      id:           Date.now().toString(),
      role:         'user',
      text,
      timestamp:    new Date().toLocaleTimeString('zh', { hour: '2-digit', minute: '2-digit' }),
      isReflection: false,
    };
    setMessages(prev => [...prev, userMsg]);

    cancelRef.current = chatStream(
      npcId, text, privateKey,
      (token)    => setStreaming(prev => prev + token),
      (fullText) => {
        setStreaming('');
        setIsSending(false);
        setMessages(prev => [...prev, {
          id:           Date.now().toString(),
          role:         'npc',
          text:         fullText,
          timestamp:    new Date().toLocaleTimeString('zh', { hour: '2-digit', minute: '2-digit' }),
          isReflection: lastReflection,
        }]);
      },
      (triggered) => setLastReflection(triggered),
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  const latestNpcMsg = [...messages].reverse().find(m => m.role === 'npc');

  return (
    <div className={`dialogue-panel${expanded ? ' dialogue-panel--expanded' : ''}`}>
      {expanded && (
        <div className="dialogue-history" ref={historyRef} data-testid="dialogue-history">
          {messages.map(msg => (
            <div
              key={msg.id}
              className={`dialogue-msg dialogue-msg--${msg.role}${msg.isReflection ? ' dialogue-msg--reflection' : ''}`}
            >
              <div className="dialogue-msg-text">
                {msg.isReflection && <span className="dialogue-reflection-badge">💡 </span>}
                {msg.text}
              </div>
              <div className="dialogue-msg-time">{msg.timestamp}</div>
            </div>
          ))}
        </div>
      )}

      <div className="dialogue-bar">
        <div className="dialogue-bar-left">
          <div className="dialogue-npc-sprite">👤</div>
          <div className="dialogue-npc-name">{npcName}</div>
        </div>

        <div className="dialogue-bar-main">
          <div className="dialogue-current">
            {isSending ? (
              <>
                <span data-testid="dialogue-streaming">{streaming}</span>
                <span className="dialogue-cursor">▌</span>
              </>
            ) : latestNpcMsg ? (
              <span className={latestNpcMsg.isReflection ? 'dialogue-reflection-msg' : ''}>
                {latestNpcMsg.isReflection && <span className="dialogue-reflection-badge">💡 </span>}
                {latestNpcMsg.text}
              </span>
            ) : (
              <span className="dialogue-placeholder">按 Enter 发送消息…</span>
            )}
          </div>

          <div className="dialogue-input-row">
            <input
              className="dialogue-input"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入消息…"
              disabled={isSending}
              data-testid="dialogue-input"
            />
            <button
              className="btn-pixel dialogue-send"
              onClick={sendMessage}
              disabled={isSending || !input.trim()}
              data-testid="dialogue-send"
            >
              发送
            </button>
          </div>
        </div>

        <div className="dialogue-bar-right">
          <button
            className="btn-pixel dialogue-expand-btn"
            onClick={() => setExpanded(e => !e)}
            data-testid="dialogue-expand-btn"
          >
            {expanded ? '↓ 收起' : '↑ 历史'}
          </button>
          <button
            className="btn-pixel dialogue-close"
            onClick={onClose}
            data-testid="dialogue-close"
          >
            ×
          </button>
        </div>
      </div>
    </div>
  );
}
