import { useEffect, useId, useLayoutEffect, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { Check, ChevronDown } from 'lucide-react';

import './controls.css';

export interface SelectOption<T extends string> {
  value: T;
  label: string;
}

interface SelectProps<T extends string> {
  label: string;
  value: T;
  options: SelectOption<T>[];
  onChange: (value: T) => void;
  icon?: ReactNode;
  tone?: 'light' | 'dark';
  className?: string;
}

interface MenuPosition {
  left: number;
  width: number;
  top?: number;
  bottom?: number;
}

const MENU_MAX_HEIGHT = 264;
const MENU_GAP = 6;

export function Select<T extends string>({ label, value, options, onChange, icon, tone = 'light', className }: SelectProps<T>) {
  const id = useId();
  const listId = `${id}-list`;
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLUListElement>(null);
  const typed = useRef({ text: '', timer: 0 });
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [position, setPosition] = useState<MenuPosition | null>(null);
  const selectedIndex = Math.max(0, options.findIndex((option) => option.value === value));
  const optionId = (index: number) => `${id}-option-${index}`;

  useLayoutEffect(() => {
    if (!open) return;
    const place = () => {
      const trigger = triggerRef.current;
      if (!trigger) return;
      const rect = trigger.getBoundingClientRect();
      const width = Math.max(rect.width, 120);
      const left = Math.max(8, Math.min(rect.left, window.innerWidth - width - 8));
      const menuHeight = Math.min(options.length * 38 + 12, MENU_MAX_HEIGHT);
      const spaceBelow = window.innerHeight - rect.bottom;
      const opensUp = spaceBelow < menuHeight + MENU_GAP && rect.top > spaceBelow;
      setPosition(opensUp
        ? { left, width, bottom: window.innerHeight - rect.top + MENU_GAP }
        : { left, width, top: rect.bottom + MENU_GAP });
    };
    place();
    window.addEventListener('resize', place);
    window.addEventListener('scroll', place, true);
    return () => {
      window.removeEventListener('resize', place);
      window.removeEventListener('scroll', place, true);
    };
  }, [open, options.length]);

  useEffect(() => {
    if (!open) return;
    // Safari never focuses a clicked button, so blur alone cannot close the menu there.
    const closeOutside = (event: PointerEvent) => {
      const target = event.target as Node;
      if (triggerRef.current?.contains(target) || menuRef.current?.contains(target)) return;
      setOpen(false);
    };
    document.addEventListener('pointerdown', closeOutside);
    return () => document.removeEventListener('pointerdown', closeOutside);
  }, [open]);

  useEffect(() => {
    if (open) document.getElementById(optionId(active))?.scrollIntoView({ block: 'nearest' });
  }, [open, active]);

  function openMenu(index = selectedIndex) {
    setActive(index);
    setOpen(true);
  }

  function choose(index: number) {
    const option = options[index];
    if (option && option.value !== value) onChange(option.value);
    setOpen(false);
  }

  function typeAhead(char: string) {
    window.clearTimeout(typed.current.timer);
    typed.current.text += char.toLowerCase();
    typed.current.timer = window.setTimeout(() => { typed.current.text = ''; }, 500);
    const start = open ? active : selectedIndex;
    for (let step = 1; step <= options.length; step += 1) {
      const index = (start + step) % options.length;
      if (options[index].label.toLowerCase().startsWith(typed.current.text)) {
        openMenu(index);
        return;
      }
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    const last = options.length - 1;
    const printable = event.key.length === 1 && event.key !== ' ' && !event.ctrlKey && !event.metaKey && !event.altKey;
    if (!open) {
      if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(event.key)) { event.preventDefault(); openMenu(); }
      else if (event.key === 'Home') { event.preventDefault(); openMenu(0); }
      else if (event.key === 'End') { event.preventDefault(); openMenu(last); }
      else if (printable) typeAhead(event.key);
      return;
    }
    if (event.key === 'Tab') { choose(active); return; }
    if (printable) { typeAhead(event.key); return; }
    const moves: Record<string, () => void> = {
      ArrowDown: () => setActive(Math.min(active + 1, last)),
      ArrowUp: () => (event.altKey ? choose(active) : setActive(Math.max(active - 1, 0))),
      Home: () => setActive(0),
      End: () => setActive(last),
      PageDown: () => setActive(Math.min(active + 10, last)),
      PageUp: () => setActive(Math.max(active - 10, 0)),
      Enter: () => choose(active),
      ' ': () => choose(active),
      Escape: () => setOpen(false),
    };
    const move = moves[event.key];
    if (!move) return;
    event.preventDefault();
    event.stopPropagation();
    move();
  }

  const selected = options[selectedIndex];

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        role="combobox"
        aria-label={label}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-activedescendant={open ? optionId(active) : undefined}
        className={['select-trigger', `select-${tone}`, className].filter(Boolean).join(' ')}
        onClick={() => {
          triggerRef.current?.focus();
          if (open) setOpen(false);
          else openMenu();
        }}
        onKeyDown={handleKeyDown}
        onBlur={() => setOpen(false)}
      >
        {icon}
        <span className="select-value">{selected?.label}</span>
        <ChevronDown size={16} className="select-chevron" aria-hidden="true" />
      </button>
      {open && position && createPortal(
        <ul
          ref={menuRef}
          id={listId}
          role="listbox"
          aria-label={label}
          className={`select-menu select-menu-${tone}${position.bottom !== undefined ? ' opens-up' : ''}`}
          style={{ ...position, maxHeight: MENU_MAX_HEIGHT }}
          onMouseDown={(event) => event.preventDefault()}
        >
          {options.map((option, index) => (
            <li
              key={option.value}
              id={optionId(index)}
              role="option"
              aria-selected={index === selectedIndex}
              className={index === active ? 'active' : undefined}
              onMouseEnter={() => setActive(index)}
              onClick={() => choose(index)}
            >
              <span>{option.label}</span>
              {index === selectedIndex && <Check size={15} aria-hidden="true" />}
            </li>
          ))}
        </ul>,
        document.body,
      )}
    </>
  );
}
