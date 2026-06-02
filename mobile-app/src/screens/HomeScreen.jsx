import { useEffect, useState } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  Image,
  ScrollView,
  ActivityIndicator,
  StyleSheet,
  Alert,
  Platform,
} from "react-native";
import * as ImagePicker from "expo-image-picker";
import * as Clipboard from "expo-clipboard";
import { BASE_URL, backendUrlProvavelmenteErrado } from "../config/api";
import {
  extrairTexto,
  extrairQuiz,
  extrairFolha,
  verificarSaude,
} from "../services/ocrApi";

const MODOS = [
  { id: "texto", label: "Texto" },
  { id: "quiz", label: "Quiz" },
  { id: "folha", label: "Folha" },
];

const DESCRICOES = {
  texto: "Foto de documento ou texto para extrair palavras.",
  quiz: "Imagem com perguntas numeradas e opções A, B, C, D.",
  folha: "Folha OMR: nome, código e respostas A–E marcadas.",
};

function perguntasEsperadasFolha(dados) {
  if (dados.tipo_folha === "omr") {
    return [
      ...Array.from({ length: 40 }, (_, i) => ({
        pergunta: i + 1,
        disciplina: 1,
      })),
      ...Array.from({ length: 40 }, (_, i) => ({
        pergunta: i + 41,
        disciplina: 2,
      })),
    ];
  }
  return Array.from({ length: 80 }, (_, i) => ({ pergunta: i + 1 }));
}

function CardPergunta({ pergunta }) {
  const [selecionada, setSelecionada] = useState(null);
  const opcoes = pergunta.opcoes || {};

  return (
    <View style={estilos.cardPergunta}>
      <View style={estilos.perguntaHeader}>
        <View style={estilos.perguntaNumWrap}>
          <Text style={estilos.perguntaNum}>{pergunta.id}</Text>
        </View>
        <Text style={estilos.perguntaTexto}>{pergunta.texto}</Text>
      </View>
      {Object.entries(opcoes).map(([letra, texto]) => (
        <TouchableOpacity
          key={letra}
          style={[
            estilos.opcaoBtn,
            selecionada === letra && estilos.opcaoBtnActiva,
          ]}
          onPress={() => setSelecionada(letra)}
        >
          <Text style={estilos.opcaoLetra}>{letra}</Text>
          <Text style={estilos.opcaoTextoOpcao}>{texto}</Text>
        </TouchableOpacity>
      ))}
    </View>
  );
}

function ResultadoTexto({ dados }) {
  const [copiado, setCopiado] = useState(false);

  const copiar = async () => {
    if (!dados.texto) return;
    await Clipboard.setStringAsync(dados.texto);
    setCopiado(true);
    setTimeout(() => setCopiado(false), 2000);
  };

  return (
    <View style={estilos.resultadoBox}>
      <View style={estilos.resultadoHeaderRow}>
        <Text style={estilos.resultadoTitulo}>Texto extraído</Text>
        <TouchableOpacity style={estilos.btnCopiar} onPress={copiar}>
          <Text style={estilos.btnCopiarTexto}>
            {copiado ? "✓ Copiado" : "Copiar"}
          </Text>
        </TouchableOpacity>
      </View>
      <View style={estilos.metricas}>
        <View style={estilos.badge}>
          <Text style={estilos.badgeTexto}>{dados.palavras ?? 0} palavras</Text>
        </View>
        <View style={estilos.badge}>
          <Text style={estilos.badgeTexto}>
            {Math.round((dados.confianca || 0) * 100)}% confiança
          </Text>
        </View>
      </View>
      <ScrollView nestedScrollEnabled style={estilos.textoBoxScroll}>
        <Text style={estilos.textoExtraido}>
          {dados.texto || "Nenhum texto detectado"}
        </Text>
      </ScrollView>
      {dados.ficheiro_docx && (
        <Text style={estilos.docxInfo}>Guardado: {dados.ficheiro_docx}</Text>
      )}
    </View>
  );
}

