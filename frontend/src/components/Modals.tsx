import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, History, Scan, User, Lock, RotateCcw, AlertTriangle, ShieldCheck } from 'lucide-react';
import type { Checkpoint } from '../types';

// Time Travel Checkpoint Timeline Modal
interface TimeTravelModalProps {
  isOpen: boolean;
  onClose: () => void;
  checkpoints: Checkpoint[];
  onRewind: (checkpointId: string) => void;
}

export const TimeTravelModal: React.FC<TimeTravelModalProps> = ({
  isOpen,
  onClose,
  checkpoints,
  onRewind,
}) => {
  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md font-mono select-none">
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            className="w-full max-w-xl bg-[#0a0a0a] border border-[#f59e0b]/40 rounded-xl p-5 shadow-[0_0_50px_rgba(0,0,0,0.9)] space-y-4 relative"
          >
            <div className="hud-corner top-left" />
            <div className="hud-corner top-right" />
            <div className="hud-corner bottom-left" />
            <div className="hud-corner bottom-right" />

            <div className="flex items-center justify-between border-b border-[#f59e0b]/20 pb-3">
              <div className="flex items-center space-x-2 text-[#f59e0b] font-bold text-xs uppercase tracking-widest border-l-4 border-l-[#f59e0b] pl-2.5">
                <History className="w-4 h-4 text-[#f59e0b]" />
                <span>TIME-TRAVEL STATE REWIND</span>
              </div>
              <button onClick={onClose} className="p-1 rounded bg-black border border-[#f59e0b]/30 hover:border-[#f59e0b] text-[#f59e0b]">
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-[11px] text-[#f59e0b]/80">
              Select a historic checkpoint state to rewind the agent's LangGraph graph memory.
            </p>

            <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
              {checkpoints.length === 0 ? (
                <div className="py-6 text-center text-[#f59e0b]/50 text-xs">
                  &gt; NO PREVIOUS CHECKPOINTS RECORDED
                </div>
              ) : (
                checkpoints.map((cp) => (
                  <div
                    key={cp.checkpoint_id}
                    className="flex items-center justify-between p-3 rounded bg-black/60 border border-[#f59e0b]/30 border-l-2 border-l-[#f59e0b] hover:border-[#f59e0b] transition-colors text-xs"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center space-x-2 text-[#f59e0b] font-bold">
                        <span className="px-1.5 py-0.5 rounded bg-[#f59e0b]/20 text-[10px] text-[#4ade80]">STEP {cp.step}</span>
                        <span>{cp.node || 'NODE'}</span>
                      </div>
                      <p className="text-[10px] text-[#f59e0b]/70">{cp.summary || cp.timestamp}</p>
                    </div>

                    <button
                      onClick={() => onRewind(cp.checkpoint_id)}
                      className="flex items-center space-x-1 py-1.5 px-3 rounded bg-[#f59e0b] hover:bg-amber-400 text-black text-xs font-bold transition-all shadow-[0_0_10px_#f59e0b]"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                      <span>REWIND</span>
                    </button>
                  </div>
                ))
              )}
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};

// Satellite Optical Scan Modal
interface SatScanModalProps {
  isOpen: boolean;
  onClose: () => void;
  onRunScan: () => void;
  isScanning: boolean;
  scanResult: string | null;
}

export const SatScanModal: React.FC<SatScanModalProps> = ({
  isOpen,
  onClose,
  onRunScan,
  isScanning,
  scanResult,
}) => {
  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md font-mono select-none">
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            className="w-full max-w-lg bg-[#0a0a0a] border border-[#f59e0b]/40 rounded-xl p-5 shadow-[0_0_50px_rgba(0,0,0,0.9)] space-y-4 relative"
          >
            <div className="hud-corner top-left" />
            <div className="hud-corner top-right" />
            <div className="hud-corner bottom-left" />
            <div className="hud-corner bottom-right" />

            <div className="flex items-center justify-between border-b border-[#f59e0b]/20 pb-3">
              <div className="flex items-center space-x-2 text-[#f59e0b] font-bold text-xs uppercase tracking-widest border-l-4 border-l-[#f59e0b] pl-2.5">
                <Scan className="w-4 h-4 text-[#f59e0b]" />
                <span>SATELLITE RECONNAISSANCE SCAN (/api/scan)</span>
              </div>
              <button onClick={onClose} className="p-1 rounded bg-black border border-[#f59e0b]/30 hover:border-[#f59e0b] text-[#f59e0b]">
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-[11px] text-[#f59e0b]/80">
              Captures real-time Esri World Imagery optical tiles for current map viewport bounds and performs vision LLM multispectral feature extraction.
            </p>

            <button
              onClick={onRunScan}
              disabled={isScanning}
              className="w-full py-3 rounded bg-[#f59e0b] hover:bg-amber-400 text-black font-bold text-xs uppercase tracking-widest shadow-[0_0_15px_#f59e0b] disabled:opacity-50 transition-all flex items-center justify-center space-x-2"
            >
              <Scan className={`w-4 h-4 ${isScanning ? 'animate-spin' : ''}`} />
              <span>{isScanning ? 'CAPTURING SATELLITE TILE...' : 'EXECUTE OPTICAL SCAN'}</span>
            </button>

            {scanResult && (
              <div className="p-3.5 rounded bg-black/60 border border-[#f59e0b]/30 border-l-2 border-l-[#f59e0b] text-xs font-mono text-[#f59e0b] whitespace-pre-wrap max-h-56 overflow-y-auto">
                {scanResult}
              </div>
            )}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};

// Operator Authentication Login Modal
interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLogin: (operatorId: string, accessKey: string) => Promise<void>;
}

export const LoginModal: React.FC<LoginModalProps> = ({ isOpen, onClose, onLogin }) => {
  const [operatorId, setOperatorId] = useState<string>('OP_ADMIN');
  const [accessKey, setAccessKey] = useState<string>('aegis2026');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await onLogin(operatorId, accessKey);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Authentication failed. Check credentials.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md font-mono select-none">
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            className="w-full max-w-sm bg-[#0a0a0a] border border-[#f59e0b]/50 rounded-xl p-6 shadow-[0_0_50px_rgba(0,0,0,0.9)] space-y-4 relative"
          >
            <div className="hud-corner top-left" />
            <div className="hud-corner top-right" />
            <div className="hud-corner bottom-left" />
            <div className="hud-corner bottom-right" />

            <div className="flex items-center justify-between border-b border-[#f59e0b]/20 pb-3">
              <div className="flex items-center space-x-2 text-[#f59e0b] font-bold text-xs uppercase tracking-widest border-l-4 border-l-[#f59e0b] pl-2.5">
                <ShieldCheck className="w-5 h-5 text-[#f59e0b]" />
                <span>OPERATOR CLEARANCE AUTH</span>
              </div>
              <button onClick={onClose} className="p-1 rounded bg-black border border-[#f59e0b]/30 text-[#f59e0b]">
                <X className="w-4 h-4" />
              </button>
            </div>

            {error && (
              <div className="p-2.5 rounded bg-red-500/15 border border-red-500/40 text-red-300 text-xs flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4 text-xs">
              <div className="space-y-1">
                <label className="block text-[#f59e0b] uppercase tracking-wider text-[10px]">OPERATOR ID / USERNAME</label>
                <div className="relative">
                  <User className="w-3.5 h-3.5 text-[#f59e0b]/60 absolute left-3 top-3" />
                  <input
                    type="text"
                    value={operatorId}
                    onChange={(e) => setOperatorId(e.target.value)}
                    required
                    className="w-full bg-black/40 border border-[#f59e0b]/30 border-l-2 border-l-[#f59e0b] rounded pl-9 pr-3 py-2 text-[#f59e0b] outline-none focus:border-[#f59e0b] focus:shadow-[0_0_10px_rgba(245,158,11,0.2)] font-mono"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="block text-[#f59e0b] uppercase tracking-wider text-[10px]">ACCESS KEY / PASSWORD</label>
                <div className="relative">
                  <Lock className="w-3.5 h-3.5 text-[#f59e0b]/60 absolute left-3 top-3" />
                  <input
                    type="password"
                    value={accessKey}
                    onChange={(e) => setAccessKey(e.target.value)}
                    required
                    className="w-full bg-black/40 border border-[#f59e0b]/30 border-l-2 border-l-[#f59e0b] rounded pl-9 pr-3 py-2 text-[#f59e0b] outline-none focus:border-[#f59e0b] focus:shadow-[0_0_10px_rgba(245,158,11,0.2)] font-mono"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full py-3 rounded bg-[#f59e0b] hover:bg-amber-400 text-black font-bold text-xs uppercase tracking-widest shadow-[0_0_15px_#f59e0b] disabled:opacity-50 transition-all"
              >
                {isSubmitting ? 'VERIFYING BCYPT HASH...' : 'AUTHENTICATE ACCESS'}
              </button>
            </form>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};
