import React, { useState, useEffect, useRef, memo, useCallback, useMemo } from 'react';
import { Input, Button, Card, Space, Alert, Spin } from 'antd';
import { SendOutlined, ClearOutlined, DownloadOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import rehypeRaw from 'rehype-raw';
import remarkGfm from 'remark-gfm';
import axios from 'axios';
import { useChatContext } from '../contexts/ChatContext';
import './ChatPanel.css';

const { TextArea } = Input;

// ============================================================
// 消息列表独立组件 - 深度优化版本
// ============================================================

// 1. Plotly 图表组件 - 用 memo 包裹避免重复渲染
const PlotlyFrame = memo(function PlotlyFrame({ plotlyMsg, pIndex, className }) {
  return (
    <iframe
      className={className}
      srcDoc={plotlyMsg.content}
      title={`Plotly Visualization ${pIndex + 1}`}
      loading="lazy"
    />
  );
});

// 2. PDB 结构查看器组件 - 用 memo 包裹
const PDBViewer = memo(function PDBViewer({ msg, viewerKey }) {
  const containerRef = useRef(null);
  
  useEffect(() => {
    const el = containerRef.current;
    if (el && msg.content && !el.dataset.initialized) {
      el.dataset.initialized = 'true';
      
      const initViewer = () => {
        if (window.$3Dmol) {
          const viewer = window.$3Dmol.createViewer(el, { 
            backgroundColor: 'white', 
            width: '100%', 
            height: 700 
          });
          viewer.addModel(msg.content, 'pdb');
          viewer.setStyle({}, { cartoon: { color: 'spectrum' } });
          viewer.zoomTo();
          viewer.render();
        }
      };
      
      if (!window.$3Dmol) {
        const script = document.createElement('script');
        script.src = 'https://3dmol.csb.pitt.edu/build/3Dmol-min.js';
        script.onload = initViewer;
        document.head.appendChild(script);
      } else {
        initViewer();
      }
    }
  }, [msg.content, msg.sequence]);
  
  const handleDownload = useCallback(() => {
    const blob = new Blob([msg.content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${msg.sequence || 'structure'}.pdb`;
    a.click();
    URL.revokeObjectURL(url);
  }, [msg.content, msg.sequence]);
  
  return (
    <div className="message message-assistant">
      <div className="plotly-grid-title">
        🧬 3D Structure: {msg.sequence || 'Unknown'}
      </div>
      <div className="pdb-structure-container">
        <div
          id={`viewer-${viewerKey}`}
          className="pdb-viewer"
          ref={containerRef}
        />
        <div style={{ marginTop: 12, textAlign: 'center' }}>
          <Button
            size="small"
            icon={<DownloadOutlined />}
            onClick={handleDownload}
          >
            Download PDB
          </Button>
        </div>
      </div>
    </div>
  );
});

// 3. 主消息列表组件
const MessageList = memo(function MessageList({ messages, messagesEndRef, lastAssistantMessageId }) {
  // 使用 useMemo 缓存渲染结果，只在关键条件变化时才重新计算
  const rendered = useMemo(() => {
    const result = [];
    let plotlyBuffer = [];
    let textBuffer = '';
    let currentRole = null;
    let keyCounter = 0;

    const flushTextBuffer = () => {
      if (textBuffer && currentRole) {
        result.push(
          <div key={`text-${keyCounter++}`} className={`message message-${currentRole}`}>
            {currentRole === 'user' && (
              <div className="message-bubble user-message">
                {textBuffer}
              </div>
            )}
            {currentRole === 'assistant' && (
              <div className="assistant-message">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  rehypePlugins={[rehypeRaw]}
                  components={{
                    img: ({node, ...props}) => (
                      <img
                        {...props}
                        style={{ maxWidth: '100%', height: 'auto', borderRadius: '8px' }}
                        onError={(e) => {
                          console.warn("⚠️ 图片加载失败，已自动隐藏:", props.src);
                          e.target.style.display = 'none';
                        }}
                      />
                    ),
                    div: ({node, ...props}) => (
                      <div {...props} style={{ width: '100%', overflowX: 'auto' }} />
                    )
                  }}
                >
                  {textBuffer}
                </ReactMarkdown>
              </div>
            )}
          </div>
        );
        textBuffer = '';
      }
    };

    const flushPlotlyBuffer = () => {
      if (plotlyBuffer.length > 0) {
        const isParetoCharts = plotlyBuffer.length === 3;
        const isDashboard = plotlyBuffer.length === 1 &&
          (plotlyBuffer[0].content.includes('Model Performance Overview') ||
           plotlyBuffer[0].content.includes('MIC Distribution'));

        result.push(
          <div key={`plotly-container-${keyCounter++}`}>
            {isParetoCharts && (
              <div className="plotly-grid-title">
                🎯 Multi-Objective Optimization: Pareto Front Analysis
              </div>
            )}
            {isDashboard && (
              <div className="plotly-grid-title">
                📊 Multi-Generator Comparison Dashboard
              </div>
            )}
            <div className={isParetoCharts ? "plotly-grid pareto-grid" : ""}>
              {plotlyBuffer.map((plotlyMsg, pIndex) => (
                <PlotlyFrame
                  key={pIndex}
                  plotlyMsg={plotlyMsg}
                  pIndex={pIndex}
                  className={isDashboard ? "plotly-frame-dashboard" : "plotly-frame"}
                />
              ))}
            </div>
          </div>
        );
        plotlyBuffer = [];
      }
    };

    // 遍历消息 - 优化：不再跳过消息，让 RAF 节流处理
    messages.forEach((msg, index) => {
      // ✅ 不再跳过任何消息 - 所有进度都实时显示给用户
      // RAF 会自动节流到每帧更新一次，避免闪烁
      
      if (msg.role === 'assistant' && msg.type === 'plotly') {
        flushTextBuffer();
        currentRole = null;
        plotlyBuffer.push(msg);
      } else if (msg.role === 'assistant' && msg.type === 'html_table') {
        flushTextBuffer();
        flushPlotlyBuffer();
        currentRole = null;
        result.push(
          <div key={`table-${keyCounter++}`} className="message message-assistant">
            <div className="table-container" dangerouslySetInnerHTML={{ __html: msg.content }} />
          </div>
        );
      } else if (msg.role === 'assistant' && msg.type === 'pdb') {
        flushTextBuffer();
        flushPlotlyBuffer();
        currentRole = null;
        result.push(
          <PDBViewer
            key={`pdb-${keyCounter++}`}
            msg={msg}
            viewerKey={keyCounter - 1}
          />
        );
      } else if (msg.role === 'error') {
        flushTextBuffer();
        flushPlotlyBuffer();
        currentRole = null;
        result.push(
          <div key={`error-${keyCounter++}`} className="message message-error">
            <Alert title="Error" description={msg.content} type="error" />
          </div>
        );
      } else {
        flushPlotlyBuffer();
        if (currentRole && currentRole !== msg.role) {
          flushTextBuffer();
        }
        currentRole = msg.role;
        textBuffer += msg.content;
      }
    });

    flushTextBuffer();
    flushPlotlyBuffer();

    return result;
  }, [messages, lastAssistantMessageId]); // ✅ 只在完整消息变化时重新渲染

  return (
    <div className="messages-container">
      {rendered}
      <div ref={messagesEndRef} />
    </div>
  );
});

function ChatPanel() {
  const { messages, setMessages, clearMessages } = useChatContext();
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);
  
  // Refs to track latest values for useCallback (avoid stale closure)
  const inputValueRef = useRef(inputValue);
  const isLoadingRef = useRef(isLoading);
  const messagesRef = useRef(messages); // Track messages for scrolling
  
  // Keep refs in sync with state
  useEffect(() => {
    inputValueRef.current = inputValue;
  }, [inputValue]);
  
  useEffect(() => {
    isLoadingRef.current = isLoading;
  }, [isLoading]);
  
  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  // 优化 1：只在 Assistant 完成响应且有新消息时才滚动
  const [lastAssistantMessageId, setLastAssistantMessageId] = useState(null);
  
  useEffect(() => {
    if (!isLoading && messagesRef.current.length > 0) {
      // Assistant 完成响应，滚动到底部
      setTimeout(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
      }, 100);
    }
  }, [isLoading]);

  // Handle sending message - useCallback 依赖 setMessages/setIsLoading（稳定引用）
  const handleSend = useCallback(async () => {
    const currentInputValue = inputValueRef.current;
    const currentIsLoading = isLoadingRef.current;
    
    if (!currentInputValue.trim() || currentIsLoading) return;

    const userMessage = currentInputValue.trim();
    setInputValue('');
    
    // Add user message
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setIsLoading(true);

    try {
      // Create EventSource for SSE streaming
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: userMessage }),
      });

      if (!response.ok) {
        throw new Error('Failed to connect to backend');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      
      // 流式文本缓冲 - 使用 index 精确更新同一条消息
      let localTextBuffer = '';
      let localRafId = null;
      let textMsgIndex = -1; // 记录当前文本消息在 messages 数组中的位置
      
      // 添加初始 assistant 文本消息，记录其 index
      setMessages(prev => {
        textMsgIndex = prev.length; // 新消息将插入在此位置
        return [...prev, { role: 'assistant', content: '', type: 'text', completed: false }];
      });

      const flushLocalTextBuffer = () => {
        if (!localTextBuffer) return;
        const toFlush = localTextBuffer;
        localTextBuffer = '';
        setMessages(prev => {
          const newMessages = [...prev];
          // 找到最后一条 type=text 的 assistant 消息并追加
          for (let i = newMessages.length - 1; i >= 0; i--) {
            if (newMessages[i].role === 'assistant' && newMessages[i].type === 'text') {
              newMessages[i] = { ...newMessages[i], content: newMessages[i].content + toFlush };
              return newMessages;
            }
          }
          // fallback: 没有找到则新建
          newMessages.push({ role: 'assistant', content: toFlush, type: 'text' });
          return newMessages;
        });
      };

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop(); // Keep incomplete line in buffer

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              if (data.type === 'text') {
                // 直接追加到 buffer，使用 RAF 节流
                localTextBuffer += data.content;
                
                // 取消之前的 RAF，只在下一帧更新
                if (localRafId) cancelAnimationFrame(localRafId);
                localRafId = requestAnimationFrame(() => {
                  flushLocalTextBuffer();
                  localRafId = null;
                });
              } else if (data.type === 'dataframe') {
                // Flush text buffer first
                flushLocalTextBuffer();
                
                // Handle DataFrame display
                setMessages(prev => {
                  const newMessages = [...prev];
                  newMessages.push({
                    role: 'assistant',
                    content: data.content,
                    type: 'dataframe'
                  });
                  return newMessages;
                });
              } else if (data.type === 'plotly_html') {
                // Flush text buffer first
                flushLocalTextBuffer();
                
                // Handle Plotly visualization
                const htmlContent =
                  typeof data.content === 'string'
                    ? data.content
                    : data.content && typeof data.content.content === 'string'
                      ? data.content.content
                      : '';
                if (!htmlContent) {
                  console.warn('Received empty Plotly HTML content from SSE:', data);
                }
                setMessages(prev => {
                  const newMessages = [...prev];
                  newMessages.push({
                    role: 'assistant',
                    content: htmlContent,
                    type: 'plotly'
                  });
                  return newMessages;
                });
              } else if (data.type === 'html_table') {
                // Flush text buffer first
                flushLocalTextBuffer();
                
                // Handle HTML table visualization
                setMessages(prev => {
                  const newMessages = [...prev];
                  newMessages.push({
                    role: 'assistant',
                    content: data.content,
                    type: 'html_table'
                  });
                  return newMessages;
                });
              } else if (data.type === 'pdb_data') {
                // Flush text buffer first
                flushLocalTextBuffer();
                
                // Handle PDB structure visualization
                setMessages(prev => {
                  const newMessages = [...prev];
                  newMessages.push({
                    role: 'assistant',
                    content: data.content,
                    sequence: data.sequence || '',
                    type: 'pdb'
                  });
                  return newMessages;
                });
              } else if (data.type === 'end') {
                // Stream ended
                break;
              } else if (data.type === 'error') {
                throw new Error(data.content);
              }
            } catch (e) {
              console.error('Failed to parse SSE data:', e);
            }
          }
        }
      }
      
      // Flush remaining text buffer and mark as complete
      if (localRafId) cancelAnimationFrame(localRafId);
      flushLocalTextBuffer();
      
      // Mark last message as complete
      setMessages(prev => {
        const newMessages = [...prev];
        const lastMsg = newMessages[newMessages.length - 1];
        if (lastMsg && lastMsg.role === 'assistant') {
          lastMsg.completed = true;
        }
        return newMessages;
      });
      
      setLastAssistantMessageId(Date.now()); // Trigger scroll
    } catch (error) {
      console.error('Error:', error);
      setMessages(prev => [...prev, {
        role: 'error',
        content: `❌ Error: ${error.message}`
      }]);
    } finally {
      setIsLoading(false);
    }
  }, [setMessages, setIsLoading]); // ✅ 只依赖稳定的 dispatch 函数，不依赖 inputValue/isLoading

  // Handle clear chat
  const handleClear = useCallback(() => {
    clearMessages();
  }, [clearMessages]);

  // Handle Enter key
  const handleKeyPress = useCallback((e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }, [handleSend]);

  return (
    <div className="chat-panel">
      <Alert
        title="💡 Hint"
        description="Try 'Design 5 peptides against Gram-negative bacteria' or 'Analyze sequence KLLKLLK'"
        type="info"
        showIcon
        closable
        style={{ marginBottom: 16 }}
      />

      <Card
        title="Chat Lab"
        extra={
          <Button
            icon={<ClearOutlined />}
            onClick={handleClear}
            disabled={messages.length === 0}
          >
            Clear
          </Button>
        }
        style={{ height: 'calc(100vh - 300px)', display: 'flex', flexDirection: 'column' }}
        styles={{ body: { flex: 1, overflow: 'auto', padding: 16 } }}
      >
        {/* 消息列表用深度优化的 memo 组件 */}
        <MessageList 
          messages={messages} 
          messagesEndRef={messagesEndRef} 
          lastAssistantMessageId={lastAssistantMessageId}
        />
        {isLoading && (
          <div className="message message-loading" style={{ textAlign: 'center', padding: '20px' }}>
            <Spin size="large" />
            <div style={{ marginTop: 10, color: '#666' }}>Agent is thinking...</div>
          </div>
        )}
      </Card>

      <Space.Compact style={{ width: '100%', marginTop: 16 }}>
        <TextArea
          id="chat-input"
          name="message"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Enter your command..."
          autoSize={{ minRows: 1, maxRows: 4 }}
          disabled={isLoading}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSend}
          loading={isLoading}
          disabled={!inputValue.trim()}
        >
          Send
        </Button>
      </Space.Compact>
    </div>
  );
}

export default ChatPanel;