function ResultadoQuiz({ dados }) {
  const [mostrarBruto, setMostrarBruto] = useState(false);
  const total = dados.total_perguntas ?? dados.perguntas?.length ?? 0;

  return (
    <View style={estilos.resultadoBox}>
      <Text style={estilos.resultadoTitulo}>
        {total} pergunta{total !== 1 ? "s" : ""} encontrada
        {total !== 1 ? "s" : ""}
      </Text>
      {dados.perguntas?.length > 0 ? (
        dados.perguntas.map((p) => <CardPergunta key={p.id} pergunta={p} />)
      ) : (
        <Text style={estilos.semRespostas}>
          Nenhuma pergunta detectada. Use numeração (1. 2.) e opções A) B) C) D).
        </Text>
      )}
      {dados.texto_bruto ? (
        <>
          <TouchableOpacity
            style={estilos.btnDetalhes}
            onPress={() => setMostrarBruto(!mostrarBruto)}
          >
            <Text style={estilos.btnDetalhesTexto}>
              {mostrarBruto ? "Ocultar" : "Ver"} texto bruto
            </Text>
          </TouchableOpacity>
          {mostrarBruto && (
            <ScrollView nestedScrollEnabled style={estilos.textoBoxScroll}>
              <Text style={estilos.textoExtraido}>{dados.texto_bruto}</Text>
            </ScrollView>
          )}
        </>
      ) : null}
    </View>
  );
}

function textoRespostaFolha(item) {
  if (!item) return "Não marcada";
  if (item.estado === "multipla_marcacao") return "Múltipla marcação";
  return item.resposta || "Não marcada";
}

function ResultadoFolha({ dados }) {
  const mapa = new Map(
    (dados.respostas || []).map((r) => [Number(r.pergunta), r])
  );
  const perguntas = perguntasEsperadasFolha(dados);
  const marcadas =
    dados.respostas_marcadas ||
    (dados.respostas || []).filter((r) => r.estado === "marcada");
  const d1 = dados?.exame_integrado?.disciplina_1;
  const d2 = dados?.exame_integrado?.disciplina_2;
  const temRespostas = (dados.respostas || []).length > 0;

  return (
    <View style={estilos.resultadoBox}>
      <Text style={estilos.resultadoTitulo}>Folha processada</Text>
      {dados.tipo_folha && (
        <Text style={estilos.tipoFolha}>
          {dados.tipo_folha === "omr" ? "Folha OMR (UCM)" : "Folha simples"}
        </Text>
      )}
      {dados.request_id && (
        <Text style={estilos.campoFolha}>
          <Text style={estilos.campoLabel}>Request: </Text>
          {dados.request_id.slice(0, 8)}…
        </Text>
      )}
      <Text style={estilos.campoFolha}>
        <Text style={estilos.campoLabel}>Nome: </Text>
        {dados.nome || "Não identificado"}
      </Text>
      <Text style={estilos.campoFolha}>
        <Text style={estilos.campoLabel}>Código: </Text>
        {dados.codigo || "Não identificado"}
      </Text>
      <Text style={estilos.campoFolha}>
        <Text style={estilos.campoLabel}>Marcações: </Text>
        {marcadas.length} / {dados.total_questoes || 80}
      </Text>
      {(d1 || d2) && (
        <>
          <Text style={estilos.campoFolha}>
            <Text style={estilos.campoLabel}>Disciplina 1: </Text>
            {d1?.disciplina_escolhida || "Não marcada"}
          </Text>
          <Text style={estilos.campoFolha}>
            <Text style={estilos.campoLabel}>Disciplina 2: </Text>
            {d2?.disciplina_escolhida || "Não marcada"}
          </Text>
        </>
      )}
      {dados.imagem_sha256 && (
        <Text style={estilos.docxInfo}>
          Hash: {dados.imagem_sha256.slice(0, 16)}…
        </Text>
      )}

      {temRespostas ? (
        <>
          <Text style={[estilos.resultadoTitulo, { marginTop: 12 }]}>
            Questões (1–80)
          </Text>
          <ScrollView nestedScrollEnabled style={{ maxHeight: 320 }}>
            {perguntas.map((p) => {
              const r = mapa.get(Number(p.pergunta));
              const texto = textoRespostaFolha(r);
              const naoMarcada = !r || r.estado === "nao_marcada";
              const multipla = r?.estado === "multipla_marcacao";
              return (
                <View
                  key={p.pergunta}
                  style={[
                    estilos.respostaItem,
                    naoMarcada && estilos.respostaNaoMarcada,
                    multipla && estilos.respostaMultipla,
                  ]}
                >
                  <Text style={estilos.respostaTexto}>
                    Pergunta {p.pergunta}
                    {(r?.disciplina || p.disciplina)
                      ? ` (D${r?.disciplina || p.disciplina})`
                      : ""}
                    :{" "}
                    <Text style={estilos.respostaLetra}>{texto}</Text>
                  </Text>
                </View>
              );
            })}
          </ScrollView>
        </>
      ) : (
        <Text style={estilos.semRespostas}>
          Sem respostas A–E nesta fase. Use o resultado de disciplinas acima.
        </Text>
      )}

      {dados.avisos?.length > 0 && (
        <View style={estilos.avisoBox}>
          {dados.avisos.map((a, i) => (
            <Text key={i} style={estilos.avisoTexto}>
              {a}
            </Text>
          ))}
        </View>
      )}
      {dados.ficheiro_json && (
        <Text style={estilos.docxInfo}>JSON: {dados.ficheiro_json}</Text>
      )}
    </View>
  );
}

