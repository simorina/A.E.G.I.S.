import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, CheckCircle2, Zap } from 'lucide-react';
import type { ThinkingStep } from '../types';

interface ThinkingDropdownProps {
  steps?: ThinkingStep[];
  isThinking?: boolean;
}

export const ThinkingDropdown: React.FC<ThinkingDropdownProps> = ({
  steps = [],
  isThinking = false,
}) => {
  const [isOpen, setIsOpen] = useState<boolean>(isThinking);

  const stepCount = steps.length;

  return (
    <div className="rounded bg-black/60 border border-[#f59e0b]/30 border-l-2 border-l-[#f59e0b] overflow-hidden text-xs font-mono select-none">
      {/* Accordion Toggle Header */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-3 py-2 flex items-center justify-between bg-[#f59e0b]/10 hover:bg-[#f59e0b]/20 transition-colors text-left"
      >
        <div className="flex items-center space-x-2">
          {isThinking ? (
            <Zap className="w-3.5 h-3.5 text-[#f59e0b] animate-pulse" />
          ) : (
            <CheckCircle2 className="w-3.5 h-3.5 text-[#4ade80]" />
          )}
          <span className="font-bold tracking-wider text-[#f59e0b] uppercase">
            {isThinking ? `⚡ TACTICAL_THINKING_STREAM (${stepCount} STEPS)` : `✓ THINKING_PROCESS_COMPLETED (${stepCount} STEPS)`}
          </span>
        </div>

        <div className="flex items-center space-x-2 text-[#f59e0b]/70">
          <span className="text-[9px] uppercase tracking-widest">{isOpen ? 'COLLAPSE' : 'EXPAND'}</span>
          <motion.div animate={{ rotate: isOpen ? 180 : 0 }} transition={{ duration: 0.2 }}>
            <ChevronDown className="w-3.5 h-3.5 text-[#f59e0b]" />
          </motion.div>
        </div>
      </button>

      {/* Accordion Content Body */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="border-t border-[#f59e0b]/20 p-3 space-y-1.5 bg-black/80 text-[11px] max-h-60 overflow-y-auto"
          >
            {steps.length === 0 ? (
              <div className="text-[#f59e0b]/50 italic text-[10px]">
                &gt; INITIALIZING REASONING NODES...
              </div>
            ) : (
              steps.map((step, idx) => (
                <div key={idx} className="flex items-start space-x-2 text-[#f59e0b]/90 leading-tight">
                  <span className="text-[#f59e0b]/50 text-[9px] shrink-0">[{step.timestamp}]</span>
                  <span className="shrink-0">{step.icon || '⚙️'}</span>
                  <span className="font-mono">{step.text}</span>
                </div>
              ))
            )}

            {isThinking && (
              <div className="flex items-center space-x-2 text-[#f59e0b] text-[10px] pt-1">
                <span className="w-1.5 h-1.5 rounded-full bg-[#f59e0b] animate-ping" />
                <span className="italic">&gt; PROCESSING MULTI-STEP TOOL REASONING...</span>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
