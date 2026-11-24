import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  CalendarClock,
  CalendarDays,
  ChevronDown,
  Clock3,
  Headphones,
  MapPin,
  Mic,
  MicOff,
  MoreHorizontal,
  Phone,
  PhoneOff,
  Search,
  ShieldCheck,
  Stethoscope,
  Users,
  X,
} from 'lucide-react';
import { PipecatClient } from '@pipecat-ai/client-js';
import { PipecatClientAudio, PipecatClientMicToggle, PipecatClientProvider } from '@pipecat-ai/client-react';
import { SmallWebRTCTransport } from '@pipecat-ai/small-webrtc-transport';
import { api, Appointment, Doctor, formatDate, formatShortDate, formatTime, Overview, Slot } from './lib/api';

type TranscriptEntry = {
  id: string;
  speaker: 'caller' | 'assistant';
  text: string;
  at: Date;
};

type VoiceState = 'idle' | 'connecting' | 'connected' | 'error';
type AppointmentTab = 'upcoming' | 'cancelled';

const PIPECAT_URL = import.meta.env.VITE_PIPECAT_URL || 'http://localhost:7860';

function initials(name: string) {
  return name
    .replace('Dr. ', '')
    .split(' ')
    .map((part) => part[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();
}

function App() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [slots, setSlots] = useState<Slot[]>([]);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [cancelledAppointments, setCancelledAppointments] = useState<Appointment[]>([]);
  const [activeTab, setActiveTab] = useState<AppointmentTab>('upcoming');
  const [searchTerm, setSearchTerm] = useState('');
  const [isCallOpen, setIsCallOpen] = useState(false);
  const [voiceState, setVoiceState] = useState<VoiceState>('idle');
  const [voiceError, setVoiceError] = useState('');
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [lastSync, setLastSync] = useState<Date | null>(null);
  const [apiError, setApiError] = useState('');
  const [client] = useState(
    () =>
      new PipecatClient({
        transport: new SmallWebRTCTransport(),
        enableMic: true,
        enableCam: false,
        callbacks: {
          onConnected: () => setVoiceState('connected'),
          onDisconnected: () => setVoiceState('idle'),
          onUserInput: (data) => {
            if (data.input_type === 'transcription' && data.final && data.text.trim()) {
              setTranscript((current) => [
                ...current,
                { id: crypto.randomUUID(), speaker: 'caller', text: data.text.trim(), at: new Date() },
              ]);
            }
          },
          onBotOutput: (data) => {
            const isCompleteSentence =
              data.output_type === 'sentence' &&
              (!data.spoken_status || data.spoken_status === 'completed');
            if (isCompleteSentence && data.text.trim()) {
              setTranscript((current) => [
                ...current,
                { id: crypto.randomUUID(), speaker: 'assistant', text: data.text.trim(), at: new Date() },
              ]);
            }
          },
          onError: (message) => {
            const details = message.data as { error?: string; message?: string } | undefined;
            setVoiceError(details?.error || details?.message || 'The voice connection ran into a problem.');
            setVoiceState('error');
          },
        },
      }),
  );

  const refreshDashboard = useCallback(async () => {
    try {
      const [nextOverview, nextDoctors, nextSlots, nextAppointments, nextCancelled] = await Promise.all([
        api.overview(),
        api.doctors(),
        api.availability(),
        api.appointments('booked'),
        api.appointments('cancelled'),
      ]);
      setOverview(nextOverview);
      setDoctors(nextDoctors.items);
      setSlots(nextSlots.items);
      setAppointments(nextAppointments.items);
      setCancelledAppointments(nextCancelled.items);
      setLastSync(new Date());
      setApiError('');
    } catch (error) {
      setApiError(error instanceof Error ? error.message : 'Unable to reach the clinic API.');
    }
  }, []);

  useEffect(() => {
    void refreshDashboard();
    const interval = window.setInterval(() => void refreshDashboard(), 4000);
    return () => window.clearInterval(interval);
  }, [refreshDashboard]);

  const startCall = useCallback(async () => {
    setIsCallOpen(true);
    setTranscript([]);
    setVoiceError('');
    setVoiceState('connecting');
    try {
      await client.initDevices();
      await client.startBotAndConnect({
        endpoint: `${PIPECAT_URL}/start`,
        requestData: {
          transport: 'webrtc',
          enableDefaultIceServers: true,
        },
      });
    } catch (error) {
      setVoiceError(error instanceof Error ? error.message : 'Unable to start the voice session.');
      setVoiceState('error');
    }
  }, [client]);

  const endCall = useCallback(async () => {
    try {
      await client.disconnect();
    } finally {
      setVoiceState('idle');
      setIsCallOpen(false);
      void refreshDashboard();
    }
  }, [client, refreshDashboard]);

  const visibleAppointments = useMemo(() => {
    const rows = activeTab === 'upcoming' ? appointments : cancelledAppointments;
    const query = searchTerm.trim().toLowerCase();
    if (!query) return rows;
    return rows.filter(
      (item) =>
        item.doctor_name.toLowerCase().includes(query) ||
        item.specialty.toLowerCase().includes(query) ||
        item.id.toLowerCase().includes(query) ||
        item.phone_number.includes(query),
    );
  }, [activeTab, appointments, cancelledAppointments, searchTerm]);

  const availableDoctors = useMemo(
    () =>
      doctors.map((doctor) => ({
        ...doctor,
        nextSlots: slots.filter((slot) => slot.doctor_id === doctor.id).slice(0, 3),
        totalSlots: slots.filter((slot) => slot.doctor_id === doctor.id).length,
      })),
    [doctors, slots],
  );

  const todaysAppointments = appointments.filter(
    (item) => new Date(item.starts_at).toDateString() === new Date().toDateString(),
  ).length;

  return (
    <PipecatClientProvider client={client}>
      <div className="app-shell">
        <aside className="sidebar">
          <div className="brand-lockup">
            <div className="brand-mark"><Stethoscope size={19} strokeWidth={1.8} /></div>
            <div>
              <div className="brand-name">morrow</div>
              <div className="brand-subtitle">CLINIC OPERATIONS</div>
            </div>
          </div>

          <div className="sidebar-section-label">WORKSPACE</div>
          <nav className="sidebar-nav">
            <a href="#overview" className="nav-item active"><Activity size={17} /><span>Overview</span></a>
            <a href="#appointments" className="nav-item"><CalendarDays size={17} /><span>Appointments</span><span className="nav-count">{appointments.length}</span></a>
            <a href="#doctors" className="nav-item"><Users size={17} /><span>Doctors</span></a>
          </nav>

          <div className="sidebar-bottom">
            <div className="system-card">
              <div className="system-card-top">
                <span className={lastSync ? 'system-dot' : 'system-dot offline'} />
                <span>Dashboard API</span>
                <span className="system-live">{lastSync ? 'ONLINE' : 'OFFLINE'}</span>
              </div>
              <div className="system-card-note">{lastSync ? 'Data refreshes every four seconds.' : 'Waiting for the clinic API.'}</div>
            </div>
            <div className="profile-row">
              <div className="profile-avatar">MC</div>
              <div className="profile-details"><strong>Morrow Clinic</strong><span>Front desk</span></div>
              <MoreHorizontal size={18} className="profile-more" />
            </div>
          </div>
        </aside>

        <main className="main-content">
          <header className="topbar">
            <div className="breadcrumb"><span>Workspace</span><span className="breadcrumb-divider">/</span><strong>Overview</strong></div>
            <div className="topbar-actions">
              <div className="sync-status"><span className="system-dot" />{lastSync ? `Synced ${lastSync.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}` : 'Connecting'}</div>
              <div className="topbar-avatar" aria-label="Morrow Clinic">MC</div>
            </div>
          </header>

          <div className="content-wrap" id="overview">
            <section className="page-heading">
              <div>
                <div className="eyebrow">{new Intl.DateTimeFormat('en-IN', { weekday: 'long', day: '2-digit', month: 'long', year: 'numeric' }).format(new Date()).toUpperCase()}</div>
                <h1>Good afternoon.</h1>
                <p>Here is what is happening at your clinic today.</p>
              </div>
              <button className="primary-button" onClick={() => void startCall()} disabled={voiceState === 'connecting' || voiceState === 'connected'}>
                <Phone size={16} /> Try a call
              </button>
            </section>

            {apiError && (
              <div className="error-banner">
                <span>{apiError}</span>
                <button onClick={() => void refreshDashboard()}>Retry</button>
              </div>
            )}

            <section className="metric-grid" aria-label="Clinic overview">
              <MetricCard
                label="Appointments booked"
                value={overview?.stats.booked ?? '—'}
                note={`${todaysAppointments} scheduled for today`}
                icon={<CalendarClock size={18} />}
                trend="up"
              />
              <MetricCard
                label="Available time slots"
                value={overview?.stats.available_slots ?? '—'}
                note="Across all doctors"
                icon={<Clock3 size={18} />}
              />
              <MetricCard
                label="On the roster"
                value={doctors.length || '—'}
                note="Doctors accepting appointments"
                icon={<Users size={18} />}
              />
              <div className="metric-card voice-metric">
                <div className="metric-topline"><span>Voice assistant</span><span className="metric-icon voice-icon"><Headphones size={18} /></span></div>
                <div className="voice-metric-main"><span className="voice-pulse" /> <strong>Ready for calls</strong></div>
                <button className="text-button" onClick={() => void startCall()}>Open call screen <ArrowUpRight size={14} /></button>
              </div>
            </section>

            <section className="section-block doctors-section" id="doctors">
              <div className="section-heading">
                <div><span className="section-kicker">THE CARE TEAM</span><h2>Doctors & availability</h2></div>
                <div className="section-note">Next available appointments</div>
              </div>
              <div className="doctor-grid">
                {availableDoctors.map((doctor) => (
                  <DoctorCard key={doctor.id} doctor={doctor} />
                ))}
              </div>
            </section>

            <section className="section-block appointments-section" id="appointments">
              <div className="section-heading appointment-heading">
                <div><span className="section-kicker">SCHEDULE</span><h2>Appointments</h2></div>
                <div className="appointment-toolbar">
                  <div className="search-field"><Search size={15} /><input value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} placeholder="Search appointments" /></div>
                  <button className="filter-button" onClick={() => setSearchTerm('')}>Clear filter <ChevronDown size={14} /></button>
                </div>
              </div>
              <div className="table-card">
                <div className="table-tabs">
                  <button className={activeTab === 'upcoming' ? 'table-tab active' : 'table-tab'} onClick={() => setActiveTab('upcoming')}>Upcoming <span>{appointments.length}</span></button>
                  <button className={activeTab === 'cancelled' ? 'table-tab active' : 'table-tab'} onClick={() => setActiveTab('cancelled')}>Cancelled <span>{cancelledAppointments.length}</span></button>
                  <div className="table-meta">Updates automatically</div>
                </div>
                <div className="appointment-table-wrap">
                  <table className="appointment-table">
                    <thead><tr><th>APPOINTMENT</th><th>DATE & TIME</th><th>PHONE</th><th>LOCATION</th><th>STATUS</th></tr></thead>
                    <tbody>
                      {visibleAppointments.map((appointment) => (
                        <AppointmentRow key={appointment.id} appointment={appointment} />
                      ))}
                      {visibleAppointments.length === 0 && (
                        <tr><td colSpan={5} className="empty-state">No {activeTab === 'upcoming' ? 'upcoming' : 'cancelled'} appointments found.</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
                <div className="table-footer"><span>Showing {visibleAppointments.length} record{visibleAppointments.length === 1 ? '' : 's'}</span><span>All times in IST</span></div>
              </div>
            </section>

            <footer className="page-footer"><span>Morrow Clinic appointment desk</span><span>Local demo data · Asia/Kolkata</span></footer>
          </div>
        </main>
      </div>
      <PipecatClientAudio />
      {isCallOpen && (
        <CallModal
          state={voiceState}
          error={voiceError}
          transcript={transcript}
          onRetry={() => void startCall()}
          onEnd={() => void endCall()}
        />
      )}
    </PipecatClientProvider>
  );
}

function MetricCard({
  label,
  value,
  note,
  icon,
  trend,
}: {
  label: string;
  value: string | number;
  note: string;
  icon: ReactNode;
  trend?: 'up' | 'down';
}) {
  return (
    <div className="metric-card">
      <div className="metric-topline"><span>{label}</span><span className="metric-icon">{icon}</span></div>
      <div className="metric-value">{value}</div>
      <div className="metric-note">{trend === 'up' && <ArrowUpRight size={13} />}{trend === 'down' && <ArrowDownRight size={13} />}{note}</div>
    </div>
  );
}

function DoctorCard({ doctor }: { doctor: Doctor & { nextSlots: Slot[]; totalSlots: number } }) {
  return (
    <article className="doctor-card">
      <div className="doctor-card-header">
        <div className={`doctor-avatar avatar-${doctor.color}`}>{initials(doctor.name)}</div>
        <div className="doctor-details"><h3>{doctor.name}</h3><p>{doctor.specialty}</p></div>
      </div>
      <div className="doctor-meta"><span><MapPin size={13} />{doctor.location}</span><span>{doctor.experience_years} yrs experience</span></div>
      <div className="doctor-divider" />
      <div className="slot-heading"><span>Next available</span><span>{doctor.totalSlots} open slots</span></div>
      <div className="slot-list">
        {doctor.nextSlots.length > 0 ? doctor.nextSlots.map((slot) => (
          <div className="slot-pill" key={slot.id}><span>{formatShortDate(slot.starts_at)}</span><strong>{formatTime(slot.starts_at)}</strong></div>
        )) : <span className="no-slots">No open slots listed</span>}
      </div>
    </article>
  );
}

function AppointmentRow({ appointment }: { appointment: Appointment }) {
  return (
    <tr>
      <td><div className="appointment-doctor"><div className="table-avatar">{initials(appointment.doctor_name)}</div><div><strong>{appointment.doctor_name}</strong><span>{appointment.specialty}</span></div></div></td>
      <td><div className="date-cell"><strong>{formatDate(appointment.starts_at)}</strong><span>{formatTime(appointment.starts_at)} – {formatTime(appointment.ends_at)}</span></div></td>
      <td><span className="phone-cell">•••• {appointment.phone_number.slice(-4)}</span></td>
      <td><span className="location-cell">{appointment.location}</span></td>
      <td><span className={`status-pill ${appointment.status}`}><span />{appointment.status === 'booked' ? 'Confirmed' : 'Cancelled'}</span></td>
    </tr>
  );
}

function CallModal({
  state,
  error,
  transcript,
  onRetry,
  onEnd,
}: {
  state: VoiceState;
  error: string;
  transcript: TranscriptEntry[];
  onRetry: () => void;
  onEnd: () => void;
}) {
  const [elapsed, setElapsed] = useState(0);
  const transcriptEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (state !== 'connected') return;
    const interval = window.setInterval(() => setElapsed((value) => value + 1), 1000);
    return () => window.clearInterval(interval);
  }, [state]);

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [transcript]);

  const timeLabel = `${String(Math.floor(elapsed / 60)).padStart(2, '0')}:${String(elapsed % 60).padStart(2, '0')}`;
  const statusLabel = state === 'connected' ? 'Connected' : state === 'connecting' ? 'Connecting to assistant' : state === 'error' ? 'Connection issue' : 'Call ended';

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="call-title">
      <div className="call-window">
        <div className="call-header"><div className="call-brand"><div className="brand-mark small"><Stethoscope size={15} /></div><span>Morrow Clinic</span><span className="call-header-separator">/</span><span className="call-header-muted">Voice desk</span></div><button className="modal-close" onClick={onEnd} aria-label="Close call"><X size={18} /></button></div>
        <div className="call-body">
          <div className="call-left">
            <div className="call-overline">APPOINTMENT ASSISTANT</div>
            <div className={`call-orb ${state === 'connected' ? 'is-live' : ''} ${state === 'connecting' ? 'is-connecting' : ''}`}>
              <div className="call-orb-core"><Headphones size={31} strokeWidth={1.6} /></div>
              <div className="call-orb-ring ring-one" /><div className="call-orb-ring ring-two" />
            </div>
            <h2 id="call-title">Morrow Clinic</h2>
            <p className="call-subtitle">Voice appointment desk</p>
            <div className={`call-status ${state}`}><span className="status-indicator" />{statusLabel}</div>
            <div className="call-timer">{timeLabel}</div>
            {state === 'error' && <p className="call-error">{error || 'The call could not be connected.'}</p>}
            <div className="call-controls">
              {state === 'connected' ? (
                <PipecatClientMicToggle>
                  {({ disabled, isMicEnabled, onClick }) => (
                    <button className={`call-control ${isMicEnabled ? '' : 'muted'}`} onClick={onClick} disabled={disabled} aria-label={isMicEnabled ? 'Mute microphone' : 'Unmute microphone'}>
                      {isMicEnabled ? <Mic size={18} /> : <MicOff size={18} />}
                    </button>
                  )}
                </PipecatClientMicToggle>
              ) : (
                <button className="call-control muted" disabled aria-label="Microphone unavailable"><MicOff size={18} /></button>
              )}
              {state === 'error' ? (
                <button className="end-call-button retry-button" onClick={onRetry}><Phone size={17} /> Try again</button>
              ) : (
                <button className="end-call-button" onClick={onEnd}><PhoneOff size={18} /> End call</button>
              )}
            </div>
            <div className="call-security"><ShieldCheck size={14} /> Phone confirmation is scoped to this call.</div>
          </div>
          <div className="call-transcript-panel">
            <div className="transcript-heading"><div><span className="section-kicker">LIVE CAPTIONS</span><h3>Conversation</h3></div><span className="transcript-live"><span /> LIVE</span></div>
            <div className="transcript-content">
              {transcript.length === 0 ? (
                <div className="transcript-empty">
                  <div className="transcript-empty-icon"><Activity size={19} /></div>
                  <strong>{state === 'connecting' ? 'Setting up your call' : 'Your conversation will appear here'}</strong>
                  <p>{state === 'connecting' ? 'Allow microphone access when your browser asks.' : 'Speak naturally. Your words and the assistant’s replies will be shown as you talk.'}</p>
                </div>
              ) : transcript.map((entry) => (
                <div className={`transcript-entry ${entry.speaker}`} key={entry.id}>
                  <div className="transcript-entry-meta"><strong>{entry.speaker === 'caller' ? 'You' : 'Morrow assistant'}</strong><span>{entry.at.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}</span></div>
                  <p>{entry.text}</p>
                </div>
              ))}
              <div ref={transcriptEndRef} />
            </div>
            <div className="transcript-footnote"><span className="transcript-lock"><ShieldCheck size={13} /></span> Live transcript · Not saved after this demo call</div>
          </div>
        </div>
        <div className="call-footer"><span><span className="system-dot" /> {state === 'connected' ? 'Microphone active' : 'Waiting for connection'}</span><span>Keep this window open during the call</span></div>
      </div>
    </div>
  );
}

export default App;
