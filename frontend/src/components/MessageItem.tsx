import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import type { Message } from '../store/chatStore';

interface Props {
  message: Message;
}

export default function MessageItem({ message }: Props) {
  const isUser = message.role === 'user';

  return (
    <div style={{
      display: 'flex',
      justifyContent: isUser ? 'flex-end' : 'flex-start',
      marginBottom: 16,
    }}>
      <div style={{
        maxWidth: '75%',
        padding: '10px 14px',
        borderRadius: isUser ? '16px 16px 2px 16px' : '16px 16px 16px 2px',
        backgroundColor: isUser ? '#4B3FE3' : '#fff',
        color: isUser ? '#fff' : '#1a1a2e',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        lineHeight: 1.6,
        fontSize: 14,
      }}>
        {isUser ? (
          <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{message.content}</p>
        ) : (
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              code({ node, inline, className, children, ...props }: any) {
                const match = /language-(\w+)/.exec(className || '');
                return !inline && match ? (
                  <SyntaxHighlighter
                    style={oneDark}
                    language={match[1]}
                    PreTag="div"
                    {...props}
                  >
                    {String(children).replace(/\n$/, '')}
                  </SyntaxHighlighter>
                ) : (
                  <code style={{
                    background: '#f0f0f0',
                    padding: '2px 6px',
                    borderRadius: 4,
                    fontSize: 13,
                  }} {...props}>{children}</code>
                );
              },
              p({ children }: any) {
                return <p style={{ margin: '0 0 8px' }}>{children}</p>;
              },
            }}
          >
            {message.content}
          </ReactMarkdown>
        )}
        {message.needHuman && (
          <div style={{
            marginTop: 8,
            padding: '6px 10px',
            background: '#fff3e0',
            borderRadius: 6,
            fontSize: 12,
            color: '#e65100',
          }}>
            该问题需要转接人工客服
          </div>
        )}
      </div>
    </div>
  );
}
