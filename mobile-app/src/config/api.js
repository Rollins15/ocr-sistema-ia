/**
 * URL do backend OCR.
 *
 * Crie mobile-app/.env com:
 *   EXPO_PUBLIC_API_URL=http://SEU_IP:8000
 *
 * Referências:
 * - Emulador Android: http://10.0.2.2:8000
 * - Expo Web / iOS Simulator: http://localhost:8000
 * - Telemóvel físico (Expo Go): http://IP_DO_PC:8000 (ipconfig → IPv4)
 */
export const BASE_URL =
  process.env.EXPO_PUBLIC_API_URL || "http://localhost:8000";
