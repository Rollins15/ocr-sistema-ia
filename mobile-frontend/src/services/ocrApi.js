// src/services/ocrApi.js
// Serviço de API para React Native

const BASE_URL = "http://10.0.2.2:8000"; // Android emulador → localhost do PC
// Para dispositivo físico, usar o IP da máquina: "http://192.168.x.x:8000"

/**
 * Envia imagem para /ocr/image
 * imageUri: URI da imagem (ficheiro local ou câmara)
 */
export async function extrairTexto(imageUri) {
  const formData = new FormData();
  formData.append("file", {
    uri: imageUri,
    type: "image/jpeg",
    name: "foto.jpg",
  });

  const resposta = await fetch(`${BASE_URL}/ocr/image`, {
    method: "POST",
    body: formData,
    headers: { "Content-Type": "multipart/form-data" },
  });

  if (!resposta.ok) {
    throw new Error(`Erro ${resposta.status}`);
  }

  return resposta.json();
}

export async function verificarSaude() {
  const resposta = await fetch(`${BASE_URL}/health`);
  return resposta.json();
}
