import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import { CalendarClock, ChevronDown, ChevronLeft, ChevronRight } from 'lucide-react';

import { Select, type SelectOption } from '@/components/Select';
import './controls.css';

interface DateTimePickerProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
}

interface Time {
  hour: number;
  minute: number;
}

type Period = 'AM' | 'PM';

const WEEKDAYS = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];
const HOUR_OPTIONS: SelectOption<string>[] = Array.from({ length: 12 }, (_, index) => ({ value: String(index + 1), label: pad(index + 1) }));
const MINUTE_OPTIONS: SelectOption<string>[] = Array.from({ length: 12 }, (_, index) => ({ value: pad(index * 5), label: pad(index * 5) }));
const dayFormat = new Intl.DateTimeFormat(undefined, { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });
const timeFormat = new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit', hour12: true });
const fullDayFormat = new Intl.DateTimeFormat(undefined, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
const monthFormat = new Intl.DateTimeFormat(undefined, { month: 'long', year: 'numeric' });
const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

function pad(value: number): string {
  return String(value).padStart(2, '0');
}

function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function monthStart(date: Date, offset = 0): Date {
  return new Date(date.getFullYear(), date.getMonth() + offset, 1);
}

function addDays(date: Date, days: number): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate() + days);
}

function sameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

function dayKey(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function toDate(day: Date, time: Time): Date {
  return new Date(day.getFullYear(), day.getMonth(), day.getDate(), time.hour, time.minute);
}

// Same local format as a datetime-local input, so callers can keep using new Date(value).
function composeValue(day: Date, time: Time): string {
  return `${dayKey(day)}T${pad(time.hour)}:${pad(time.minute)}`;
}

function parseValue(value: string): { day: Date; time: Time } | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(value);
  if (!match) return null;
  const [year, month, date, hour, minute] = match.slice(1).map(Number);
  return { day: new Date(year, month - 1, date), time: { hour, minute } };
}

function nextSlot(): Time {
  const soon = new Date(Date.now() + 15 * 60_000);
  soon.setMinutes(Math.ceil(soon.getMinutes() / 5) * 5, 0, 0);
  return { hour: soon.getHours(), minute: soon.getMinutes() };
}

function monthGrid(month: Date): Date[] {
  const start = addDays(month, -month.getDay());
  return Array.from({ length: 42 }, (_, index) => addDays(start, index));
}

