import React, { useState, useEffect, useRef, useCallback } from 'react';
import { GenerationOptions } from '@/types/avatarTypes';
import Button from '@atlaskit/button/standard-button';
import TextField from '@atlaskit/textfield';
import SendIcon from '@atlaskit/icon/glyph/send';
import { token } from '@atlaskit/tokens';

interface InteractiveAIChatProps {
  avatarOptions: GenerationOptions;
  onClose?: () => void;
}

interface ChatMessage {
  id: string;
  type: 'user' | 'agent';
  content: string;
  timestamp: Date;
  emotion?: string;
  confidence?: number;
}

export const InteractiveAIChat: React.FC<InteractiveAIChatProps> = ({
  avatarOptions,
  onClose
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // 自動スクロール機能
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // セッションの初期化
  useEffect(() => {
    initializeChatSession();
  }, []);

  const initializeChatSession = async () => {
    try {
      setError(null);

      // 実際の実装ではバックエンドAPIを呼び出す
      const newSessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      setSessionId(newSessionId);

      // ウェルカムメッセージを追加
      const welcomeMessage: ChatMessage = {
        id: 'welcome',
        type: 'agent',
        content: `こんにちは！${avatarOptions.style}スタイルのアバターです。どのようなお手伝いができますか？`,
        timestamp: new Date(),
        emotion: 'friendly',
        confidence: 0.95
      };

      setMessages([welcomeMessage]);

    } catch (err) {
      setError('チャットセッションの初期化に失敗しました。');
      console.error('Chat initialization error:', err);
    }
  };

  const sendMessage = async () => {
    if (!inputMessage.trim() || isLoading || !sessionId) return;

    const userMessage: ChatMessage = {
      id: `user_${Date.now()}`,
      type: 'user',
      content: inputMessage.trim(),
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);
    setError(null);

    try {
      // 実際の実装ではバックエンドAPIを呼び出す
      await new Promise(resolve => setTimeout(resolve, 1000 + Math.random() * 2000));

      // シミュレートされたAI応答
      const aiResponses = [
        `「${userMessage.content}」についてお答えします。興味深い質問ですね！`,
        'それは素晴らしいアイデアです。一緒に詳しく考えていきましょう。',
        'ご質問ありがとうございます。私の知識に基づいてお答えします。',
        'なるほど、よくわかりました。追加の情報が必要ですか？',
        'とても良いポイントですね。さらなる詳細を共有します。'
      ];

      const randomResponse = aiResponses[Math.floor(Math.random() * aiResponses.length)];

      const agentMessage: ChatMessage = {
        id: `agent_${Date.now()}`,
        type: 'agent',
        content: randomResponse,
        timestamp: new Date(),
        emotion: 'helpful',
        confidence: 0.85 + Math.random() * 0.1
      };

      setMessages(prev => [...prev, agentMessage]);

    } catch (err) {
      setError('メッセージの送信に失敗しました。もう一度お試しください。');
      console.error('Send message error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const clearChat = () => {
    setMessages([]);
    setError(null);
    initializeChatSession();
  };

  return (
    <div style={{
      width: '100%',
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      backgroundColor: token('color.background.neutral', '#FAFBFC'),
      borderRadius: '8px',
      overflow: 'hidden'
    }}>
      {/* ヘッダー */}
      <div style={{
        backgroundColor: token('color.background.brand', '#0C5CFF'),
        color: 'white',
        padding: '16px 20px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <div>
          <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600 }}>
            インタラクティブAIアバター
          </h3>
          <p style={{ margin: '4px 0 0 0', fontSize: '0.85rem', opacity: 0.9 }}>
            {avatarOptions.style}スタイル | {avatarOptions.complexity}モード
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <Button
            appearance="subtle"
            onClick={clearChat}
            style={{ color: 'white' }}
          >
            クリア
          </Button>
          {onClose && (
            <Button
              appearance="subtle"
              onClick={onClose}
              style={{ color: 'white' }}
            >
              閉じる
            </Button>
          )}
        </div>
      </div>

      {/* エラーメッセージ */}
      {error && (
        <div style={{
          backgroundColor: token('color.background.warning', '#FFF3CD'),
          color: token('color.text.warning', '#856404'),
          padding: '12px 16px',
          borderBottom: `1px solid ${token('color.border.warning', '#FFC107')}`
        }}>
          {error}
        </div>
      )}

      {/* メッセージエリア */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '16px',
        maxHeight: '400px'
      }}>
        {messages.length === 0 ? (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            color: token('color.text.subtle', '#6B778C'),
            fontSize: '0.9rem'
          }}>
            会話を開始してください...
          </div>
        ) : (
          messages.map((message) => (
            <div
              key={message.id}
              style={{
                marginBottom: '16px',
                display: 'flex',
                justifyContent: message.type === 'user' ? 'flex-end' : 'flex-start'
              }}
            >
              <div
                style={{
                  maxWidth: '70%',
                  padding: '12px 16px',
                  borderRadius: '16px',
                  backgroundColor: message.type === 'user'
                    ? token('color.background.brand', '#0C5CFF')
                    : token('color.background.neutral.subtle', '#F4F5F7'),
                  color: message.type === 'user'
                    ? 'white'
                    : token('color.text', '#172B4D'),
                  boxShadow: '0 1px 2px rgba(0, 0, 0, 0.1)'
                }}
              >
                <div style={{ marginBottom: '4px' }}>
                  {message.content}
                </div>
                <div style={{
                  fontSize: '0.7rem',
                  opacity: 0.7,
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}>
                  <span>
                    {message.timestamp.toLocaleTimeString('ja-JP', {
                      hour: '2-digit',
                      minute: '2-digit'
                    })}
                  </span>
                  {message.type === 'agent' && message.confidence && (
                    <span>
                      信頼度: {Math.round(message.confidence * 100)}%
                    </span>
                  )}
                </div>
                {message.emotion && (
                  <div style={{
                    fontSize: '0.7rem',
                    opacity: 0.7,
                    marginTop: '2px'
                  }}>
                    感情: {message.emotion}
                  </div>
                )}
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* 入力エリア */}
      <div style={{
        padding: '16px 20px',
        borderTop: `1px solid ${token('color.border', '#DFE1E6')}`,
        backgroundColor: 'white'
      }}>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <TextField
            ref={inputRef}
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="メッセージを入力してください..."
            isDisabled={isLoading}
            style={{ flex: 1 }}
            aria-label="メッセージ入力"
          />
          <Button
            appearance="primary"
            onClick={sendMessage}
            isDisabled={!inputMessage.trim() || isLoading}
            iconBefore={<SendIcon label="送信" />}
            aria-label="メッセージを送信"
          >
            {isLoading ? '送信中...' : '送信'}
          </Button>
        </div>

        {/* ヒントテキスト */}
        <div style={{
          marginTop: '8px',
          fontSize: '0.75rem',
          color: token('color.text.subtle', '#6B778C')
        }}>
          💡 ヒント: アバターの設定、生成、または一般的な質問をお試しください
        </div>
      </div>
    </div>
  );
};
