const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export type Doctor = {
  id: string;
  name: string;
  specialty: string;
  qualifications: string;
  experience_years: number;
  location: string;
  color: string;
};

export type Slot = {
  id: string;
  doctor_id: string;
  doctor_name: string;
  specialty: string;
  location: string;
  starts_at: string;
  ends_at: string;
};

export type Appointment = {
  id: string;
  doctor_id: string;
  doctor_name: string;
  specialty: string;
  location: string;
  slot_id: string;
  starts_at: string;
  ends_at: string;
  phone_number: string;
  status: 'booked' | 'cancelled';
  booked_at: string;
  cancelled_at: string | null;
};

export type Overview = {
  stats: { booked: number; cancelled: number; available_slots: number };
  upcoming_appointments: Appointment[];
  today: string;
  timezone: string;
};

export const api = {
  overview: () => request<Overview>('/api/overview'),
  doctors: () => request<{ items: Doctor[]; count: number }>('/api/doctors'),
  appointments: (status: 'booked' | 'cancelled' | 'all' = 'booked') =>
    request<{ items: Appointment[]; count: number }>(`/api/appointments?status=${status}`),
  availability: () => request<{ items: Slot[]; count: number }>('/api/availability'),
};

export const formatTime = (value: string) =>
  new Intl.DateTimeFormat('en-IN', { hour: 'numeric', minute: '2-digit', hour12: true }).format(new Date(value));

export const formatDate = (value: string) =>
  new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(value));

export const formatShortDate = (value: string) =>
  new Intl.DateTimeFormat('en-IN', { weekday: 'short', day: 'numeric', month: 'short' }).format(new Date(value));

export const maskPhone = (value: string) => `•••• ${value.slice(-4)}`;
