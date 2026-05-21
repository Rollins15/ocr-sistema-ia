import { BASE_URL } from "../config/api";

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
  });

  if (!resposta.ok) {
    throw new Error(`Erro ${resposta.status}`);
  }

  return resposta.json();
}

export async function extrairFolha(imageUri) {
  const formData = new FormData();
  formData.append("file", {
    uri: imageUri,
    type: "image/jpeg",
    name: "folha.jpg",
  });

  const resposta = await fetch(`${BASE_URL}/ocr/folha`, {
    method: "POST",
    body: formData,
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
