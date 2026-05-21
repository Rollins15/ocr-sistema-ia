import { useState } from "react";
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
import { extrairTexto, extrairFolha } from "../services/ocrApi";

export default function HomeScreen() {
  const [imagem, setImagem] = useState(null);
  const [modo, setModo] = useState("texto"); // "texto" | "folha"
  const [carregando, setCarregando] = useState(false);
  const [resultado, setResultado] = useState(null);
  const [erro, setErro] = useState(null);

  const abrirCamera = async () => {
    const permissao = await ImagePicker.requestCameraPermissionsAsync();
    if (!permissao.granted) {
      Alert.alert("Permissão necessária", "Precisa de permitir o acesso à câmara.");
      return;
    }

    const res = await ImagePicker.launchCameraAsync({
      mediaTypes: ["images"],
      quality: 0.9,
      allowsEditing: true,
    });

    if (!res.canceled) {
      setImagem(res.assets[0].uri);
      setResultado(null);
      setErro(null);
    }
  };

  const abrirGaleria = async () => {
    const permissao = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permissao.granted) {
      Alert.alert("Permissão necessária", "Precisa de permitir o acesso à galeria.");
      return;
    }

    const res = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images"],
      quality: 0.9,
      allowsEditing: true,
    });

    if (!res.canceled) {
      setImagem(res.assets[0].uri);
      setResultado(null);
      setErro(null);
    }
  };

  const processar = async () => {
    if (!imagem) return;
    setCarregando(true);
    setErro(null);
    setResultado(null);

    try {
      const dados =
        modo === "folha" ? await extrairFolha(imagem) : await extrairTexto(imagem);
      setResultado(dados);
    } catch {
      setErro(
        "Erro ao processar. Confirma o IP em src/config/api.js e que o backend está activo (mesma Wi-Fi)."
      );
    } finally {
      setCarregando(false);
    }
  };

  return (
    <ScrollView style={estilos.container} contentContainerStyle={estilos.conteudo}>
      <View style={estilos.header}>
        <Text style={estilos.titulo}>OCR — Leitura de Texto</Text>
        <Text style={estilos.subtitulo}>Inteligência Artificial · UCM</Text>
      </View>

      <View style={estilos.modoTabs}>
        <TouchableOpacity
          style={[estilos.tab, modo === "texto" && estilos.tabActivo]}
          onPress={() => {
            setModo("texto");
            setResultado(null);
          }}
        >
          <Text style={[estilos.tabTexto, modo === "texto" && estilos.tabTextoActivo]}>
            Texto
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[estilos.tab, modo === "folha" && estilos.tabActivo]}
          onPress={() => {
            setModo("folha");
            setResultado(null);
          }}
        >
          <Text style={[estilos.tabTexto, modo === "folha" && estilos.tabTextoActivo]}>
            Folha
          </Text>
        </TouchableOpacity>
      </View>

      <Text style={estilos.descricao}>
        {modo === "folha"
          ? "Foto da folha OMR (código 10 colunas + respostas A–E)."
          : "Foto de documento ou texto para extrair palavras."}
      </Text>

      <View style={estilos.botoesImagem}>
        <TouchableOpacity style={[estilos.btn, estilos.btnCamera]} onPress={abrirCamera}>
          <Text style={estilos.btnTexto}>📷  Câmara</Text>
        </TouchableOpacity>

        <TouchableOpacity style={[estilos.btn, estilos.btnGaleria]} onPress={abrirGaleria}>
          <Text style={estilos.btnTexto}>🖼️  Galeria</Text>
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
            <Text style={estilos.btnTexto}>
              {modo === "folha" ? "Processar folha" : "Extrair texto"}
            </Text>
          )}
        </TouchableOpacity>
      )}

      {erro && (
        <View style={estilos.erroBox}>
          <Text style={estilos.erroTexto}>{erro}</Text>
        </View>
      )}

      {resultado && modo === "texto" && (
        <View style={estilos.resultadoBox}>
          <View style={estilos.metricas}>
            <View style={estilos.badge}>
              <Text style={estilos.badgeTexto}>{resultado.palavras} palavras</Text>
            </View>
            <View style={estilos.badge}>
              <Text style={estilos.badgeTexto}>
                {Math.round((resultado.confianca || 0) * 100)}% confiança
              </Text>
            </View>
          </View>

          <Text style={estilos.resultadoTitulo}>Texto extraído</Text>
          <View style={estilos.textoBox}>
            <ScrollView nestedScrollEnabled style={{ maxHeight: 300 }}>
              <Text style={estilos.textoExtraido}>
                {resultado.texto || "Nenhum texto detectado"}
              </Text>
            </ScrollView>
          </View>

          {resultado.ficheiro_docx && (
            <Text style={estilos.docxInfo}>Guardado: {resultado.ficheiro_docx}</Text>
          )}
        </View>
      )}

      {resultado && modo === "folha" && (
        <View style={estilos.resultadoBox}>
          <Text style={estilos.resultadoTitulo}>Folha processada</Text>
          {resultado.tipo_folha && (
            <Text style={estilos.tipoFolha}>
              {resultado.tipo_folha === "omr" ? "Modelo OMR UCM" : "Folha simples"}
            </Text>
          )}

          <Text style={estilos.campoFolha}>
            <Text style={estilos.campoLabel}>Nome: </Text>
            {resultado.nome || "(não preenchido)"}
          </Text>
          <Text style={estilos.campoFolha}>
            <Text style={estilos.campoLabel}>Código: </Text>
            {resultado.codigo || "(não detectado)"}
          </Text>

          <Text style={[estilos.resultadoTitulo, { marginTop: 12 }]}>Respostas</Text>
          {resultado.respostas?.length > 0 ? (
            resultado.respostas.map((r) => (
              <View key={r.pergunta} style={estilos.respostaItem}>
                <Text style={estilos.respostaTexto}>
                  Pergunta {r.pergunta}
                  {r.disciplina ? ` (D${r.disciplina})` : ""}:{" "}
                  <Text style={estilos.respostaLetra}>{r.resposta}</Text>
                </Text>
              </View>
            ))
          ) : (
            <Text style={estilos.semRespostas}>Nenhuma alternativa marcada detectada.</Text>
          )}

          {resultado.ficheiro_json && (
            <Text style={estilos.docxInfo}>JSON: {resultado.ficheiro_json}</Text>
          )}
        </View>
      )}
    </ScrollView>
  );
}

