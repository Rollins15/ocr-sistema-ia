// src/services/ocrApi.js
// Serviço que comunica com o Backend FastAPI

const BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

/**
 * Envia imagem para o endpoint /ocr/image
 * Retorna texto extraído e metadados
 */
export async function extrairTexto(imagemFile) {
  const formData = new FormData();
  formData.append("file", imagemFile);

  const resposta = await fetch(`${BASE_URL}/ocr/image`, {
    method: "POST",
    body: formData,
  });

  if (!resposta.ok) {
    throw new Error(`Erro do servidor: ${resposta.status}`);
  }

  return resposta.json();
}

/**
 * Envia imagem para o endpoint /ocr/quiz
 * Retorna array de perguntas com opções A/B/C/D
 */
export async function extrairQuiz(imagemFile) {
  const formData = new FormData();
  formData.append("file", imagemFile);

  const resposta = await fetch(`${BASE_URL}/ocr/quiz`, {
    method: "POST",
    body: formData,
  });

  if (!resposta.ok) {
    throw new Error(`Erro do servidor: ${resposta.status}`);
  }

  return resposta.json();
}

/**
 * Envia imagem para o endpoint /ocr/folha
 * Retorna nome, código e respostas marcadas
 */
export async function extrairFolha(imagemFile) {
  const formData = new FormData();
  formData.append("file", imagemFile);
  formData.append("diagnostico_detalhado", "true");

  const resposta = await fetch(`${BASE_URL}/ocr/folha`, {
    method: "POST",
    body: formData,
    cache: "no-store",
    headers: {
      "Cache-Control": "no-cache",
      Pragma: "no-cache",
    },
  });

  if (!resposta.ok) {
    throw new Error(`Erro do servidor: ${resposta.status}`);
  }

  return resposta.json();
}

/**
 * Verifica se o backend está a funcionar
 */
export async function verificarSaude() {
  const resposta = await fetch(`${BASE_URL}/health`);
  return resposta.json();
}