export function DateTimePicker({ label, value, onChange }: DateTimePickerProps) {
  const id = useId();
  const panelId = `${id}-panel`;
  const titleId = `${id}-title`;
  const triggerRef = useRef<HTMLButtonElement>(null);
  const daysRef = useRef<HTMLDivElement>(null);
  const focusAfterMove = useRef(false);
  const parsed = parseValue(value);
  const today = startOfDay(new Date());
  const [open, setOpen] = useState(() => !parsed);
  const [draftTime, setDraftTime] = useState(nextSlot);
  const [viewMonth, setViewMonth] = useState(() => monthStart(parsed?.day ?? today));
  const [focusDay, setFocusDay] = useState(() => parsed?.day ?? today);
  const days = useMemo(() => monthGrid(viewMonth), [viewMonth]);

  const time = parsed?.time ?? draftTime;
  const period: Period = time.hour < 12 ? 'AM' : 'PM';
  const hour12 = time.hour % 12 || 12;
  const isPast = parsed ? toDate(parsed.day, parsed.time).getTime() <= Date.now() : false;
  const inView = (day: Date) => day.getMonth() === viewMonth.getMonth() && day.getFullYear() === viewMonth.getFullYear();
  const tabbableDay = inView(focusDay) ? focusDay : days.find((day) => inView(day) && day >= today) ?? focusDay;

  useEffect(() => {
    if (!focusAfterMove.current) return;
    focusAfterMove.current = false;
    daysRef.current?.querySelector<HTMLButtonElement>(`[data-day="${dayKey(focusDay)}"]`)?.focus();
  }, [focusDay, viewMonth]);

  function close() {
    setOpen(false);
    triggerRef.current?.focus();
  }

  function updateTime(next: Time) {
    if (parsed) onChange(composeValue(parsed.day, next));
    else setDraftTime(next);
  }

  function pickDay(day: Date) {
    if (day < today) return;
    onChange(composeValue(day, time));
    setFocusDay(day);
    if (!inView(day)) setViewMonth(monthStart(day));
  }

  function handleDayKey(event: KeyboardEvent<HTMLButtonElement>, day: Date) {
    const moves: Record<string, () => Date> = {
      ArrowLeft: () => addDays(day, -1),
      ArrowRight: () => addDays(day, 1),
      ArrowUp: () => addDays(day, -7),
      ArrowDown: () => addDays(day, 7),
      Home: () => addDays(day, -day.getDay()),
      End: () => addDays(day, 6 - day.getDay()),
      PageUp: () => new Date(day.getFullYear(), day.getMonth() - 1, day.getDate()),
      PageDown: () => new Date(day.getFullYear(), day.getMonth() + 1, day.getDate()),
    };
    const move = moves[event.key];
    if (!move) return;
    event.preventDefault();
    const next = move();
    const target = next < today ? today : next;
    focusAfterMove.current = true;
    setFocusDay(target);
    setViewMonth(monthStart(target));
  }

  return (
    <div className="datetime">
      <button
        ref={triggerRef}
        type="button"
        className={parsed ? 'datetime-trigger' : 'datetime-trigger is-empty'}
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        onClick={() => setOpen((current) => !current)}
      >
        <CalendarClock size={18} aria-hidden="true" />
        <span className="sr-only">{label}: </span>
        <span className="datetime-value">{parsed ? `${dayFormat.format(parsed.day)} · ${timeFormat.format(toDate(parsed.day, parsed.time))}` : 'Choose a date and time'}</span>
        <ChevronDown size={17} className="datetime-chevron" aria-hidden="true" />
      </button>

      {open && (
        <div
          id={panelId}
          className="datetime-panel"
          role="group"
          aria-labelledby={titleId}
          onKeyDown={(event) => { if (event.key === 'Escape') { event.preventDefault(); close(); } }}
        >
          <div className="calendar-head">
            <button type="button" className="calendar-nav" onClick={() => setViewMonth((month) => monthStart(month, -1))} disabled={viewMonth <= monthStart(today)} aria-label="Previous month"><ChevronLeft size={18} /></button>
            <strong id={titleId} aria-live="polite">{monthFormat.format(viewMonth)}</strong>
            <button type="button" className="calendar-nav" onClick={() => setViewMonth((month) => monthStart(month, 1))} aria-label="Next month"><ChevronRight size={18} /></button>
          </div>
          <div className="calendar-weekdays" aria-hidden="true">{WEEKDAYS.map((day) => <span key={day}>{day}</span>)}</div>
          <div className="calendar-days" ref={daysRef}>
            {days.map((day) => {
              const key = dayKey(day);
              const selected = Boolean(parsed && sameDay(day, parsed.day));
              const isToday = sameDay(day, today);
              const classes = ['calendar-day', !inView(day) && 'outside', isToday && 'today', selected && 'selected'].filter(Boolean).join(' ');
              return (
                <button
                  key={key}
                  type="button"
                  data-day={key}
                  className={classes}
                  tabIndex={sameDay(day, tabbableDay) ? 0 : -1}
                  disabled={day < today}
                  aria-pressed={selected}
                  aria-current={isToday ? 'date' : undefined}
                  aria-label={fullDayFormat.format(day)}
                  onClick={() => pickDay(day)}
                  onKeyDown={(event) => handleDayKey(event, day)}
                >
                  {day.getDate()}
                </button>
              );
            })}
          </div>

          <div className="time-row">
            <span className="eyebrow">TIME</span>
            <div className="time-controls">
              <Select tone="dark" className="time-select" label="Hour" value={String(hour12)} options={HOUR_OPTIONS} onChange={(hour) => updateTime({ ...time, hour: (Number(hour) % 12) + (period === 'PM' ? 12 : 0) })} />
              <span className="time-colon" aria-hidden="true">:</span>
              <Select tone="dark" className="time-select" label="Minute" value={pad(time.minute)} options={MINUTE_OPTIONS} onChange={(minute) => updateTime({ ...time, minute: Number(minute) })} />
              <div className="period-toggle" role="group" aria-label="AM or PM">
                {(['AM', 'PM'] as const).map((option) => (
                  <button
                    key={option}
                    type="button"
                    className={period === option ? 'active' : undefined}
                    aria-pressed={period === option}
                    onClick={() => { if (option !== period) updateTime({ ...time, hour: (time.hour % 12) + (option === 'PM' ? 12 : 0) }); }}
                  >
                    {option}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="datetime-foot">
            <p className={isPast ? 'datetime-note warn' : 'datetime-note'} role={isPast ? 'alert' : undefined}>
              {isPast ? 'That time has already passed. Pick a later one.' : `Times are in ${timeZone}`}
            </p>
            <button type="button" className="datetime-done" onClick={close}>Done</button>
          </div>
        </div>
      )}
    </div>
  );
}
