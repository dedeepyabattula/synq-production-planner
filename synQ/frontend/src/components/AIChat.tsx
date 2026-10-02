import React, { useState, useRef, useEffect } from 'react';
import { aiService } from '../api';
import { MessageSquare, Send, X, Bot, User, Minimize2, Maximize2 } from 'lucide-react';
import { AIChatMessage } from '../types';

interface AIChatProps {
  factoryId: number;
}

const AIChat: React.FC<AIChatProps> = ({ factoryId }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [messages, setMessages] = useState<AIChatMessage[]>([{
    role: 'assistant',
    content: "Hi! I'm SynQ AI. How can I help you manage production or handle disruptions today?"
  }]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (isOpen && !isMinimized) {
      scrollToBottom();
    }
  }, [messages, isOpen, isMinimized]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMsg = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setIsLoading(true);

    try {
      const res = await aiService.chat(factoryId, userMsg);
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: res.response,
        actions: res.actions
      }]);
    } catch (err) {
      console.error(err);
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: "Sorry, I had trouble processing that request. The AI server might be down." 
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 w-14 h-14 bg-synq-primary hover:bg-blue-600 rounded-full flex items-center justify-center text-white shadow-lg shadow-blue-900/50 transition-transform hover:scale-105 z-50 animate-bounce-slow"
      >
        <MessageSquare size={24} />
      </button>
    );
  }

  return (
    <div 
      className={`fixed right-6 bottom-6 bg-synq-card shadow-2xl rounded-xl border border-synq-primary/30 flex flex-col z-50 transition-all duration-300 ease-in-out ${
        isMinimized ? 'w-80 h-14' : 'w-96 h-[500px]'
      }`}
    >
      {/* Header */}
      <div 
        className="h-14 bg-synq-dark rounded-t-xl border-b border-synq-border flex items-center justify-between px-4 cursor-pointer select-none"
        onClick={() => setIsMinimized(!isMinimized)}
      >
        <div className="flex items-center gap-2">
          <div className="relative">
            <Bot size={20} className="text-synq-accent" />
            <span className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
          </div>
          <span className="font-bold text-sm">SynQ Copilot</span>
        </div>
        <div className="flex items-center gap-2 text-synq-muted">
          <button className="hover:text-synq-text transition-colors p-1">
            {isMinimized ? <Maximize2 size={16} /> : <Minimize2 size={16} />}
          </button>
          <button 
            className="hover:text-red-400 transition-colors p-1"
            onClick={(e) => { e.stopPropagation(); setIsOpen(false); }}
          >
            <X size={18} />
          </button>
        </div>
      </div>

      {/* Body & Input (hidden when minimized) */}
      {!isMinimized && (
        <>
          <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar bg-synq-card/50">
            {messages.map((m, i) => (
              <div key={i} className={`flex gap-3 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                {m.role === 'assistant' && (
                  <div className="w-8 h-8 rounded-full bg-synq-dark border border-synq-border flex items-center justify-center flex-shrink-0">
                    <Bot size={16} className="text-synq-accent" />
                  </div>
                )}
                
                <div className={`max-w-[80%] rounded-2xl p-3 text-sm ${
                  m.role === 'user' 
                    ? 'bg-synq-primary text-white rounded-tr-sm' 
                    : 'bg-synq-dark border border-synq-border text-synq-text rounded-tl-sm shadow-md'
                }`}>
                  <p className="whitespace-pre-wrap">{m.content}</p>
                  
                  {/* Action buttons if AI returned actions */}
                  {m.actions && m.actions.length > 0 && (
                    <div className="mt-3 space-y-2">
                      {m.actions.map((act, idx) => (
                        <button 
                          key={idx}
                          className="block w-full bg-synq-card hover:bg-synq-border border border-synq-primary/30 text-synq-accent text-xs p-2 rounded text-center transition-colors font-medium"
                          onClick={() => window.location.href = '/disruption'}
                        >
                          {act.type === 'disruption_detected' ? 'Open Disruption Simulator' : 'Take Action'}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {m.role === 'user' && (
                  <div className="w-8 h-8 rounded-full bg-synq-dark border border-synq-border flex items-center justify-center flex-shrink-0">
                    <User size={16} className="text-synq-muted" />
                  </div>
                )}
              </div>
            ))}
            {isLoading && (
              <div className="flex gap-3 justify-start">
                 <div className="w-8 h-8 rounded-full bg-synq-dark border border-synq-border flex items-center justify-center flex-shrink-0">
                    <Bot size={16} className="text-synq-accent" />
                  </div>
                  <div className="bg-synq-dark border border-synq-border rounded-2xl rounded-tl-sm p-4 flex items-center gap-1 shadow-md">
                    <span className="w-2 h-2 bg-synq-muted rounded-full animate-bounce"></span>
                    <span className="w-2 h-2 bg-synq-muted rounded-full animate-bounce [animation-delay:-0.15s]"></span>
                    <span className="w-2 h-2 bg-synq-muted rounded-full animate-bounce [animation-delay:-0.3s]"></span>
                  </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <form 
            onSubmit={handleSend}
            className="p-3 bg-synq-dark border-t border-synq-border rounded-b-xl flex gap-2"
          >
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder="e.g., Worker John is absent..."
              className="flex-1 bg-synq-card border border-synq-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-synq-primary transition-colors text-synq-text"
              disabled={isLoading}
            />
            <button 
              type="submit" 
              disabled={!input.trim() || isLoading}
              className="w-10 flex-shrink-0 bg-synq-primary text-white rounded-lg flex items-center justify-center disabled:opacity-50 hover:bg-blue-600 transition-colors"
            >
              <Send size={16} />
            </button>
          </form>
        </>
      )}
    </div>
  );
};

export default AIChat;
