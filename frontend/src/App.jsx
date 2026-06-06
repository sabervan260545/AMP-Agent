import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import { Layout, Menu } from 'antd';
import { CommentOutlined, DatabaseOutlined, DashboardOutlined, FileTextOutlined, ExperimentOutlined, BookOutlined, ThunderboltOutlined } from '@ant-design/icons';
import ChatPanel from './components/ChatPanel';
import SequencePanel from './components/SequencePanel';
import ServiceHealth from './components/ServiceHealth';
import LogViewer from './components/LogViewer';
import GraphRAGTest from './components/GraphRAGTest';
import StructureDemoGuide from './components/StructureDemoGuide';
import EvalsDashboard from './components/EvalsDashboard';
import { ChatProvider } from './contexts/ChatContext';
import './App.css';

const { Header, Content, Sider } = Layout;

function App() {
  const menuItems = [
    {
      key: '/',
      icon: <CommentOutlined />,
      label: <Link to="/">Chat Lab</Link>,
    },
    {
      key: '/sequences',
      icon: <DatabaseOutlined />,
      label: <Link to="/sequences">Sequence Assets</Link>,
    },
    {
      key: '/health',
      icon: <DashboardOutlined />,
      label: <Link to="/health">Service Health</Link>,
    },
    {
      key: '/logs',
      icon: <FileTextOutlined />,
      label: <Link to="/logs">Tool Logs</Link>,
    },
    {
      key: '/graph-rag',
      icon: <ExperimentOutlined />,
      label: <Link to="/graph-rag">Knowledge Brain</Link>,
    },
    {
      key: '/evals',
      icon: <ThunderboltOutlined />,
      label: <Link to="/evals">Evals Dashboard</Link>,
    },
    {
      key: '/structure-demo',
      icon: <BookOutlined />,
      label: <Link to="/structure-demo">User Guide</Link>,
    },
  ];

  return (
    <ChatProvider>
      <Router>
        <Layout style={{ minHeight: '100vh' }}>
        <Sider theme="light" width={200}>
          <div style={{ 
            height: 64, 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center',
            fontSize: 18,
            fontWeight: 'bold',
            borderBottom: '1px solid #f0f0f0'
          }}>
            🧬 AMP Agent
          </div>
          <Menu
            mode="inline"
            defaultSelectedKeys={['/']}
            items={menuItems}
            style={{ borderRight: 0 }}
          />
        </Sider>
        <Layout>
          <Header style={{ 
            background: '#fff', 
            padding: '0 24px',
            borderBottom: '1px solid #f0f0f0',
            display: 'flex',
            alignItems: 'center'
          }}>
            <h2 style={{ margin: 0 }}>AMP Generation & Analysis Platform</h2>
          </Header>
          <Content style={{ margin: '24px', background: '#fff', padding: 24 }}>
            <Routes>
              <Route path="/" element={<ChatPanel />} />
              <Route path="/sequences" element={<SequencePanel />} />
              <Route path="/health" element={<ServiceHealth />} />
              <Route path="/logs" element={<LogViewer />} />
              <Route path="/graph-rag" element={<GraphRAGTest />} />
              <Route path="/evals" element={<EvalsDashboard />} />
              <Route path="/structure-demo" element={<StructureDemoGuide />} />
            </Routes>
          </Content>
        </Layout>
      </Layout>
    </Router>
    </ChatProvider>
  );
}

export default App;
/* Force rebuild Tue Jan  6 11:52:19 AM CST 2026 */
