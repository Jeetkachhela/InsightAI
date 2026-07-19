"use client";

import React from "react";
import { AlertTriangle, Trash2, LogOut, X, Loader2 } from "lucide-react";

interface ConfirmModalProps {
  isOpen: boolean;
  title: string;
  description: string;
  confirmText?: string;
  cancelText?: string;
  variant?: "danger" | "violet" | "default";
  iconType?: "danger" | "logout" | "info";
  isLoading?: boolean;
  onConfirm: () => void;
  onClose: () => void;
}

export default function ConfirmModal({
  isOpen,
  title,
  description,
  confirmText = "Confirm",
  cancelText = "Cancel",
  variant = "danger",
  iconType = "danger",
  isLoading = false,
  onConfirm,
  onClose,
}: ConfirmModalProps) {
  if (!isOpen) return null;

  const getIconButton = () => {
    switch (iconType) {
      case "logout":
        return <LogOut className="text-amber-400" size={24} />;
      case "info":
        return <AlertTriangle className="text-violet-400" size={24} />;
      case "danger":
      default:
        return <Trash2 className="text-red-400" size={24} />;
    }
  };

  const getConfirmButtonStyles = () => {
    switch (variant) {
      case "violet":
        return "bg-violet-600 hover:bg-violet-500 text-white border-violet-500/30 shadow-violet-500/20";
      case "default":
        return "bg-zinc-800 hover:bg-zinc-700 text-white border-zinc-700";
      case "danger":
      default:
        return "bg-red-600 hover:bg-red-500 text-white border-red-500/30 shadow-red-500/20";
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
      <div
        className="relative w-full max-w-md bg-zinc-950 border border-zinc-800/80 rounded-xl p-6 shadow-2xl shadow-black/80 space-y-4 text-left"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-zinc-500 hover:text-white transition-colors cursor-pointer p-1 rounded-md hover:bg-zinc-900"
        >
          <X size={16} />
        </button>

        <div className="flex items-start gap-4">
          <div className="p-3 rounded-xl bg-zinc-900 border border-zinc-800 flex-shrink-0">
            {getIconButton()}
          </div>
          <div>
            <h3 className="text-base font-bold text-white tracking-tight">{title}</h3>
            <p className="mt-1 text-xs text-zinc-400 leading-relaxed">{description}</p>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 pt-2 border-t border-zinc-900">
          <button
            type="button"
            onClick={onClose}
            disabled={isLoading}
            className="px-4 py-2 text-xs font-semibold text-zinc-400 hover:text-white bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 rounded-lg transition-all cursor-pointer disabled:opacity-50"
          >
            {cancelText}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isLoading}
            className={`px-4 py-2 text-xs font-semibold rounded-lg border shadow-lg transition-all flex items-center gap-1.5 cursor-pointer disabled:opacity-50 ${getConfirmButtonStyles()}`}
          >
            {isLoading && <Loader2 size={12} className="animate-spin" />}
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}
