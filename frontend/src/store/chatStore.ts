import { create } from 'zustand';
import { sendMessage, type ChatResponse } from '../api/chat';

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  intent?: string;
  needHuman?: boolean;
}

export interface Session {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
}

interface ChatState {
  sessions: Session[];
  activeSessionId: string | null;
  isLoading: boolean;

  createSession: () => void;
  setActiveSession: (id: string) => void;
  sendMessage: (content: string) => Promise<void>;
  deleteSession: (id: string) => void;

  getActiveSession: () => Session | undefined;
}

export const useChatStore = create<ChatState>((set, get) => ({
  sessions: [],
  activeSessionId: null,
  isLoading: false,

  createSession: () => {
    const newSession: Session = {
      id: crypto.randomUUID(),
      title: '新对话',
      messages: [],
      createdAt: Date.now(),
    };
    set((state) => ({
      sessions: [newSession, ...state.sessions],
      activeSessionId: newSession.id,
    }));
  },

  setActiveSession: (id) => {
    set({ activeSessionId: id });
  },

  sendMessage: async (content: string) => {
    const state = get();

    // 如果没有活跃会话，自动创建一个
    let sessionId = state.activeSessionId;
    if (!sessionId) {
      const newSession: Session = {
        id: crypto.randomUUID(),
        title: content.slice(0, 20) || '新对话',
        messages: [],
        createdAt: Date.now(),
      };
      sessionId = newSession.id;
      set((s) => ({
        sessions: [newSession, ...s.sessions],
        activeSessionId: sessionId,
      }));
    }

    // 添加用户消息
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      timestamp: Date.now(),
    };

    set((s) => ({
      sessions: s.sessions.map((session) =>
        session.id === sessionId
          ? {
              ...session,
              messages: [...session.messages, userMessage],
              title: session.messages.length === 0 ? content.slice(0, 20) || '新对话' : session.title,
            }
          : session
      ),
      isLoading: true,
    }));

    try {
      const res: ChatResponse = await sendMessage({
        message: content,
        session_id: sessionId,
      });

      const assistantMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: res.answer,
        timestamp: Date.now(),
        intent: res.intent,
        needHuman: res.need_human,
      };

      set((s) => ({
        sessions: s.sessions.map((session) =>
          session.id === sessionId
            ? { ...session, messages: [...session.messages, assistantMessage] }
            : session
        ),
        isLoading: false,
      }));
    } catch (error) {
      const errorMessage: Message = {
        id: crypto.randomUUID(),
        role: 'system',
        content: '抱歉，请求出错，请稍后重试。',
        timestamp: Date.now(),
      };

      set((s) => ({
        sessions: s.sessions.map((session) =>
          session.id === sessionId
            ? { ...session, messages: [...session.messages, errorMessage] }
            : session
        ),
        isLoading: false,
      }));
    }
  },

  deleteSession: (id) => {
    set((state) => {
      const filtered = state.sessions.filter((s) => s.id !== id);
      return {
        sessions: filtered,
        activeSessionId: state.activeSessionId === id ? (filtered[0]?.id ?? null) : state.activeSessionId,
      };
    });
  },

  getActiveSession: () => {
    const state = get();
    return state.sessions.find((s) => s.id === state.activeSessionId);
  },
}));