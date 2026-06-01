// src/App.jsx
// Aplicação Web React — OCR com extração de Quiz
// Instalar: npm install
// Executar:  npm start

import { useState, useRef, useEffect } from "react";
import { extrairTexto, extrairQuiz, extrairDisciplinas } from "./services/ocrApi";
import "./App.css";

// ─── Modal: captura pela câmara do PC ─────────────────────────────────────────
function ModalCamera({ aberto, onFechar, onCaptura }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const [erroCamera, setErroCamera] = useState(null);

  useEffect(() => {
    if (!aberto) return;

    let activo = true;
    setErroCamera(null);

    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: { ideal: "environment" } }, audio: false })
      .then((stream) => {
        if (!activo) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) videoRef.current.srcObject = stream;
      })
      .catch(() => {
        setErroCamera(
          "Não foi possível aceder à câmara. Permite o acesso no browser (ícone de cadeado na barra de endereço)."
        );
      });

    return () => {
      activo = false;
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    };
  }, [aberto]);

  const capturar = () => {
    const video = videoRef.current;
    if (!video?.videoWidth) return;

    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        const ficheiro = new File([blob], `camera_${Date.now()}.jpg`, {
          type: "image/jpeg",
        });
        onCaptura(ficheiro);
        onFechar();
      },
      "image/jpeg",
      0.92
    );
  };

  if (!aberto) return null;

  return (
    <div className="camera-overlay" onClick={onFechar}>
      <div className="camera-modal" onClick={(e) => e.stopPropagation()}>
        <h3>Capturar com a câmara</h3>
        {erroCamera ? (
          <p className="camera-erro">{erroCamera}</p>
        ) : (
          <video ref={videoRef} autoPlay playsInline muted className="camera-video" />
        )}
        <div className="camera-botoes">
          <button type="button" className="btn-camera-cancelar" onClick={onFechar}>
            Cancelar
          </button>
          <button
            type="button"
            className="btn-camera-capturar"
            onClick={capturar}
            disabled={!!erroCamera}
          >
            Tirar foto
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Seleccionar imagem: ficheiro, câmara ou arrastar ───────────────────────
function SelecionarImagem({ onImagemSelecionada, previewUrl }) {
  const inputRef = useRef(null);
  const [cameraAberta, setCameraAberta] = useState(false);

  const handleDrop = (e) => {
    e.preventDefault();
    const ficheiro = e.dataTransfer.files[0];
    if (ficheiro?.type?.startsWith("image/")) onImagemSelecionada(ficheiro);
  };

  return (
    <>
      <div className="origem-botoes">
        <button
          type="button"
          className="btn-origem"
          onClick={() => inputRef.current?.click()}
        >
          📁 Carregar ficheiro
        </button>
        <button
          type="button"
          className="btn-origem btn-origem-camera"
          onClick={() => setCameraAberta(true)}
        >
          📷 Câmara
        </button>
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          hidden
          onChange={(e) => {
            const ficheiro = e.target.files?.[0];
            if (ficheiro) onImagemSelecionada(ficheiro);
            e.target.value = "";
          }}
        />
      </div>

      <div
        className="upload-zona"
        onDrop={handleDrop}
        onDragOver={(e) => e.preventDefault()}
      >
        {previewUrl ? (
          <img src={previewUrl} alt="Preview" className="preview-img" />
        ) : (
          <>
            <span className="upload-icone">🖼️</span>
            <p>Arrasta uma imagem aqui</p>
            <p className="upload-sub">ou usa os botões acima</p>
          </>
        )}
      </div>

      <ModalCamera
        aberto={cameraAberta}
        onFechar={() => setCameraAberta(false)}
        onCaptura={onImagemSelecionada}
      />
    </>
  );
}

// ─── Componente: Card de Pergunta Quiz ───────────────────────────────────────
function CardPergunta({ pergunta }) {
  const [selecionada, setSelecionada] = useState(null);

  return (
    <div className="card-pergunta">
      <div className="pergunta-header">
        <span className="pergunta-num">{pergunta.id}</span>
        <p className="pergunta-texto">{pergunta.texto}</p>
      </div>
      <div className="opcoes-grid">
        {Object.entries(pergunta.opcoes).map(([letra, texto]) => (
          <button
            key={letra}
            className={`opcao-btn ${selecionada === letra ? "selecionada" : ""}`}
            onClick={() => setSelecionada(letra)}
          >
            <span className="opcao-letra">{letra}</span>
            <span className="opcao-texto">{texto}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

// ─── Componente: Resultado Texto Geral ───────────────────────────────────────
function ResultadoTexto({ dados }) {
  const [copiado, setCopiado] = useState(false);

  const copiar = () => {
    navigator.clipboard.writeText(dados.texto);
    setCopiado(true);
    setTimeout(() => setCopiado(false), 2000);
  };

  return (
    <div className="resultado-box">
      <div className="resultado-header">
        <h3>Texto Extraído</h3>
        <div className="resultado-meta">
          <span className="badge">{dados.palavras} palavras</span>
          <span className="badge">{Math.round(dados.confianca * 100)}% confiança</span>
          <button className="btn-copiar" onClick={copiar}>
            {copiado ? "✓ Copiado" : "Copiar"}
          </button>
        </div>
      </div>
      <pre className="texto-extraido">{dados.texto}</pre>
      {dados.ficheiro_docx && (
        <p className="docx-info">
          Ficheiro guardado: <code>{dados.ficheiro_docx}</code>
        </p>
      )}
    </div>
  );
}

// ─── Resultado: EXAME INTEGRADO (disciplinas) ───────────────────────────────
function ResultadoDisciplinas({ dados }) {
  const lista = dados.disciplinas || [];

  return (
    <div className="resultado-box resultado-folha">
      <h3>EXAME INTEGRADO</h3>
      <span className="badge tipo-folha">Disciplinas marcadas</span>
      <div className="folha-campos">
        <p>
          <strong>Total:</strong> {lista.length} disciplina{lista.length !== 1 ? "s" : ""}
        </p>
        {dados.exame_integrado_detectado === false && (
          <p className="aviso-secao">
            Secção não confirmada por OCR; verifique a foto da folha.
          </p>
        )}
      </div>
      <h4>Disciplinas seleccionadas</h4>
      {lista.length > 0 ? (
        <ul className="lista-respostas">
          {lista.map((nome, i) => (
            <li key={`${nome}-${i}`}>
              <strong>{nome}</strong>
            </li>
          ))}
        </ul>
      ) : (
        <p className="sem-resultado">Nenhuma disciplina marcada detectada.</p>
      )}
      {dados.avisos?.length > 0 && (
        <ul className="lista-avisos">
          {dados.avisos.map((a, i) => (
            <li key={i}>{a}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ─── APP PRINCIPAL ────────────────────────────────────────────────────────────
export default function App() {
  const [imagem, setImagem] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [modo, setModo] = useState("texto"); // "texto" | "quiz" | "folha"
  const [carregando, setCarregando] = useState(false);
  const [resultado, setResultado] = useState(null);
  const [erro, setErro] = useState(null);

  const handleImagemSelecionada = (ficheiro) => {
    if (!ficheiro?.type?.startsWith("image/")) return;

    setPreviewUrl((urlAnterior) => {
      if (urlAnterior) URL.revokeObjectURL(urlAnterior);
      return URL.createObjectURL(ficheiro);
    });
    setImagem(ficheiro);
    setResultado(null);
    setErro(null);
  };

  const handleProcessar = async () => {
    if (!imagem) return;

    setCarregando(true);
    setErro(null);
    setResultado(null);

    try {
      let dados;
      if (modo === "quiz") {
        dados = await extrairQuiz(imagem);
      } else if (modo === "folha") {
        dados = await extrairDisciplinas(imagem);
      } else {
        dados = await extrairTexto(imagem);
      }

      setResultado(dados);
    } catch (err) {
      setErro("Erro ao processar a imagem. Verifica se o backend está a funcionar.");
    } finally {
      setCarregando(false);
    }
  };

  return (
    <div className="app">
      {/* Cabeçalho */}
      <header className="header">
        <h1>OCR — Leitura de Texto em Imagens</h1>
        <p>Universidade Católica de Moçambique · Inteligência Artificial</p>
      </header>

      <main className="conteudo">
        {/* Selector de modo */}
        <div className="modo-tabs">
          <button
            className={`tab ${modo === "texto" ? "activo" : ""}`}
            onClick={() => { setModo("texto"); setResultado(null); }}
          >
            Texto Geral
          </button>
          <button
            className={`tab ${modo === "quiz" ? "activo" : ""}`}
            onClick={() => { setModo("quiz"); setResultado(null); }}
          >
            Extractor de Quiz
          </button>
          <button
            className={`tab ${modo === "folha" ? "activo" : ""}`}
            onClick={() => { setModo("folha"); setResultado(null); }}
          >
            Folha de Avaliação (EXAME INTEGRADO)
          </button>
        </div>

        <div className="painel">
          {/* Lado esquerdo: upload */}
          <div className="painel-esquerdo">
            <h2>
              {modo === "texto" && "Carregar imagem com texto"}
              {modo === "quiz" && "Carregar imagem com perguntas"}
              {modo === "folha" && "Carregar folha — secção EXAME INTEGRADO"}
            </h2>
            <p className="descricao">
              {modo === "texto" &&
                "Carrega um ficheiro, usa a câmara do PC ou arrasta uma imagem com texto."}
              {modo === "quiz" &&
                "Carrega ou fotografa uma imagem com perguntas numeradas e opções A, B, C, D."}
              {modo === "folha" &&
                "Detecta apenas as disciplinas marcadas (Disciplina 1 e 2). Não lê nome, código nem respostas A–E."}
            </p>

            <SelecionarImagem
              onImagemSelecionada={handleImagemSelecionada}
              previewUrl={previewUrl}
            />

            <button
              className="btn-processar"
              onClick={handleProcessar}
              disabled={!imagem || carregando}
            >
              {carregando
                ? "A processar..."
                : modo === "folha"
                  ? "Detectar disciplinas"
                  : "Extrair Texto"}
            </button>

            {erro && <div className="erro-msg">{erro}</div>}
          </div>

          {/* Lado direito: resultado */}
          <div className="painel-direito">
            {!resultado && !carregando && (
              <div className="placeholder">
                <span>O resultado aparece aqui</span>
              </div>
            )}

            {carregando && (
              <div className="carregando">
                <div className="spinner" />
                <p>A analisar a imagem...</p>
              </div>
            )}

            {resultado && modo === "texto" && (
              <ResultadoTexto dados={resultado} />
            )}

            {resultado && modo === "quiz" && (
              <div className="resultado-quiz">
                <h3>
                  {resultado.total_perguntas} pergunta
                  {resultado.total_perguntas !== 1 ? "s" : ""} encontrada
                  {resultado.total_perguntas !== 1 ? "s" : ""}
                </h3>
                {resultado.perguntas && resultado.perguntas.length > 0 ? (
                  resultado.perguntas.map((p) => (
                    <CardPergunta key={p.id} pergunta={p} />
                  ))
                ) : (
                  <div className="sem-resultado">
                    <p>Nenhuma pergunta detectada.</p>
                    <p className="sub">
                      Garante que as perguntas estão numeradas (1. 2. 3.)
                      e as opções com letra (A) B) C) D)).
                    </p>
                    {resultado.texto_bruto && (
                      <details>
                        <summary>Ver texto bruto extraído</summary>
                        <pre>{resultado.texto_bruto}</pre>
                      </details>
                    )}
                  </div>
                )}
              </div>
            )}

            {resultado && modo === "folha" && (
              <ResultadoDisciplinas dados={resultado} />
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
