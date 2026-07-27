import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, MessageSquare, Trash2, Search, Edit2, Check, X } from 'lucide-react';
import type { Conversation } from '../types';

interface SidebarProps {
  isOpen: boolean;
  conversations: Conversation[];
  activeConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onNewConversation: () => void;
  onDeleteConversation: (id: string) => void;
  onRenameConversation: (id: string, newTitle: string) => void;
  onClearAll: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  isOpen,
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  onRenameConversation,
  onClearAll,
}) => {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');

  const filteredConversations = conversations.filter((c) =>
    (c.title || `MISSION_${c.id.substring(0, 6)}`)
      .toLowerCase()
      .includes(searchQuery.toLowerCase())
  );

  const startEditing = (c: Conversation, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(c.id);
    setEditTitle(c.title || `MISSION_${c.id.substring(0, 6)}`);
  };

  const saveEditing = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (editTitle.trim()) {
      onRenameConversation(id, editTitle.trim());
    }
    setEditingId(null);
  };

  const cancelEditing = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(null);
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.aside
          initial={{ width: 0, opacity: 0 }}
          animate={{ width: 280, opacity: 1 }}
          exit={{ width: 0, opacity: 0 }}
          transition={{ duration: 0.25, ease: 'easeInOut' }}
          className="h-full bg-[#0a0a0a]/95 border-r border-[#f59e0b]/30 flex flex-col z-20 shrink-0 font-mono select-none backdrop-blur-md relative"
        >
          {/* Top Mission Header */}
          <div className="p-3.5 border-b border-[#f59e0b]/20 space-y-3">
            <div className="border-l-4 border-l-[#f59e0b] pl-2.5 flex items-center justify-between">
              <div>
                <h2 className="text-xs font-bold tracking-widest text-[#f59e0b] uppercase glow-amber-text">
                  &gt; MISSION_LOG_v8.4
                </h2>
                <div className="text-[8px] tracking-[2px] opacity-70 text-[#f59e0b] uppercase">
                  ACTIVE OPERATIONAL THREADS
                </div>
              </div>
              <span className="text-[9px] px-1.5 py-0.5 rounded bg-[#f59e0b]/15 text-[#4ade80] border border-[#f59e0b]/30 font-bold">
                {conversations.length} SECURED
              </span>
            </div>

            <button
              onClick={onNewConversation}
              className="w-full py-2 px-3 rounded bg-black/60 border border-[#f59e0b] text-[#f59e0b] hover:bg-[#f59e0b] hover:text-black font-bold text-xs uppercase tracking-widest transition-all shadow-[0_0_10px_rgba(245,158,11,0.2)] flex items-center justify-center space-x-2 group cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5 group-hover:scale-125 transition-transform" />
              <span>INITIALIZE_MISSION</span>
            </button>

            {/* Search Filter Box */}
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-[#f59e0b]/50 absolute left-2.5 top-2.5" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="FILTER MISSIONS..."
                className="w-full bg-black/40 border border-[#f59e0b]/30 border-l-2 border-l-[#f59e0b] rounded pl-8 pr-2 py-1.5 text-[11px] text-[#f59e0b] placeholder-[#f59e0b]/40 outline-none focus:border-[#f59e0b] focus:shadow-[0_0_10px_rgba(245,158,11,0.2)] transition-all font-mono"
              />
            </div>
          </div>

          {/* Conversations List */}
          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {filteredConversations.length === 0 ? (
              <div className="p-4 text-center text-[10px] text-[#f59e0b]/50 tracking-wider">
                &gt; NO ACTIVE THREADS FOUND
              </div>
            ) : (
              filteredConversations.map((c) => {
                const isActive = c.id === activeConversationId;
                return (
                  <div
                    key={c.id}
                    onClick={() => onSelectConversation(c.id)}
                    className={`group relative p-2.5 rounded border transition-all cursor-pointer flex items-center justify-between text-xs ${
                      isActive
                        ? 'bg-[#f59e0b]/15 border-[#f59e0b] border-l-4 border-l-[#f59e0b] text-[#f59e0b] shadow-[0_0_15px_rgba(245,158,11,0.2)] font-bold'
                        : 'bg-black/30 border-[#f59e0b]/20 text-[#f59e0b]/80 hover:border-[#f59e0b]/60 hover:text-[#f59e0b] hover:bg-black/60'
                    }`}
                  >
                    <div className="flex items-center space-x-2 min-w-0 flex-1 pr-2">
                      <MessageSquare className={`w-3.5 h-3.5 shrink-0 ${isActive ? 'text-[#4ade80]' : 'text-[#f59e0b]/60'}`} />

                      {editingId === c.id ? (
                        <input
                          type="text"
                          value={editTitle}
                          onChange={(e) => setEditTitle(e.target.value)}
                          onClick={(e) => e.stopPropagation()}
                          className="w-full bg-black border border-[#f59e0b] text-[11px] text-[#f59e0b] px-1 py-0.5 outline-none font-mono"
                          autoFocus
                        />
                      ) : (
                        <span className="truncate text-[11px] tracking-wider uppercase">
                          {c.title || `MISSION_${c.id.substring(0, 6)}`}
                        </span>
                      )}
                    </div>

                    {/* Inline Action Buttons */}
                    <div className="flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      {editingId === c.id ? (
                        <>
                          <button
                            onClick={(e) => saveEditing(c.id, e)}
                            className="p-1 text-[#4ade80] hover:text-white"
                          >
                            <Check className="w-3 h-3" />
                          </button>
                          <button
                            onClick={cancelEditing}
                            className="p-1 text-red-400 hover:text-white"
                          >
                            <X className="w-3 h-3" />
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            onClick={(e) => startEditing(c, e)}
                            className="p-1 text-[#f59e0b]/70 hover:text-[#f59e0b]"
                            title="Rename Mission"
                          >
                            <Edit2 className="w-3 h-3" />
                          </button>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              e.preventDefault();
                              onDeleteConversation(c.id);
                            }}
                            className="p-1 rounded text-[#f59e0b]/70 hover:text-red-400 hover:bg-red-500/20 transition-all z-10"
                            title="Delete Mission Thread"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Bottom Control & Status Bar */}
          <div className="p-3 border-t border-[#f59e0b]/20 bg-black/60 flex items-center justify-between text-[9px] text-[#f59e0b]/70">
            <span>&gt; UPLINK: <span className="text-[#4ade80] font-bold">ONLINE</span></span>
            {conversations.length > 0 && (
              <button
                onClick={onClearAll}
                className="hover:text-red-400 font-bold uppercase transition-colors"
              >
                CLEAR_ALL
              </button>
            )}
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
};
