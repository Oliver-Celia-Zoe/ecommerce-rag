import apiClient from './client';

export interface ChatRequest {
  message: string;
  session_id?: string;
}

export interface ChatResponse {
  answer: string;
  session_id: string;
  intent?: string;
  need_human: boolean;
}

export async function sendMessage(data: ChatRequest): Promise<ChatResponse> {
  const res = await apiClient.post<ChatResponse>('/chat/', data);
  return res.data;
}