const estilos = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f5f5" },
  conteudo: { padding: 20, paddingBottom: 40 },
  header: {
    backgroundColor: "#1a56db",
    borderRadius: 12,
    padding: 20,
    marginBottom: 16,
  },
  titulo: { color: "white", fontSize: 20, fontWeight: "700", marginBottom: 4 },
  subtitulo: { color: "rgba(255,255,255,0.8)", fontSize: 13 },
  modoTabs: { flexDirection: "row", gap: 8, marginBottom: 12 },
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
  tabTexto: { color: "#1a56db", fontWeight: "600", fontSize: 14 },
  tabTextoActivo: { color: "white" },
  descricao: { fontSize: 13, color: "#6b7280", marginBottom: 16 },
  botoesImagem: { flexDirection: "row", gap: 12, marginBottom: 16 },
  btn: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
  },
  btnCamera: { backgroundColor: "#1a56db" },
  btnGaleria: { backgroundColor: "#059669" },
  btnProcessar: { backgroundColor: "#7c3aed", marginBottom: 16 },
  btnDesactivado: { backgroundColor: "#9ca3af" },
  btnTexto: { color: "white", fontSize: 15, fontWeight: "600" },
  previewContainer: {
    backgroundColor: "white",
    borderRadius: 10,
    padding: 8,
    marginBottom: 16,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#e5e7eb",
  },
  preview: { width: "100%", height: 220, borderRadius: 8 },
  erroBox: {
    backgroundColor: "#fef2f2",
    borderWidth: 1,
    borderColor: "#fca5a5",
    borderRadius: 8,
    padding: 12,
    marginBottom: 16,
  },
  erroTexto: { color: "#dc2626", fontSize: 13 },
  resultadoBox: {
    backgroundColor: "white",
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: "#e5e7eb",
  },
  metricas: { flexDirection: "row", gap: 8, marginBottom: 12 },
  badge: {
    backgroundColor: "#eff6ff",
    borderWidth: 1,
    borderColor: "#bfdbfe",
    borderRadius: 20,
    paddingHorizontal: 12,
    paddingVertical: 4,
  },
  badgeTexto: { color: "#1d4ed8", fontSize: 12, fontWeight: "600" },
  resultadoTitulo: {
    fontSize: 15,
    fontWeight: "700",
    marginBottom: 10,
    color: "#111827",
  },
  tipoFolha: { fontSize: 12, color: "#1d4ed8", marginBottom: 10, fontWeight: "600" },
  campoFolha: { fontSize: 14, color: "#374151", marginBottom: 8 },
  campoLabel: { fontWeight: "700" },
  respostaItem: {
    backgroundColor: "#f9fafb",
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 8,
    padding: 12,
    marginBottom: 8,
  },
  respostaTexto: { fontSize: 14, color: "#374151" },
  respostaLetra: { fontWeight: "700", color: "#1a56db" },
  semRespostas: { fontSize: 13, color: "#9ca3af", fontStyle: "italic" },
  textoBox: {
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
});
