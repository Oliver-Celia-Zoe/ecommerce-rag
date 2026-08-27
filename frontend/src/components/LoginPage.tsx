import { useState } from 'react';
import { useAuthStore } from '../store/authStore';

export default function LoginPage() {
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const { login, register } = useAuthStore();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (isRegister) {
        await register({ username, password });
      } else {
        await login({ username, password });
      }
      localStorage.setItem('username', username);
    } catch (err: any) {
      setError(err.response?.data?.error?.message || '操作失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <h1 style={styles.title}>Air Fryer AI Assistant</h1>
        <p style={styles.subtitle}>智能空气炸锅客服系统</p>

        <form onSubmit={handleSubmit} style={styles.form}>
          <input
            style={styles.input}
            type="text"
            placeholder="用户名"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            minLength={3}
            required
          />
          <input
            style={styles.input}
            type="password"
            placeholder="密码"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={6}
            required
          />
          {error && <div style={styles.error}>{error}</div>}
          <button style={styles.button} type="submit" disabled={loading}>
            {loading ? '处理中...' : isRegister ? '注册' : '登录'}
          </button>
        </form>

        <p style={styles.switch}>
          {isRegister ? '已有账号？' : '没有账号？'}
          <button
            style={styles.switchBtn}
            onClick={() => { setIsRegister(!isRegister); setError(''); }}
          >
            {isRegister ? '去登录' : '去注册'}
          </button>
        </p>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    minHeight: '100vh',
    backgroundColor: '#f5f5f5',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  },
  card: {
    background: '#fff',
    borderRadius: 12,
    padding: '40px 32px',
    width: 380,
    boxShadow: '0 2px 12px rgba(0,0,0,0.08)',
  },
  title: {
    fontSize: 22,
    fontWeight: 700,
    margin: '0 0 4px',
    color: '#1a1a2e',
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 14,
    color: '#666',
    margin: '0 0 28px',
    textAlign: 'center',
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: 14,
  },
  input: {
    padding: '10px 14px',
    borderRadius: 8,
    border: '1px solid #ddd',
    fontSize: 14,
    outline: 'none',
    transition: 'border-color 0.2s',
  },
  button: {
    padding: '10px',
    borderRadius: 8,
    border: 'none',
    backgroundColor: '#4B3FE3',
    color: '#fff',
    fontSize: 15,
    fontWeight: 600,
    cursor: 'pointer',
    marginTop: 6,
  },
  error: {
    color: '#e53935',
    fontSize: 13,
    textAlign: 'center',
  },
  switch: {
    fontSize: 13,
    color: '#888',
    textAlign: 'center',
    marginTop: 18,
  },
  switchBtn: {
    background: 'none',
    border: 'none',
    color: '#4B3FE3',
    fontWeight: 600,
    cursor: 'pointer',
    fontSize: 13,
    padding: 0,
    marginLeft: 4,
  },
};
