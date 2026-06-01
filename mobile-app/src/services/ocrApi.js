import { BASE_URL } from "../config/api";

function ficheiroImagem(imageUri, nome = "foto.jpg") {
  return {
    uri: imageUri,
    type: "image/jpeg",
    name: nome,
  };
}

async function pedidoPost(endpoint, formData) {
  const resposta = await fetch(`${BASE_URL}${endpoint}`, {
    method: "POST",
    body: formData,
    cache: "no-store",
    headers: {
      "Cache-Control": "no-cache",
      Pragma: "no-cache",
    },
  });

  if (!resposta.ok) {
    const detalhe = await resposta.text().catch(() => "");
    throw new Error(
      `Erro ${resposta.status}${detalhe ? `: ${detalhe.slice(0, 120)}` : ""}`
    );
  }

  return resposta.json();
}

export async function extrairTexto(imageUri) {
  const formData = new FormData();
  formData.append("file", ficheiroImagem(imageUri));
  return pedidoPost("/ocr/image", formData);
}

export async function extrairQuiz(imageUri) {
  const formData = new FormData();
  formData.append("file", ficheiroImagem(imageUri, "quiz.jpg"));
  return pedidoPost("/ocr/quiz", formData);
}

export async function extrairFolha(imageUri) {
  const formData = new FormData();
  formData.append("file", ficheiroImagem(imageUri, "folha.jpg"));
  formData.append("diagnostico_detalhado", "true");
  return pedidoPost("/ocr/folha", formData);
}

export async function verificarSaude() {
  const resposta = await fetch(`${BASE_URL}/health`);
  if (!resposta.ok) {
    throw new Error(`Health check falhou: ${resposta.status}`);
  }
  return resposta.json();
}
