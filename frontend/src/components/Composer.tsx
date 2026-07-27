import React, { useState, useRef, useEffect } from 'react';
import { Send, Image as ImageIcon, X, AlertCircle, Sparkles } from 'lucide-react';

interface ComposerProps {
  onSendMessage: (message: string, imagePayload?: { dataUrl: string; name: string } | null) => void;
  isLoading: boolean;
  awaitingInput: boolean;
}

export const Composer: React.FC<ComposerProps> = ({
  onSendMessage,
  isLoading,
  awaitingInput,
}) => {
  const [text, setText] = useState<string>('');
  const [attachment, setAttachment] = useState<{ dataUrl: string; name: string } | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 140)}px`;
    }
  }, [text]);

  const handleSend = () => {
    if ((!text.trim() && !attachment) || isLoading) return;
    onSendMessage(text.trim(), attachment);
    setText('');
    setAttachment(null);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (evt) => {
      if (evt.target?.result) {
        setAttachment({
          dataUrl: evt.target.result as string,
          name: file.name,
        });
      }
    };
    reader.readAsDataURL(file);
  };

  return (
    <div className="p-3 bg-slate-950/90 border-t border-slate-800 backdrop-blur-md relative z-10">
      {/* Clarification Mode Warning Badge */}
      {awaitingInput && (
        <div className="mb-2 px-3 py-1.5 rounded-lg bg-amber-500/15 border border-amber-500/40 text-amber-300 text-xs font-mono flex items-center space-x-2 animate-pulse">
          <AlertCircle className="w-4 h-4 text-amber-400 shrink-0" />
          <span>AWAITING OPERATOR CLARIFICATION — REPLY TO CONTINUE REACT LOOP</span>
        </div>
      )}

      {/* Attachment Thumbnail Preview */}
      {attachment && (
        <div className="mb-2 relative inline-flex items-center space-x-2 p-1.5 rounded-lg bg-slate-900 border border-amber-500/30">
          <img src={attachment.dataUrl} alt="Upload preview" className="w-10 h-10 object-cover rounded" />
          <span className="text-xs font-mono text-slate-300 max-w-[150px] truncate">{attachment.name}</span>
          <button
            onClick={() => setAttachment(null)}
            className="p-1 rounded-full bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-red-400"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Main Input Controls matching Auth Portal bracket style */}
      <div className="flex items-end space-x-2 bg-black/40 border border-[#f59e0b]/30 border-l-2 border-l-[#f59e0b] rounded-xl p-2 focus-within:border-[#f59e0b] focus-within:shadow-[0_0_15px_rgba(245,158,11,0.2)] transition-all">
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          accept="image/*"
          className="hidden"
        />

        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          className="p-2 rounded-lg text-[#f59e0b]/70 hover:text-[#f59e0b] hover:bg-[#f59e0b]/10 transition-colors"
          title="Attach Optical Imagery"
        >
          <ImageIcon className="w-4 h-4" />
        </button>

        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={awaitingInput ? "Type clarification..." : "Type tactical request (e.g., 'traccia via dante', 'ospedali vicino duomo')..."}
          rows={1}
          disabled={isLoading}
          className="flex-1 bg-transparent border-0 text-xs font-mono text-[#f59e0b] placeholder-[#f59e0b]/40 focus:outline-none focus:ring-0 resize-none py-1.5 px-1 max-h-32"
        />

        <button
          type="button"
          onClick={handleSend}
          disabled={(!text.trim() && !attachment) || isLoading}
          className="p-2.5 rounded-lg bg-[#f59e0b] hover:bg-amber-400 disabled:opacity-40 disabled:cursor-not-allowed text-black font-bold font-mono transition-all shadow-md shadow-[#f59e0b]/30"
        >
          {isLoading ? (
            <Sparkles className="w-4 h-4 animate-spin text-black" />
          ) : (
            <Send className="w-4 h-4 text-black" />
          )}
        </button>
      </div>
    </div>
  );
};
