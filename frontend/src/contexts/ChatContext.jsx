import React, { createContext, useContext, useState, useEffect } from 'react';

const ChatContext = createContext();

export const ChatProvider = ({ children }) => {
  // Initialize from localStorage or empty array
  const [messages, setMessages] = useState(() => {
    try {
      const saved = localStorage.getItem('chatMessages');
      return saved ? JSON.parse(saved) : [];
    } catch (e) {
      console.error('Failed to load messages from localStorage:', e);
      return [];
    }
  });

  // Auto-save to localStorage whenever messages change
  // Filter out large content (plots, dataframes, etc.) to avoid quota issues
  useEffect(() => {
    try {
      // Only save lightweight messages (user input and text responses)
      const lightMessages = messages
        .map(msg => {
          // Keep user messages as-is
          if (msg.role === 'user') {
            return msg;
          }
          // For assistant messages, filter out large content types
          if (msg.role === 'assistant') {
            // Skip plotly charts, dataframes, and other large content
            if (msg.type === 'plotly' || msg.type === 'dataframe' || msg.type === 'pdb') {
              return null; // Don't save these
            }
            // Keep text messages and tool calls (they're small)
            return msg;
          }
          return msg;
        })
        .filter(msg => msg !== null) // Remove null entries
        .slice(-100); // Keep only last 100 lightweight messages
      
      localStorage.setItem('chatMessages', JSON.stringify(lightMessages));
    } catch (e) {
      console.error('Failed to save messages to localStorage:', e);
      // If still fails, try emergency cleanup
      try {
        // Keep only the most essential messages
        const essentialMessages = messages
          .filter(msg => msg.role === 'user' || (msg.role === 'assistant' && msg.type === 'text'))
          .slice(-50);
        localStorage.setItem('chatMessages', JSON.stringify(essentialMessages));
      } catch (retryError) {
        console.warn('Emergency cleanup also failed, clearing localStorage:', retryError);
        localStorage.removeItem('chatMessages');
      }
    }
  }, [messages]);

  const clearMessages = () => {
    setMessages([]);
    localStorage.removeItem('chatMessages');
  };

  return (
    <ChatContext.Provider value={{ messages, setMessages, clearMessages }}>
      {children}
    </ChatContext.Provider>
  );
};

export const useChatContext = () => {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error('useChatContext must be used within ChatProvider');
  }
  return context;
};
