import React from 'react';
import { motion } from 'framer-motion';
import { Cpu, ShieldAlert } from 'lucide-react';

interface SkeletonLoaderProps {
  type?: 'thinking' | 'chat' | 'scan';
  mode?: 'thinking' | 'chat' | 'scan';
}

export const SkeletonLoader: React.FC<SkeletonLoaderProps> = ({ type, mode }) => {
  const activeType = mode || type || 'chat';

  if (activeType === 'thinking') {
    return (
      <motion.div 
        initial={{ opacity: 0, y: 5 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full bg-[#0a0a0a]/90 border border-[#f59e0b]/40 border-l-4 border-l-[#f59e0b] rounded-lg p-3 my-2 shadow-[0_0_20px_rgba(245,158,11,0.15)] overflow-hidden relative font-mono"
      >
        <div className="flex items-center space-x-2 border-b border-[#f59e0b]/20 pb-2 mb-2">
          <Cpu className="w-4 h-4 text-[#f59e0b] animate-spin" />
          <div className="h-3 w-36 bg-[#f59e0b]/20 rounded relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-[#f59e0b]/40 to-transparent animate-shimmer" />
          </div>
          <span className="text-[10px] text-[#f59e0b] font-bold ml-auto uppercase tracking-wider">&gt; COMPUTING_SPATIAL_INTEL...</span>
        </div>
        
        <div className="space-y-2 py-1">
          <div className="h-2.5 w-3/4 bg-black/60 rounded relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-[#f59e0b]/30 to-transparent animate-shimmer" />
          </div>
          <div className="h-2.5 w-1/2 bg-black/40 rounded relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-[#f59e0b]/30 to-transparent animate-shimmer" />
          </div>
        </div>
      </motion.div>
    );
  }

  if (activeType === 'scan') {
    return (
      <div className="flex flex-col items-center justify-center p-8 space-y-4 text-center font-mono">
        <ShieldAlert className="w-12 h-12 text-[#f59e0b] animate-pulse" />
        <div className="space-y-2 w-full max-w-xs">
          <div className="h-4 bg-black border border-[#f59e0b]/30 rounded w-full relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-[#f59e0b]/40 to-transparent animate-shimmer" />
          </div>
          <div className="h-3 bg-black/60 rounded w-2/3 mx-auto relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-[#f59e0b]/40 to-transparent animate-shimmer" />
          </div>
        </div>
        <p className="text-xs text-[#f59e0b] font-bold tracking-wider">&gt; CAPTURING SATELLITE OPTICAL TILE...</p>
      </div>
    );
  }

  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex space-x-3 p-4 my-2 rounded-xl bg-[#0a0a0a]/90 border border-[#f59e0b]/30 border-l-4 border-l-[#f59e0b] font-mono"
    >
      <div className="w-8 h-8 rounded bg-[#f59e0b]/20 border border-[#f59e0b]/40 flex items-center justify-center shrink-0">
        <Cpu className="w-4 h-4 text-[#f59e0b] animate-pulse" />
      </div>
      <div className="space-y-2 flex-1 pt-1">
        <div className="h-3 bg-black rounded w-1/4 relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-[#f59e0b]/30 to-transparent animate-shimmer" />
        </div>
        <div className="h-3 bg-black/80 rounded w-full relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-[#f59e0b]/30 to-transparent animate-shimmer" />
        </div>
        <div className="h-3 bg-black/60 rounded w-4/5 relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-[#f59e0b]/30 to-transparent animate-shimmer" />
        </div>
      </div>
    </motion.div>
  );
};
