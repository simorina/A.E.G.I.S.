import React, { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Shield, User as UserIcon, Terminal } from 'lucide-react';
import type { Message } from '../types';
import { ThinkingDropdown } from './ThinkingDropdown';
import { SkeletonLoader } from './SkeletonLoader';

interface ChatContainerProps {
  messages: Message[];
  isLoading: boolean;
}

export const ChatContainer: React.FC<ChatContainerProps> = ({ messages, isLoading }) => {
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  return (
    <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4 font-mono select-text bg-[#050505]/60 relative">
      {/* Empty State Welcome Terminal */}
      {messages.length === 0 && (
        <div className="h-full flex flex-col items-center justify-center text-center p-8 border border-[#f59e0b]/20 bg-black/40 rounded-2xl relative overflow-hidden my-auto">
          <div className="hud-corner top-left" />
          <div className="hud-corner top-right" />
          <div className="hud-corner bottom-left" />
          <div className="hud-corner bottom-right" />

          <div className="w-14 h-14 rounded-2xl bg-[#f59e0b]/10 border border-[#f59e0b]/40 flex items-center justify-center mb-4 shadow-[0_0_20px_rgba(245,158,11,0.2)]">
            <Terminal className="w-7 h-7 text-[#f59e0b]" />
          </div>
          <h2 className="text-sm font-bold tracking-widest text-[#f59e0b] uppercase glow-amber-text mb-2">
            A.E.G.I.S. // TACTICAL_GEOINT_CONSOLE
          </h2>
          <p className="text-xs text-[#f59e0b]/70 max-w-md leading-relaxed mb-4">
            AWAITING OPERATOR INTEL QUERY. TYPE COMMANDS SUCH AS <span className="text-[#4ade80]">'traccia via dante'</span> OR <span className="text-[#4ade80]">'ospedali vicino duomo'</span> TO EXECUTE POSTGIS / OVERPASS SPATIAL REASONING.
          </p>
          <div className="text-[9px] text-[#f59e0b]/50 tracking-[2px] uppercase">
            &gt; ENCRYPTION: AES-256-GCM · DB: POSTGIS SCHEMA1 · REASONING: REACT LANGGRAPH
          </div>
        </div>
      )}

      {/* Message Timeline */}
      <AnimatePresence initial={false}>
        {messages.map((msg, index) => {
          const isUser = msg.role === 'user';
          return (
            <motion.div
              key={msg.id || index}
              initial={{ opacity: 0, y: 12, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ duration: 0.2, ease: 'easeOut' }}
              className={`flex flex-col space-y-2 max-w-[90%] md:max-w-[85%] ${
                isUser ? 'ml-auto items-end' : 'mr-auto items-start'
              }`}
            >
              {/* Message Header Tag */}
              <div className="flex items-center space-x-2 text-[10px] tracking-wider uppercase opacity-80">
                {isUser ? (
                  <>
                    <span className="text-[#4ade80] font-bold">&gt; OPERATOR_TELEMETRY_LOG</span>
                    <div className="w-5 h-5 rounded bg-[#4ade80]/15 border border-[#4ade80]/40 flex items-center justify-center">
                      <UserIcon className="w-3 h-3 text-[#4ade80]" />
                    </div>
                  </>
                ) : (
                  <>
                    <div className="w-5 h-5 rounded bg-[#f59e0b]/15 border border-[#f59e0b]/40 flex items-center justify-center shadow-[0_0_8px_rgba(245,158,11,0.3)]">
                      <Shield className="w-3 h-3 text-[#f59e0b]" />
                    </div>
                    <span className="text-[#f59e0b] font-bold">&gt; AI_INTEL_BRIEFING</span>
                  </>
                )}
              </div>

              {/* Message Body Card */}
              <div
                className={`p-4 rounded-xl text-xs leading-relaxed border backdrop-blur-md relative ${
                  isUser
                    ? 'bg-black/60 border-[#4ade80]/40 border-l-4 border-l-[#4ade80] text-[#4ade80] shadow-[0_0_15px_rgba(74,222,128,0.15)]'
                    : 'bg-[#0a0a0a]/90 border-[#f59e0b]/30 border-l-4 border-l-[#f59e0b] text-[#f59e0b] shadow-[0_0_20px_rgba(245,158,11,0.15)]'
                }`}
              >
                {/* Optional Attached Image */}
                {msg.image_data && (
                  <div className="mb-3 rounded border border-[#f59e0b]/30 overflow-hidden max-w-xs">
                    <img src={msg.image_data} alt="Attached optical intel" className="w-full h-auto object-cover" />
                  </div>
                )}

                {/* Thinking Process Accordion */}
                {!isUser && (msg.thinkingSteps || msg.isThinking) && (
                  <div className="mb-3">
                    <ThinkingDropdown steps={msg.thinkingSteps} isThinking={msg.isThinking} />
                  </div>
                )}

                {/* Text Content */}
                {msg.content ? (
                  <div className="whitespace-pre-wrap font-mono">{msg.content}</div>
                ) : (
                  !isUser && msg.isThinking && (
                    <div className="text-[11px] text-[#f59e0b]/70 italic flex items-center space-x-2">
                      <span className="w-2 h-2 rounded-full bg-[#f59e0b] animate-ping" />
                      <span>Esecuzione ragionamento spaziale in corso...</span>
                    </div>
                  )
                )}
              </div>
            </motion.div>
          );
        })}
      </AnimatePresence>

      {/* Loading Skeleton Loader */}
      {isLoading && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mr-auto w-full max-w-lg"
        >
          <SkeletonLoader mode="thinking" />
        </motion.div>
      )}
    </div>
  );
};
