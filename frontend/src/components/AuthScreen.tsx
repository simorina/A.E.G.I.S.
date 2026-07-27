import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Shield, Lock, User, KeyRound, AlertTriangle, Cpu, Radio } from 'lucide-react';
import type { User as UserType } from '../types';

interface AuthScreenProps {
  onLogin: (operatorId: string, accessKey: string) => Promise<void>;
  user: UserType | null;
}

export const AuthScreen: React.FC<AuthScreenProps> = ({ onLogin, user }) => {
  const [operatorId, setOperatorId] = useState<string>('OP_ADMIN');
  const [accessKey, setAccessKey] = useState<string>('aegis2026');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const presets = [
    { id: 'OP_ADMIN', key: 'aegis2026', rank: 'SIGMA-7', role: 'System Administrator' },
    { id: 'CMD_USR_0001', key: 'tango-down', rank: 'OMEGA-9', role: 'Field Commander' },
    { id: 'CMD_USR_0042', key: 'falcon99', rank: 'ALPHA-3', role: 'Tactical Analyst' },
  ];

  const handleSelectPreset = (p: typeof presets[0]) => {
    setOperatorId(p.id);
    setAccessKey(p.key);
    setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await onLogin(operatorId, accessKey);
    } catch (err: any) {
      setError(err.message || 'Authentication failed. Invalid operator credentials.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (user) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/95 backdrop-blur-xl">
        {/* Animated Background Hex Grid Pattern */}
        <div className="absolute inset-0 bg-[radial-gradient(#d97706_1px,transparent_1px)] [background-size:24px_24px] opacity-10 pointer-events-none" />

        <motion.div
          initial={{ opacity: 0, scale: 0.92, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.92, y: 20 }}
          transition={{ duration: 0.3, ease: 'easeOut' }}
          className="w-full max-w-md bg-slate-900/90 border border-amber-500/40 rounded-3xl p-7 shadow-2xl space-y-6 relative overflow-hidden glass-panel"
        >
          {/* Top Tactical Banner */}
          <div className="flex flex-col items-center text-center space-y-2 border-b border-amber-500/20 pb-5">
            <div className="w-14 h-14 rounded-2xl bg-amber-500/15 border border-amber-500/40 flex items-center justify-center shadow-lg shadow-amber-500/20">
              <Shield className="w-7 h-7 text-amber-400" />
            </div>
            <div>
              <h1 className="text-lg font-bold font-mono text-amber-400 tracking-wider glow-amber-text flex items-center justify-center gap-2">
                A.E.G.I.S. GEOINT
                <span className="text-[10px] px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-normal border border-amber-500/40">
                  AUTH 2.0
                </span>
              </h1>
              <p className="text-xs font-mono text-slate-400 mt-1">
                RESTRICTED ACCESS · BCRYPT PASSWORD VERIFICATION
              </p>
            </div>
          </div>

          {/* Quick Preset Operator Selector */}
          <div className="space-y-1.5 font-mono text-xs">
            <label className="block text-[10px] uppercase text-slate-400 font-semibold tracking-wider">
              SELECT PRESET OPERATOR CREDENTIALS:
            </label>
            <div className="grid grid-cols-3 gap-2">
              {presets.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => handleSelectPreset(p)}
                  className={`p-2 rounded-xl border text-left transition-all ${
                    operatorId === p.id
                      ? 'bg-amber-500/20 border-amber-500 text-amber-300 shadow-md shadow-amber-500/10'
                      : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:border-slate-700 hover:text-slate-200'
                  }`}
                >
                  <div className="font-bold truncate text-[11px]">{p.id}</div>
                  <div className="text-[9px] text-amber-400/80">{p.rank}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <motion.div 
              initial={{ opacity: 0, y: -5 }}
              animate={{ opacity: 1, y: 0 }}
              className="p-3 rounded-xl bg-red-500/15 border border-red-500/40 text-red-300 text-xs font-mono flex items-center space-x-2.5"
            >
              <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
              <span>{error}</span>
            </motion.div>
          )}

          {/* Login Form */}
          <form onSubmit={handleSubmit} className="space-y-4 font-mono text-xs">
            <div className="space-y-1">
              <label className="block text-slate-300 text-[11px]">OPERATOR USERNAME</label>
              <div className="relative">
                <User className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
                <input
                  type="text"
                  value={operatorId}
                  onChange={(e) => setOperatorId(e.target.value)}
                  required
                  placeholder="e.g. OP_ADMIN"
                  className="w-full bg-slate-950 border border-slate-700/80 rounded-xl pl-9 pr-3 py-2.5 text-slate-100 placeholder-slate-600 focus:outline-none focus:border-amber-500/70 transition-colors"
                />
              </div>
            </div>

            <div className="space-y-1">
              <label className="block text-slate-300 text-[11px]">ACCESS KEY / PASSWORD</label>
              <div className="relative">
                <KeyRound className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
                <input
                  type="password"
                  value={accessKey}
                  onChange={(e) => setAccessKey(e.target.value)}
                  required
                  placeholder="••••••••"
                  className="w-full bg-slate-950 border border-slate-700/80 rounded-xl pl-9 pr-3 py-2.5 text-slate-100 placeholder-slate-600 focus:outline-none focus:border-amber-500/70 transition-colors"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full py-3 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 font-bold text-xs font-mono transition-all shadow-lg shadow-amber-500/25 disabled:opacity-50 flex items-center justify-center space-x-2 group"
            >
              {isSubmitting ? (
                <>
                  <Cpu className="w-4 h-4 animate-spin text-slate-950" />
                  <span>VERIFYING BCYPT HASH...</span>
                </>
              ) : (
                <>
                  <Lock className="w-4 h-4 text-slate-950 group-hover:scale-110 transition-transform" />
                  <span>AUTHENTICATE OPERATOR SESSION</span>
                </>
              )}
            </button>
          </form>

          {/* Footer Security Notice */}
          <div className="pt-2 text-center text-[10px] font-mono text-slate-500 border-t border-slate-800/80 flex items-center justify-center space-x-1.5">
            <Radio className="w-3 h-3 text-emerald-400 animate-pulse" />
            <span>SECURE TERMINAL · POSTGRES POSTGIS SCHEMA1</span>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};
