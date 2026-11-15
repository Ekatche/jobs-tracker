"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { FiX } from "react-icons/fi";

interface AccessibleDialogProps {
  isOpen: boolean;
  onClose: () => void;
  titleId: string;
  title: ReactNode;
  subtitle?: string;
  maxWidthClass?: string;
  children: ReactNode;
}

function isPointerOutsideDialog(e: PointerEvent, dialog: HTMLDialogElement): boolean {
  const rect = dialog.getBoundingClientRect();
  return (
    e.clientX < rect.left ||
    e.clientX > rect.right ||
    e.clientY < rect.top ||
    e.clientY > rect.bottom
  );
}

/**
 * Accessible top-layer modal built on native `<dialog>` (`showModal()`).
 * Browser handles `Esc`, inert background, focus trapping, and focus restoration.
 */
export default function AccessibleDialog({
  isOpen,
  onClose,
  titleId,
  title,
  subtitle,
  maxWidthClass = "max-w-4xl",
  children,
}: AccessibleDialogProps) {
  const dialogRef = useRef<HTMLDialogElement | null>(null);
  const pressedOutsideRef = useRef(false);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    dialog.setAttribute("closedby", "any");

    if (isOpen && !dialog.open) {
      dialog.showModal();
    } else if (!isOpen && dialog.open) {
      dialog.close();
    }
  }, [isOpen]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog || "closedBy" in HTMLDialogElement.prototype) return;

    const handlePointerDown = (e: PointerEvent) => {
      pressedOutsideRef.current = isPointerOutsideDialog(e, dialog);
    };
    const handlePointerUp = (e: PointerEvent) => {
      if (pressedOutsideRef.current && isPointerOutsideDialog(e, dialog)) {
        dialog.close();
      }
      pressedOutsideRef.current = false;
    };

    dialog.addEventListener("pointerdown", handlePointerDown);
    dialog.addEventListener("pointerup", handlePointerUp);
    return () => {
      dialog.removeEventListener("pointerdown", handlePointerDown);
      dialog.removeEventListener("pointerup", handlePointerUp);
    };
  }, []);

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby={titleId}
      onClose={onClose}
      className={`m-auto w-[calc(100%-2rem)] ${maxWidthClass} max-h-[90vh] rounded-2xl border border-slate-700/80 bg-[#0f172a] p-0 text-slate-100 shadow-2xl open:flex open:flex-col`}
    >
      <div className="flex items-start justify-between gap-4 border-b border-slate-800 bg-slate-900/80 px-6 py-4 rounded-t-2xl">
        <div>
          <h2 id={titleId} className="text-lg font-bold text-white flex items-center gap-2">
            {title}
          </h2>
          {subtitle && <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>}
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Fermer"
          className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white transition-colors"
        >
          <FiX className="w-5 h-5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5 custom-scrollbar">{children}</div>
    </dialog>
  );
}