export default function HomeScreen() {
  const [imagem, setImagem] = useState(null);
  const [modo, setModo] = useState("texto");
  const [carregando, setCarregando] = useState(false);
  const [resultado, setResultado] = useState(null);
  const [erro, setErro] = useState(null);
  const [backendOk, setBackendOk] = useState(null);

  useEffect(() => {
    verificarSaude()
      .then(() => setBackendOk(true))
      .catch(() => setBackendOk(false));
  }, []);

  const seleccionarImagem = (uri) => {
    setImagem(uri);
    setResultado(null);
    setErro(null);
  };

  const abrirCamera = async () => {
    const permissao = await ImagePicker.requestCameraPermissionsAsync();
    if (!permissao.granted) {
      Alert.alert("Permissão necessária", "Permita o acesso à câmara.");
      return;
    }
    const res = await ImagePicker.launchCameraAsync({
      mediaTypes: ["images"],
      quality: 0.9,
      allowsEditing: true,
    });
    if (!res.canceled) seleccionarImagem(res.assets[0].uri);
  };

  const abrirGaleria = async () => {
    const permissao = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permissao.granted) {
      Alert.alert("Permissão necessária", "Permita o acesso à galeria.");
      return;
    }
    const res = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images"],
      quality: 0.9,
      allowsEditing: true,
    });
    if (!res.canceled) seleccionarImagem(res.assets[0].uri);
  };

  const processar = async () => {
    if (!imagem) return;
    setCarregando(true);
    setErro(null);
    setResultado(null);

    try {
      let dados;
      if (modo === "quiz") {
        dados = await extrairQuiz(imagem);
      } else if (modo === "folha") {
        dados = await extrairFolha(imagem);
      } else {
        dados = await extrairTexto(imagem);
      }
      setResultado(dados);
    } catch (e) {
      setErro(
        `Erro ao processar (${e.message}). Backend em ${BASE_URL} — confirme que está activo.`
      );
    } finally {
      setCarregando(false);
    }
  };

  const labelProcessar =
    modo === "folha"
      ? "Processar folha"
      : modo === "quiz"
        ? "Extrair quiz"
        : "Extrair texto";

  return (
    <ScrollView style={estilos.container} contentContainerStyle={estilos.conteudo}>
      <View style={estilos.header}>
        <Text style={estilos.titulo}>OCR — Leitura de Texto</Text>
        <Text style={estilos.subtitulo}>Inteligência Artificial · UCM</Text>
      </View>

      {backendOk === false && (
        <View style={estilos.erroBox}>
          <Text style={estilos.erroTexto}>
            Backend offline em {BASE_URL}.
            {backendUrlProvavelmenteErrado()
              ? " No telemóvel, localhost é o próprio telefone — não o PC."
              : ""}{" "}
            PC: uvicorn main:app --host 0.0.0.0 --port 8000. Hotspot: no PC
            ipconfig → IPv4; em mobile-app/.env use
            EXPO_PUBLIC_API_URL=http://IP_DO_PC:8000 e reinicie com npx expo
            start -c
          </Text>
        </View>
      )}
      {backendOk === true && (
        <Text style={estilos.backendOk}>✓ Backend ligado ({BASE_URL})</Text>
      )}

      <View style={estilos.modoTabs}>
        {MODOS.map((m) => (
          <TouchableOpacity
            key={m.id}
            style={[estilos.tab, modo === m.id && estilos.tabActivo]}
            onPress={() => {
              setModo(m.id);
              setResultado(null);
              setErro(null);
            }}
          >
            <Text
              style={[estilos.tabTexto, modo === m.id && estilos.tabTextoActivo]}
            >
              {m.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <Text style={estilos.descricao}>{DESCRICOES[modo]}</Text>

      <View style={estilos.botoesImagem}>
        <TouchableOpacity style={[estilos.btn, estilos.btnCamera]} onPress={abrirCamera}>
          <Text style={estilos.btnTexto}>📷 Câmara</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[estilos.btn, estilos.btnGaleria]} onPress={abrirGaleria}>
          <Text style={estilos.btnTexto}>🖼️ Galeria</Text>
        </TouchableOpacity>
      </View>

      {imagem && (
        <View style={estilos.previewContainer}>
          <Image source={{ uri: imagem }} style={estilos.preview} resizeMode="contain" />
        </View>
      )}

      {imagem && (
        <TouchableOpacity
          style={[estilos.btn, estilos.btnProcessar, carregando && estilos.btnDesactivado]}
          onPress={processar}
          disabled={carregando}
        >
          {carregando ? (
            <ActivityIndicator color="white" />
          ) : (
            <Text style={estilos.btnTexto}>{labelProcessar}</Text>
          )}
        </TouchableOpacity>
      )}

      {erro && (
        <View style={estilos.erroBox}>
          <Text style={estilos.erroTexto}>{erro}</Text>
        </View>
      )}

      {resultado && modo === "texto" && <ResultadoTexto dados={resultado} />}
      {resultado && modo === "quiz" && <ResultadoQuiz dados={resultado} />}
      {resultado && modo === "folha" && <ResultadoFolha dados={resultado} />}
    </ScrollView>
  );
}

const estilos = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f5f5" },
  conteudo: { padding: 20, paddingBottom: 48 },
  header: {
    backgroundColor: "#1a56db",
    borderRadius: 12,
    padding: 20,
    marginBottom: 12,
  },
  titulo: { color: "white", fontSize: 20, fontWeight: "700", marginBottom: 4 },
  subtitulo: { color: "rgba(255,255,255,0.85)", fontSize: 13 },
  backendOk: {
    fontSize: 12,
    color: "#059669",
    fontWeight: "600",
    marginBottom: 10,
  },
  modoTabs: { flexDirection: "row", gap: 6, marginBottom: 10 },
  tab: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 8,
    borderWidth: 2,
    borderColor: "#1a56db",
    alignItems: "center",
    backgroundColor: "white",
  },
  tabActivo: { backgroundColor: "#1a56db" },
  tabTexto: { color: "#1a56db", fontWeight: "600", fontSize: 13 },
  tabTextoActivo: { color: "white" },
  descricao: { fontSize: 13, color: "#6b7280", marginBottom: 14 },
  botoesImagem: { flexDirection: "row", gap: 10, marginBottom: 14 },
  btn: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
  },
  btnCamera: { backgroundColor: "#1a56db" },
  btnGaleria: { backgroundColor: "#059669" },
  btnProcessar: { backgroundColor: "#7c3aed", marginBottom: 14 },
  btnDesactivado: { backgroundColor: "#9ca3af" },
  btnTexto: { color: "white", fontSize: 15, fontWeight: "600" },
  previewContainer: {
    backgroundColor: "white",
    borderRadius: 10,
    padding: 8,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: "#e5e7eb",
  },
  preview: { width: "100%", height: 200, borderRadius: 8 },
  erroBox: {
    backgroundColor: "#fef2f2",
    borderWidth: 1,
    borderColor: "#fca5a5",
    borderRadius: 8,
    padding: 12,
    marginBottom: 14,
  },
  erroTexto: { color: "#dc2626", fontSize: 13 },
  resultadoBox: {
    backgroundColor: "white",
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: "#e5e7eb",
    marginBottom: 12,
  },
  resultadoHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 10,
  },
  resultadoTitulo: {
    fontSize: 16,
    fontWeight: "700",
    color: "#111827",
    marginBottom: 8,
  },
  btnCopiar: {
    backgroundColor: "#eff6ff",
    borderWidth: 1,
    borderColor: "#bfdbfe",
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  btnCopiarTexto: { color: "#1d4ed8", fontSize: 12, fontWeight: "600" },
  metricas: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 10 },
  badge: {
    backgroundColor: "#eff6ff",
    borderWidth: 1,
    borderColor: "#bfdbfe",
    borderRadius: 20,
    paddingHorizontal: 12,
    paddingVertical: 4,
  },
  badgeTexto: { color: "#1d4ed8", fontSize: 12, fontWeight: "600" },
  textoBoxScroll: {
    maxHeight: 280,
    backgroundColor: "#f9fafb",
    borderRadius: 8,
    padding: 12,
    borderWidth: 1,
    borderColor: "#e5e7eb",
  },
  textoExtraido: {
    fontFamily: Platform.OS === "ios" ? "Courier" : "monospace",
    fontSize: 13,
    color: "#374151",
    lineHeight: 20,
  },
  docxInfo: { marginTop: 10, fontSize: 11, color: "#9ca3af" },
  tipoFolha: { fontSize: 12, color: "#1d4ed8", marginBottom: 8, fontWeight: "600" },
  campoFolha: { fontSize: 14, color: "#374151", marginBottom: 6 },
  campoLabel: { fontWeight: "700" },
  respostaItem: {
    backgroundColor: "#f9fafb",
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 8,
    padding: 10,
    marginBottom: 6,
  },
  respostaNaoMarcada: { opacity: 0.75, backgroundColor: "#fffbeb" },
  respostaMultipla: { backgroundColor: "#fef3c7" },
  respostaTexto: { fontSize: 13, color: "#374151" },
  respostaLetra: { fontWeight: "700", color: "#1a56db" },
  semMarcada: { fontStyle: "italic", color: "#9ca3af" },
  semRespostas: { fontSize: 13, color: "#9ca3af", fontStyle: "italic", marginBottom: 8 },
  avisoBox: {
    marginTop: 10,
    padding: 10,
    backgroundColor: "#fffbeb",
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#fcd34d",
  },
  avisoTexto: { fontSize: 12, color: "#92400e" },
  cardPergunta: {
    backgroundColor: "#f9fafb",
    borderRadius: 10,
    padding: 12,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: "#e5e7eb",
  },
  perguntaHeader: { flexDirection: "row", gap: 10, marginBottom: 10 },
  perguntaNumWrap: {
    backgroundColor: "#1a56db",
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
  },
  perguntaNum: {
    color: "white",
    fontWeight: "700",
    fontSize: 13,
  },
  perguntaTexto: { flex: 1, fontSize: 14, color: "#111827" },
  opcaoBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#e5e7eb",
    marginBottom: 6,
    backgroundColor: "white",
  },
  opcaoBtnActiva: { borderColor: "#1a56db", backgroundColor: "#eff6ff" },
  opcaoLetra: { fontWeight: "700", color: "#1a56db", width: 20 },
  opcaoTextoOpcao: { flex: 1, fontSize: 13, color: "#374151" },
  btnDetalhes: { marginTop: 8, marginBottom: 8 },
  btnDetalhesTexto: { color: "#1a56db", fontWeight: "600", fontSize: 13 },
});
