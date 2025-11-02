import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from 'react-query';
import { Toaster } from 'react-hot-toast';
import {
  PageLayout,
  Content,
  Main,
  LeftSidebar,
  TopBar,
} from '@atlaskit/page-layout';

// スタイルインポート
import './styles/index.css';

// ページコンポーネント
import Dashboard from '@/pages/Dashboard';
import AvatarEditor from '@/pages/AvatarEditor';
import AvatarList from '@/pages/AvatarList'; // 新しく追加
import CollaborationRoom from '@/pages/CollaborationRoom';
import AIGenerator from '@/pages/AIGenerator';
import Monitoring from '@/pages/Monitoring';

// 共通コンポーネント
import Header from '@/components/Header';
import Sidebar from '@/components/Sidebar';

// クエリクライアント設定
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <PageLayout>
          <TopBar>
            <Header />
          </TopBar>
          <Content>
            <LeftSidebar>
              <Sidebar />
            </LeftSidebar>
            <Main>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/avatars" element={<AvatarList />} /> {/* 新しく追加 */}
                <Route path="/avatars/:id" element={<AvatarEditor />} />
                <Route path="/monitoring" element={<Monitoring />} />
                <Route path="/collaboration/:sessionId" element={<CollaborationRoom />} />
                <Route path="/ai-generator" element={<AIGenerator />} />
              </Routes>
            </Main>
          </Content>
        </PageLayout>
        <Toaster position="top-right" />
      </Router>
    </QueryClientProvider>
  );
}

export default App
