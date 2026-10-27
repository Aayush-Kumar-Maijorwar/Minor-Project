import { useEffect, RefObject } from 'react';

/** Calls `handler` when a pointer event lands outside `ref`'s element - used to close
 * the Models status popover in the header when the user clicks elsewhere. */
export function useOnClickOutside(ref: RefObject<HTMLElement | null>, handler: () => void, enabled = true) {
  useEffect(() => {
    if (!enabled) return;
    function onPointerDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) handler();
    }
    document.addEventListener('mousedown', onPointerDown);
    return () => document.removeEventListener('mousedown', onPointerDown);
  }, [ref, handler, enabled]);
}
