export interface ThinkingStep {
  id: string;
  timestamp: string;
  icon: string;
  text: string;
  type?: string;
}

export interface Message {
  id?: number | string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  geojson?: string | null;
  created_at?: string;
  thinkingSteps?: ThinkingStep[];
  isThinking?: boolean;
  awaitingInput?: boolean;
  image_data?: string | null;
}

export interface Conversation {
  id: string;
  operator_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface Viewport {
  center: [number, number];
  zoom: number;
  bounds?: [[number, number], [number, number]];
}

export interface User {
  username: string;
  clearance: string;
  token: string;
}

export interface Checkpoint {
  checkpoint_id: string;
  step: number;
  node: string;
  timestamp: string;
  summary: string;
}
