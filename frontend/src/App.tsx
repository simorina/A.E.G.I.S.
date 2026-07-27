import React, { useState, useEffect, useCallback } from 'react';
import { Navbar } from './components/Navbar';
import { Sidebar } from './components/Sidebar';
import { ChatContainer } from './components/ChatContainer';
import { Composer } from './components/Composer';
import { MapView } from './components/MapView';
import { ThreeCanvas } from './components/ThreeCanvas';
import { TimeTravelModal, SatScanModal, LoginModal } from './components/Modals';
import { AuthPortal } from './components/AuthPortal';
import { apiFetch, getApiBaseUrl } from './utils/api';
import type { Message, Conversation, Viewport, User, ThinkingStep, Checkpoint } from './types';

export const App: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(true);
  const [showThreeCanvas, setShowThreeCanvas] = useState<boolean>(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [activeGeojson, setActiveGeojson] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [awaitingInput, setAwaitingInput] = useState<boolean>(false);

  // Modals state
  const [loginOpen, setLoginOpen] = useState<boolean>(false);
  const [historyOpen, setHistoryOpen] = useState<boolean>(false);
  const [scanOpen, setScanOpen] = useState<boolean>(false);
  const [checkpoints, setCheckpoints] = useState<Checkpoint[]>([]);
  const [isScanning, setIsScanning] = useState<boolean>(false);
  const [scanResult, setScanResult] = useState<string | null>(null);

  // User state & Viewport with sessionStorage persistence (defaults to null: mandatory Auth Portal on fresh launch)
  const [user, setUser] = useState<User | null>(() => {
    try {
      const saved = sessionStorage.getItem('aegis_auth_user');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  const [viewport, setViewport] = useState<Viewport>({
    center: [45.4642, 9.19],
    zoom: 13,
  });

  // Fetch conversations when user is logged in
  const fetchConversations = useCallback(async () => {
    if (!user) return;
    try {
      const res = await apiFetch(`/api/conversations?operator_id=${encodeURIComponent(user.username)}`);
      if (res.ok) {
        const data = await res.json();
        setConversations(data || []);
      }
    } catch (e) {
      console.error('Failed to fetch conversations:', e);
    }
  }, [user]);

  useEffect(() => {
    if (user) {
      fetchConversations();
    } else {
      setConversations([]);
      setActiveConversationId(null);
      setMessages([]);
      setActiveGeojson(null);
    }
  }, [user, fetchConversations]);

  // Load messages when active conversation changes
  const loadConversationMessages = async (id: string) => {
    setActiveConversationId(id);
    setAwaitingInput(false);
    try {
      const res = await apiFetch(`/api/conversations/${id}/messages`);
      if (res.ok) {
        const data = await res.json();
        const rawList = Array.isArray(data) ? data : (data.messages || []);
        const loadedMsgs: Message[] = rawList.map((m: any) => ({
          id: m.id || m.message_id,
          role: m.role,
          content: m.content,
          geojson: typeof m.geojson === 'object' && m.geojson !== null ? JSON.stringify(m.geojson) : m.geojson,
          created_at: m.created_at,
        }));
        setMessages(loadedMsgs);

        // Find last geojson to display on map
        const lastGeoMsg = [...loadedMsgs].reverse().find((m) => m.geojson);
        if (lastGeoMsg && lastGeoMsg.geojson) {
          setActiveGeojson(lastGeoMsg.geojson);
        } else {
          setActiveGeojson(null);
        }
      }
    } catch (e) {
      console.error('Failed to load conversation messages:', e);
    }
  };

  // Start new conversation
  const handleNewConversation = async () => {
    if (!user) return;
    try {
      const res = await apiFetch('/api/conversations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ operator_id: user.username, title: 'NUOVA CONVERSAZIONE' }),
      });
      if (res.ok) {
        const data = await res.json();
        setActiveConversationId(data.id);
        setMessages([]);
        setActiveGeojson(null);
        setAwaitingInput(false);
        fetchConversations();
      }
    } catch (e) {
      console.error('Failed to create new conversation:', e);
    }
  };

  // Handle SSE Streaming Message Send
  const handleSendMessage = async (text: string, imagePayload?: { dataUrl: string; name: string } | null) => {
    setIsLoading(true);

    let currentConvoId = activeConversationId;

    // Create new conversation if none active
    if (!currentConvoId && user) {
      try {
        const res = await apiFetch('/api/conversations', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ operator_id: user.username, title: 'NUOVA CONVERSAZIONE' }),
        });
        if (res.ok) {
          const data = await res.json();
          currentConvoId = data.id;
          setActiveConversationId(data.id);
        }
      } catch (e) {
        console.error('Auto conversation creation failed:', e);
      }
    }

    // Append User Message to UI
    const userMsg: Message = {
      role: 'user',
      content: awaitingInput ? `[RISPOSTA]: ${text}` : text,
      image_data: imagePayload?.dataUrl || null,
    };

    setMessages((prev) => [...prev, userMsg]);

    // Create Initial AI Placeholder Message with Thinking Steps
    const aiMsgId = `ai_${Date.now()}`;
    const aiMsg: Message = {
      id: aiMsgId,
      role: 'assistant',
      content: '',
      thinkingSteps: [],
      isThinking: true,
    };

    setMessages((prev) => [...prev, aiMsg]);

    // Build SSE Payload
    const payload = {
      message: awaitingInput ? '' : text,
      image_data: imagePayload ? imagePayload.dataUrl : null,
      image_name: imagePayload ? imagePayload.name : null,
      session_id: currentConvoId || 'anonymous',
      resume: awaitingInput ? text : null,
      viewport: viewport,
      conversation_id: currentConvoId,
    };

    setAwaitingInput(false);

    try {
      const baseUrl = getApiBaseUrl();
      const response = await fetch(`${baseUrl}/api/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            const trimmed = line.trim();
            if (trimmed.startsWith('data: ')) {
              try {
                const evt = JSON.parse(trimmed.substring(6));

                if (evt.type === 'status') {
                  const now = new Date();
                  const timeStr = `[${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}]`;
                  const icon = evt.step?.includes('tool') || evt.step?.includes('locate') ? '⚡' : evt.step?.includes('verific') ? '✓' : '⚙️';

                  const newStep: ThinkingStep = {
                    id: `${Date.now()}_${Math.random()}`,
                    timestamp: timeStr,
                    icon,
                    text: evt.step || 'Thinking step',
                    type: evt.type,
                  };

                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === aiMsgId
                        ? {
                            ...m,
                            thinkingSteps: [...(m.thinkingSteps || []), newStep],
                          }
                        : m
                    )
                  );
                } else if (evt.type === 'token') {
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === aiMsgId
                        ? {
                            ...m,
                            content: m.content + (evt.text || ''),
                          }
                        : m
                    )
                  );
                } else if (evt.type === 'final') {
                  const geoStr = typeof evt.geojson === 'object' && evt.geojson !== null ? JSON.stringify(evt.geojson) : (evt.geojson || null);
                  if (geoStr) {
                    setActiveGeojson(geoStr);
                  }
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === aiMsgId
                        ? {
                            ...m,
                            content: m.content || evt.text || '',
                            geojson: geoStr,
                            isThinking: false,
                            awaitingInput: evt.awaiting_input || false,
                          }
                        : m
                    )
                  );

                  if (evt.geojson) {
                    setActiveGeojson(evt.geojson);
                  }

                  if (evt.awaiting_input) {
                    setAwaitingInput(true);
                  }
                }
              } catch (parseErr) {
                console.error('SSE JSON parse error:', parseErr);
              }
            }
          }
        }
      }
    } catch (err: any) {
      console.error('Chat stream error:', err);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === aiMsgId
            ? {
                ...m,
                content: `SYSTEM_FAILURE: ${err.message || err}`,
                isThinking: false,
              }
            : m
        )
      );
    } finally {
      setIsLoading(false);
      fetchConversations();
    }
  };

  // Delete single conversation
  const handleDeleteConversation = async (id: string) => {
    try {
      const res = await apiFetch(`/api/conversations/${id}`, { method: 'DELETE' });
      if (res.ok) {
        if (activeConversationId === id) {
          setActiveConversationId(null);
          setMessages([]);
          setActiveGeojson(null);
        }
        fetchConversations();
      } else {
        console.error(`Delete conversation failed: ${res.status}`);
      }
    } catch (e) {
      console.error('Failed to delete conversation:', e);
    }
  };

  // Rename conversation
  const handleRenameConversation = async (id: string, newTitle: string) => {
    try {
      const res = await apiFetch(`/api/conversations/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: newTitle }),
      });
      if (res.ok) {
        fetchConversations();
      }
    } catch (e) {
      console.error('Failed to rename conversation:', e);
    }
  };

  // Clear all conversations
  const handleClearAll = async () => {
    if (!user) return;
    try {
      const res = await apiFetch(`/api/conversations?operator_id=${encodeURIComponent(user.username)}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        setActiveConversationId(null);
        setMessages([]);
        setActiveGeojson(null);
        fetchConversations();
      }
    } catch (e) {
      console.error('Failed to clear conversations:', e);
    }
  };

  // Login handler
  const handleLogin = async (operatorId: string, accessKey: string) => {
    const res = await apiFetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ operator_id: operatorId, access_key: accessKey }),
    });

    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.detail || 'Login failed');
    }

    const data = await res.json();
    const userData: User = {
      username: operatorId,
      clearance: data.clearance || 'OMEGA-9',
      token: data.token || 'SESSION_ACTIVE',
    };
    setUser(userData);
    try {
      sessionStorage.setItem('aegis_auth_user', JSON.stringify(userData));
      localStorage.removeItem('aegis_auth_user');
    } catch (e) {
      console.error('Failed to save auth to sessionStorage:', e);
    }
    fetchConversations();
  };

  const handleLogout = () => {
    try {
      sessionStorage.removeItem('aegis_auth_user');
      localStorage.removeItem('aegis_auth_user');
    } catch (e) {
      console.error('Failed to remove auth session:', e);
    }
    setUser(null);
    setConversations([]);
    setActiveConversationId(null);
    setMessages([]);
    setActiveGeojson(null);
  };

  // Time travel history fetch
  const handleOpenHistory = async () => {
    if (!activeConversationId) return;
    try {
      const res = await apiFetch(`/api/conversations/${activeConversationId}/history`);
      if (res.ok) {
        const data = await res.json();
        setCheckpoints(data.history || []);
        setHistoryOpen(true);
      }
    } catch (e) {
      console.error('Failed to load time travel history:', e);
    }
  };

  // Time travel rewind execute
  const handleRewind = async (checkpointId: string) => {
    if (!activeConversationId) return;
    try {
      const res = await apiFetch(`/api/conversations/${activeConversationId}/rewind`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ checkpoint_id: checkpointId }),
      });
      if (res.ok) {
        setHistoryOpen(false);
        loadConversationMessages(activeConversationId);
      }
    } catch (e) {
      console.error('Time travel rewind failed:', e);
    }
  };

  // Satellite scan execute
  const handleRunScan = async () => {
    setIsScanning(true);
    setScanResult(null);
    try {
      const res = await apiFetch('/api/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          viewport,
          operator_id: user?.username || 'OP_ADMIN',
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setScanResult(data.analysis || 'Satellite tile captured successfully.');
      } else {
        setScanResult('Scan failed. Ensure backend has Esri tile connectivity.');
      }
    } catch (e: any) {
      setScanResult(`Scan failure: ${e.message || e}`);
    } finally {
      setIsScanning(false);
    }
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-[#050505] text-[#f59e0b] font-mono select-none">
      {/* Auth Portal Overlay matching index.html when unauthenticated */}
      {!user && <AuthPortal onLoginSuccess={(u) => setUser(u)} />}

      {/* Navbar Header */}
      <Navbar
        user={user}
        onOpenScan={() => setScanOpen(true)}
        onOpenHistory={handleOpenHistory}
        onToggleThree={() => setShowThreeCanvas(!showThreeCanvas)}
        onLogout={handleLogout}
        onOpenLogin={() => setLoginOpen(true)}
        onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
      />

      {/* Palantir Foundry System Telemetry Ticker */}
      <div className="h-6 bg-[#0a0a0a] border-b border-[#f59e0b]/20 px-4 flex items-center justify-between text-[9px] font-mono text-[#f59e0b]/80 shrink-0 select-none">
        <div className="flex items-center space-x-4">
          <span className="flex items-center space-x-1">
            <span className="w-1.5 h-1.5 rounded-full bg-[#4ade80] animate-pulse" />
            <span className="font-bold">&gt; PALANTIR_ONTOLOGY: <span className="text-[#4ade80]">ACTIVE</span></span>
          </span>
          <span className="hidden sm:inline">&gt; DB: <span className="text-[#f59e0b] font-bold">POSTGIS schema1</span></span>
          <span className="hidden md:inline">&gt; ENGINE: <span className="text-[#f59e0b] font-bold">LANGGRAPH ReAct</span></span>
        </div>
        <div className="flex items-center space-x-4">
          <span className="hidden lg:inline">&gt; ENCRYPTION: <span className="text-[#4ade80] font-bold">AES-256-GCM</span></span>
          <span>&gt; LATENCY: <span className="text-[#4ade80] font-bold">14ms</span></span>
        </div>
      </div>

      {/* Main Workspace: Palantir Modular Tiling Panels */}
      <div className="flex flex-1 overflow-hidden relative p-1.5 gap-1.5 bg-[#050505]">
        {/* Navigation Sidebar: Palantir Ontology & Thread Explorer */}
        <Sidebar
          isOpen={sidebarOpen}
          conversations={conversations}
          activeConversationId={activeConversationId}
          onSelectConversation={loadConversationMessages}
          onNewConversation={handleNewConversation}
          onDeleteConversation={handleDeleteConversation}
          onRenameConversation={handleRenameConversation}
          onClearAll={handleClearAll}
        />

        {/* Center Panel: Palantir Intelligence Feed & ReAct Agent Log */}
        <div className="flex-1 flex flex-col min-w-0 bg-[#0a0a0a]/90 border border-[#f59e0b]/30 rounded-lg relative z-10 shadow-2xl overflow-hidden">
          <ChatContainer messages={messages} isLoading={isLoading} />
          <Composer
            onSendMessage={handleSendMessage}
            isLoading={isLoading}
            awaitingInput={awaitingInput}
          />
        </div>

        {/* Right Panel: Palantir Geospatial & 3D Intelligence Tile */}
        <div className="w-[48%] xl:w-[52%] h-full hidden md:block relative z-0 border border-[#f59e0b]/30 rounded-lg overflow-hidden bg-[#050505]">
          {showThreeCanvas ? (
            <ThreeCanvas onClose={() => setShowThreeCanvas(false)} />
          ) : (
            <MapView
              geojson={activeGeojson}
              viewport={viewport}
              onViewportChange={setViewport}
            />
          )}
        </div>
      </div>

      {/* Interactive Modals */}
      <TimeTravelModal
        isOpen={historyOpen}
        onClose={() => setHistoryOpen(false)}
        checkpoints={checkpoints}
        onRewind={handleRewind}
      />

      <SatScanModal
        isOpen={scanOpen}
        onClose={() => setScanOpen(false)}
        onRunScan={handleRunScan}
        isScanning={isScanning}
        scanResult={scanResult}
      />

      <LoginModal
        isOpen={loginOpen}
        onClose={() => setLoginOpen(false)}
        onLogin={handleLogin}
      />
    </div>
  );
};

export default App;
