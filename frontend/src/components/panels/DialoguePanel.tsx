import { useState, useEffect, useRef, useCallback } from 'react';
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
  npcId:         string;
  npcName:       string;
  onClose:       () => void;
  initialQuery?: string;
}

export function DialoguePanel({ npcId, npcName, onClose, initialQuery }: DialoguePanelProps) {
  const { privateKey } = useAuth();
  const [messages,  setMessages]  = useState<Message[]>([]);
  const [streaming, setStreaming]  = useState('');
  const [input,     setInput]     = useState('');
  const [expanded,  setExpanded]  = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [toolStatus, setToolStatus] = useState('');
  // 后端故障必须可见：原先 chatStream 静默吞错，界面表现为"什么都不发生"
  const [error, setError] = useState('');
  const lastReflectionRef = useRef(false);
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

  const sendText = useCallback((text: string) => {
    if (!text.trim() || isSending) return;
    setInput('');
    setIsSending(true);
    setError('');
    setStreaming('');
    setToolStatus('思考中…');
    lastReflectionRef.current = false;

    const userMsg: Message = {
      id:           Date.now().toString(),
      role:         'user',
      text:         text.trim(),
      timestamp:    new Date().toLocaleTimeString('zh', { hour: '2-digit', minute: '2-digit' }),
      isReflection: false,
    };
    setMessages(prev => [...prev, userMsg]);

    cancelRef.current = chatStream(
      npcId, text.trim(), privateKey,
      (token)     => { setStreaming(prev => prev + token); },
      (fullText)  => {
        setStreaming('');
        setToolStatus('');
        setIsSending(false);
        setMessages(prev => [...prev, {
          id:           Date.now().toString(),
          role:         'npc',
          text:         fullText,
          timestamp:    new Date().toLocaleTimeString('zh', { hour: '2-digit', minute: '2-digit' }),
          isReflection: lastReflectionRef.current,
        }]);
      },
      (triggered, feature) => {
        lastReflectionRef.current = triggered;
        if (triggered) {
          dispatch('cyber:reflection:triggered', {});
        }
        if (feature) {
          setMessages(prev => [...prev, {
            id:           Date.now().toString() + '_reflect',
            role:         'npc',
            text:         feature,
            timestamp:    new Date().toLocaleTimeString('zh', { hour: '2-digit', minute: '2-digit' }),
            isReflection: true,
          }]);
        }
      },
      (label)     => { setToolStatus(label); },
      (nodeId, label) => { dispatch('cyber:kg:updated', { nodeId, label }); },
      (msg)      => {
        setError(msg);
        setStreaming('');
        setToolStatus('');
        setIsSending(false);
      },
    );
  }, [npcId, privateKey, isSending]);

  const sendMessage = () => {
    const text = input.trim();
    if (!text) return;
    setInput('');
    sendText(text);
  };

  useEffect(() => {
    if (initialQuery) {
      sendText(initialQuery);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
          {error && (
            <div className="dialogue-error" data-testid="dialogue-error" role="alert">
              错误：{error}
            </div>
          )}
          <div className="dialogue-current">
            {isSending ? (
              <>
                {toolStatus && (
                  <div className="dialogue-tool-status" data-testid="dialogue-tool-status">
                    {toolStatus}
                  </div>
                )}
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
