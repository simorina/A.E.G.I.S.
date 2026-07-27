import React from 'react';
import { Shield, Radio, Scan, History, User, LogOut, Box } from 'lucide-react';
import type { User as UserType } from '../types';

interface NavbarProps {
  user: UserType | null;
  onOpenScan: () => void;
  onOpenHistory: () => void;
  onToggleThree: () => void;
  onLogout: () => void;
  onOpenLogin: () => void;
  onToggleSidebar: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  user,
  onOpenScan,
  onOpenHistory,
  onToggleThree,
  onLogout,
  onOpenLogin,
  onToggleSidebar,
}) => {
  return (
    <header className="h-14 bg-[#0a0a0a]/95 border-b border-[#f59e0b]/30 px-4 flex items-center justify-between z-30 shrink-0 backdrop-blur-md font-mono select-none">
      {/* Left section: Tactical Brand & Sidebar Toggle */}
      <div className="flex items-center space-x-3">
        <button
          onClick={onToggleSidebar}
          className="p-1.5 rounded bg-black/60 border border-[#f59e0b]/30 hover:border-[#f59e0b] text-[#f59e0b] hover:shadow-[0_0_10px_#f59e0b] transition-all"
          title="Toggle Mission Navigation Sidebar"
        >
          <Radio className="w-4 h-4 text-[#f59e0b] animate-pulse" />
        </button>

        <div className="border-l-4 border-l-[#f59e0b] pl-3 flex flex-col justify-center">
          <div className="flex items-center space-x-2">
            <Shield className="w-4 h-4 text-[#f59e0b] drop-shadow-[0_0_6px_#f59e0b]" />
            <h1 className="text-xs font-bold tracking-widest text-[#f59e0b] uppercase glow-amber-text flex items-center gap-2">
              A.E.G.I.S. <span className="text-[9px] px-1.5 py-0.5 rounded bg-[#f59e0b]/15 text-[#f59e0b] border border-[#f59e0b]/40">INTEL_CORE_v8.4</span>
            </h1>
          </div>
          <span className="text-[8px] tracking-[2px] opacity-70 text-[#f59e0b] uppercase hidden sm:block">
            AUTHORIZED PERSONNEL ONLY // CLASS_A
          </span>
        </div>
      </div>

      {/* Middle section: Tactical Quick Action Buttons */}
      <div className="flex items-center space-x-2">
        <button
          onClick={onToggleThree}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded bg-black/50 border border-[#f59e0b]/40 hover:bg-[#f59e0b] hover:text-black hover:shadow-[0_0_15px_#f59e0b] text-[11px] font-bold text-[#f59e0b] transition-all uppercase tracking-wider group"
        >
          <Box className="w-3.5 h-3.5 text-[#f59e0b] group-hover:text-black group-hover:rotate-180 transition-transform" />
          <span className="hidden md:inline">3D_CANVAS</span>
        </button>

        <button
          onClick={onOpenScan}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded bg-black/50 border border-[#f59e0b]/40 hover:bg-[#f59e0b] hover:text-black hover:shadow-[0_0_15px_#f59e0b] text-[11px] font-bold text-[#f59e0b] transition-all uppercase tracking-wider group"
        >
          <Scan className="w-3.5 h-3.5 text-[#f59e0b] group-hover:text-black group-hover:rotate-90 transition-transform" />
          <span className="hidden md:inline">SAT_RECON</span>
        </button>

        <button
          onClick={onOpenHistory}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded bg-black/50 border border-[#f59e0b]/40 hover:bg-[#f59e0b] hover:text-black hover:shadow-[0_0_15px_#f59e0b] text-[11px] font-bold text-[#f59e0b] transition-all uppercase tracking-wider"
        >
          <History className="w-3.5 h-3.5 text-[#f59e0b] group-hover:text-black" />
          <span className="hidden md:inline">TIME_TRAVEL</span>
        </button>
      </div>

      {/* Right section: Operator Data Stream Badge & Logout */}
      <div className="flex items-center space-x-3">
        {user ? (
          <div className="flex items-center space-x-2">
            <div className="px-2.5 py-1 rounded bg-black/60 border border-[#f59e0b]/30 text-[10px] text-[#f59e0b] flex items-center space-x-2">
              <span className="w-1.5 h-1.5 rounded-full bg-[#4ade80] animate-pulse" />
              <span className="font-bold tracking-wider">&gt; {user.username}</span>
              <span className="text-[9px] text-[#4ade80] border-l border-[#f59e0b]/30 pl-1.5 font-bold">[{user.clearance}]</span>
            </div>
            <button
              onClick={onLogout}
              className="p-1.5 rounded bg-black/60 border border-[#f59e0b]/30 hover:border-red-500 hover:bg-red-500/20 text-[#f59e0b] hover:text-red-400 hover:shadow-[0_0_10px_#ef4444] transition-all"
              title="Terminate Operator Session"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        ) : (
          <button
            onClick={onOpenLogin}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded bg-[#f59e0b] hover:bg-amber-400 text-black font-bold text-xs transition-all shadow-[0_0_15px_#f59e0b] uppercase tracking-wider"
          >
            <User className="w-3.5 h-3.5 text-black" />
            <span>OPERATOR_LOGIN</span>
          </button>
        )}
      </div>
    </header>
  );
};
