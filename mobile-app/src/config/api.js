import { Platform } from "react-native";
import Constants from "expo-constants";

/**
 * URL do backend OCR.
 *
 * Telemóvel físico (Expo Go / hotspot): localhost NÃO funciona — use o IP do PC.
 * Crie ou edite mobile-app/.env:
 *   EXPO_PUBLIC_API_URL=http://IP_DO_PC:8000
 * (ipconfig no Windows → IPv4 do adaptador ligado ao hotspot)
 *
 * Se não definir .env, tentamos o mesmo IP que o Metro usa (exp://IP:8081).
 */
function ipDoComputadorNaRede() {
  const raw =
    Constants.expoConfig?.hostUri ??
    Constants.expoGoConfig?.debuggerHost ??
    "";
  const host = String(raw)
    .replace(/^https?:\/\//, "")
    .split(":")[0]
    .trim();
  if (!host || host === "localhost" || host === "127.0.0.1") {
    return null;
  }
  return host;
}

export function resolveBaseUrl() {
  const fromEnv = process.env.EXPO_PUBLIC_API_URL?.trim()?.replace(/\/$/, "");

  if (
    fromEnv &&
    !/^https?:\/\/(localhost|127\.0\.0\.1)(:|\/|$)/i.test(fromEnv)
  ) {
    return fromEnv;
  }

  if (Platform.OS === "web") {
    return fromEnv || "http://localhost:8000";
  }

  const metroIp = ipDoComputadorNaRede();
  if (metroIp) {
    return `http://${metroIp}:8000`;
  }

  if (Platform.OS === "android" && !Constants.isDevice) {
    return "http://10.0.2.2:8000";
  }

  return fromEnv || "http://localhost:8000";
}

export const BASE_URL = resolveBaseUrl();

/** True quando o URL aponta para localhost num dispositivo físico. */
export function backendUrlProvavelmenteErrado() {
  if (Platform.OS === "web") {
    return false;
  }
  return /localhost|127\.0\.0\.1/.test(BASE_URL);
}
