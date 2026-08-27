import { useState, useEffect, useRef } from 'react';
import { useAuthStore } from '../store/authStore';
import { useChatStore } from '../store/chatStore';
import MessageItem from './MessageItem';
import React from 'react';

export default function ChatPage() {
  const { logout, username } = useAuthStore();
  const {
    sessions,
    activeSessionId,
    isLoading,
    createSession,
    setActiveSession,
    sendMessage,
    deleteSession,
    getActiveSession,
  } = useChatStore();

  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const activeSession = getActiveSession();

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeSession?.messages]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || isLoading) return;
    setInput('');
    await sendMessage(text);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div style={styles.container}>
      {/* 侧边栏 */}
      <div style={styles.sidebar}>
        <div style={styles.sidebarHeader}>
          <span style={styles.logo}>Air Fryer AI</span>
          <span style={styles.username}>{username}</span>
        </div>

        <button style={styles.newChatBtn} onClick={createSession}>
          + 新对话
        </button>

        <div style={styles.sessionList}>
          {sessions.map((session) => (
            <div
              key={session.id}
              style={{
                ...styles.sessionItem,
                backgroundColor: session.id === activeSessionId ? '#f0eeff' : 'transparent',
              }}
              onClick={() => setActiveSession(session.id)}
            >
              <span style={styles.sessionTitle}>{session.title}</span>
              <button
                style={styles.deleteBtn}
                onClick={(e) => { e.stopPropagation(); deleteSession(session.id); }}
                title="删除"
              >
                x
              </button>
            </div>
          ))}
        </div>

        <button style={styles.logoutBtn} onClick={logout}>退出登录</button>
      </div>

      {/* 主聊天区域 */}
      <div style={styles.main}>
        {/* 消息列表 */}
        <div style={styles.messageArea}>
          {!activeSession || activeSession.messages.length === 0 ? (
            <div style={styles.emptyState}>
              <h2>欢迎使用 Air Fryer AI 助手</h2>
              <p>你可以问我关于空气炸锅的任何问题</p>
              <div style={styles.quickQuestions}>
                {['空气炸锅怎么清洗？', '有哪些功能？', '不加热怎么办？'].map((q) => (
                  <button key={q} style={styles.quickBtn} onClick={() => setInput(q)}>
                    {q}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            activeSession.messages.map((msg) => <MessageItem key={msg.id} message={msg} />)
          )}
          {isLoading && (
            <div style={styles.loading}>
              <div style={styles.typingDot} />
              <div style={{ ...styles.typingDot, animationDelay: '0.2s' }} />
              <div style={{ ...styles.typingDot, animationDelay: '0.4s' }} />
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* 输入区域 */}
        <div style={styles.inputArea}>
          <textarea
            style={styles.textarea}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入你的问题... (Enter 发送, Shift+Enter 换行)"
            rows={2}
            disabled={isLoading}
          />
          <button
            style={{ ...styles.sendBtn, opacity: input.trim() && !isLoading ? 1 : 0.5 }}
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
          >
            发送
          </button>
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { display: 'flex', height: '100vh', fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif' },
  sidebar: {
    width: 260, backgroundColor: '#fafafa', borderRight: '1px solid #e8e8e8',
    display: 'flex', flexDirection: 'column', padding: '16px 12px',
  },
  sidebarHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  logo: { fontWeight: 700, fontSize: 16, color: '#4B3FE3' },
  username: { fontSize: 13, color: '#888' },
  newChatBtn: {
    width: '100%', padding: '10px', borderRadius: 8, border: '1px dashed #ccc',
    background: 'transparent', color: '#4B3FE3', fontWeight: 600, cursor: 'pointer',
    fontSize: 14, marginBottom: 12,
  },
  sessionList: { flex: 1, overflowY: 'auto' },
  sessionItem: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '8px 10px', borderRadius: 6, cursor: 'pointer', marginBottom: 2,
  },
  sessionTitle: { fontSize: 13, color: '#333', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
  deleteBtn: { background: 'none', border: 'none', color: '#aaa', cursor: 'pointer', fontSize: 14, padding: '0 4px' },
  logoutBtn: {
    marginTop: 12, padding: '8px', borderRadius: 6, border: '1px solid #e0e0e0',
    background: '#fff', color: '#666', cursor: 'pointer', fontSize: 13,
  },
  main: { flex: 1, display: 'flex', flexDirection: 'column', backgroundColor: '#f9f9f9' },
  messageArea: { flex: 1, overflowY: 'auto', padding: '20px 16%' },
  emptyState: {
    display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
    height: '100%', color: '#888', textAlign: 'center',
  },
  quickQuestions: { display: 'flex', gap: 8, marginTop: 20, flexWrap: 'wrap', justifyContent: 'center' },
  quickBtn: {
    padding: '8px 16px', borderRadius: 20, border: '1px solid #e0e0e0',
    background: '#fff', color: '#4B3FE3', cursor: 'pointer', fontSize: 13,
  },
  loading: { display: 'flex', gap: 4, padding: '10px 14px' },
  typingDot: {
    width: 8, height: 8, borderRadius: '50%', backgroundColor: '#999',
    animation: 'typing 1s infinite',
  },
  inputArea: {
    padding: '12px 16%', borderTop: '1px solid #e8e8e8', backgroundColor: '#fff',
    display: 'flex', gap: 10, alignItems: 'flex-end',
  },
  textarea: {
    flex: 1, padding: '10px 14px', borderRadius: 10, border: '1px solid #ddd',
    fontSize: 14, resize: 'none', outline: 'none', fontFamily: 'inherit',
    lineHeight: 1.5,
  },
  sendBtn: {
    padding: '10px 24px', borderRadius: 10, border: 'none',
    backgroundColor: '#4B3FE3', color: '#fff', fontWeight: 600,
    cursor: 'pointer', fontSize: 14, whiteSpace: 'nowrap',
  },
};
