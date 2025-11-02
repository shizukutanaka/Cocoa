import React, { useReducer, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import useWebSocket from 'react-use-websocket';
import { PageLayout, Content, Main, RightSidebar } from '@atlaskit/page-layout';
import PageHeader from '@atlaskit/page-header';
import Button from '@atlaskit/button/standard-button';
import Textfield from '@atlaskit/textfield';
import Lozenge from '@atlaskit/lozenge';
import Avatar, { AvatarGroup } from '@atlaskit/avatar';
import { token } from '@atlaskit/tokens';

import SendIcon from '@atlaskit/icon/glyph/send';
import PeopleIcon from '@atlaskit/icon/glyph/people';
import CommentIcon from '@atlaskit/icon/glyph/comment';
import BrushIcon from '@atlaskit/icon/glyph/brush';
import EditorPanelIcon from '@atlaskit/icon/glyph/editor/panel';
import ImageIcon from '@atlaskit/icon/glyph/image';
import { TopBar } from '@atlaskit/page-layout';

interface Message {
  id: string
  user_id: string
  username: string
  content: string
  timestamp: string
  type: 'text' | 'system'
}

interface Participant {
  id: string
  username: string
  role: 'owner' | 'moderator' | 'participant'
}

// Reducerのための型定義
type State = {
  messages: Message[];
  participants: Participant[];
  newMessage: string;
  isConnected: boolean;
};

type Action = 
  | { type: 'SET_MESSAGES'; payload: Message[] }
  | { type: 'ADD_MESSAGE'; payload: Message }
  | { type: 'SET_PARTICIPANTS'; payload: Participant[] }
  | { type: 'SET_NEW_MESSAGE'; payload: string }
  | { type: 'SET_CONNECTION_STATUS'; payload: boolean };

const initialState: State = {
  messages: [],
  participants: [],
  newMessage: '',
  isConnected: false,
};

const reducer = (state: State, action: Action): State => {
  switch (action.type) {
    case 'SET_MESSAGES':
      return { ...state, messages: action.payload };
    case 'ADD_MESSAGE':
      return { ...state, messages: [...state.messages, action.payload] };
    case 'SET_PARTICIPANTS':
      return { ...state, participants: action.payload };
    case 'SET_NEW_MESSAGE':
      return { ...state, newMessage: action.payload };
    case 'SET_CONNECTION_STATUS':
      return { ...state, isConnected: action.payload };
    default:
      return state;
  }
};

const CollaborationRoom: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [state, dispatch] = useReducer(reducer, initialState);
  const { messages, participants, newMessage, isConnected } = state;
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // WebSocket接続
  const socketUrl = `ws://localhost:8003/ws/collaboration/${sessionId}?token=valid_token`

  const { sendMessage, lastMessage } = useWebSocket(socketUrl, {
    onOpen: () => {
      console.log('WebSocket接続が開きました');
      dispatch({ type: 'SET_CONNECTION_STATUS', payload: true });
    },
    onClose: () => {
      console.log('WebSocket接続が閉じました');
      dispatch({ type: 'SET_CONNECTION_STATUS', payload: false });
    },
    onError: (error) => {
      console.error('WebSocketエラー:', error)
    },
    shouldReconnect: (closeEvent) => true,
  })

  // メッセージ受信処理
  useEffect(() => {
    if (lastMessage !== null) {
      const data = JSON.parse(lastMessage.data);

      if (data.type === 'chat') {
        dispatch({ type: 'ADD_MESSAGE', payload: data.message });
      } else if (data.type === 'session_info') {
        dispatch({ type: 'SET_PARTICIPANTS', payload: data.participants });
        dispatch({ type: 'SET_MESSAGES', payload: data.messages });
      }
    }
  }, [lastMessage]);

  // メッセージ送信
  const handleSendMessage = () => {
    if (newMessage.trim()) {
      const messageData = {
        type: 'chat',
        content: newMessage,
        user_id: 'current_user_id',
        username: '現在のユーザー',
        timestamp: new Date().toISOString()
      }

      sendMessage(JSON.stringify(messageData));
      dispatch({ type: 'SET_NEW_MESSAGE', payload: '' });
    }
  }

  // 自動スクロール
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const breadcrumbs = (
    <div />
  );

  const actions = (
    <Button appearance="primary">保存</Button>
  );

  const bar = (
    <div style={{ display: 'flex', alignItems: 'center', gap: token('space.100', '8px') }}>
      <Lozenge appearance={isConnected ? 'success' : 'removed'}>
        {isConnected ? '接続中' : '切断中'}
      </Lozenge>
    </div>
  );

  return (
    <PageLayout>
      <TopBar>
        <PageHeader breadcrumbs={breadcrumbs} actions={actions} bottomBar={bar}>
          コラボレーションセッション
        </PageHeader>
      </TopBar>
      <Content>
        <Main>
          {/* 3Dビューアーエリア */}
          <div style={{ flex: 1, backgroundColor: token('color.background.neutral.subtle', '#FAFBFC'), position: 'relative', height: '100%' }}>
            <div style={{ position: 'absolute', top: 0, left: 0, right: 0, padding: token('space.150', '12px'), backgroundColor: token('elevation.surface', '#FFF'), borderBottom: `1px solid ${token('color.border', '#DFE1E6')}` }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: token('space.100', '8px') }}>
                <BrushIcon label="edit" />
                <span>アバターエディタ</span>
                <div style={{ width: '1px', height: '16px', backgroundColor: token('color.border', '#DFE1E6'), margin: `0 ${token('space.100', '8px')}` }} />
                <Button appearance="subtle">ツール1</Button>
                <Button appearance="subtle">ツール2</Button>
              </div>
            </div>
            <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <div style={{ textAlign: 'center', color: token('color.text.subtlest', '#6B778C') }}>
                <ImageIcon label="3d-viewer" size="xlarge" />
                <p style={{ marginTop: token('space.200', '16px') }}>3Dアバタービューアー</p>
              </div>
            </div>
          </div>
        </Main>
        <RightSidebar>
          <div style={{ padding: token('space.200', '16px') }}>
            <h3 style={{ display: 'flex', alignItems: 'center', gap: token('space.100', '8px'), fontSize: '1.2rem', fontWeight: 500, marginBottom: token('space.150', '12px') }}>
              <PeopleIcon label="participants" />
              参加者
            </h3>
            <AvatarGroup
              appearance="stack"
              data={participants.map(p => ({ key: p.id, name: p.username, src: '' }))}
              size="medium"
            />
          </div>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', borderTop: `1px solid ${token('color.border', '#DFE1E6')}` }}>
            <h3 style={{ display: 'flex', alignItems: 'center', gap: token('space.100', '8px'), fontSize: '1.2rem', fontWeight: 500, padding: token('space.200', '16px'), borderBottom: `1px solid ${token('color.border', '#DFE1E6')}` }}>
              <CommentIcon label="chat" />
              チャット
            </h3>
            <div style={{ flex: 1, overflowY: 'auto', padding: token('space.200', '16px') }}>
              {messages.map((message) => (
                <div key={message.id} style={{ display: 'flex', gap: token('space.150', '12px'), marginBottom: token('space.150', '12px') }}>
                  <Avatar name={message.username} size="medium" />
                  <div>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: token('space.100', '8px') }}>
                      <span style={{ fontWeight: 600 }}>{message.username}</span>
                      <span style={{ color: token('color.text.subtlest', '#6B778C'), fontSize: '0.8rem' }}>
                        {new Date(message.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    <p>{message.content}</p>
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
            <div style={{ padding: token('space.200', '16px'), borderTop: `1px solid ${token('color.border', '#DFE1E6')}` }}>
              <form onSubmit={(e) => { e.preventDefault(); handleSendMessage(); }} style={{ display: 'flex', gap: token('space.100', '8px') }}>
                <Textfield
                  name="newMessage"
                  placeholder="メッセージを入力..."
                  value={newMessage}
                  onChange={(e: any) => dispatch({ type: 'SET_NEW_MESSAGE', payload: e.target.value })}
                />
                <Button type="submit" appearance="primary" iconBefore={<SendIcon label="send" />} />
              </form>
            </div>
          </div>
        </RightSidebar>
      </Content>
    </PageLayout>
  )
}

export default CollaborationRoom
