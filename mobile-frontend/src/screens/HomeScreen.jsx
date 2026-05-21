// src/screens/HomeScreen.jsx
// Ecrã principal — React Native
// Instalar: npm install
// Executar:  npx expo start   (ou npx react-native run-android)
//
// Dependências:
//   expo-image-picker  → abrir galeria ou câmara
//   expo-document-picker → carregar ficheiro
//   @react-navigation/native → navegação entre ecrãs

import { useState } from "react";
import {
  View, Text, TouchableOpacity, Image, ScrollView,
  ActivityIndicator, StyleSheet, Alert, Platform
} from "react-native";
import * as ImagePicker from "expo-image-picker";
import { extrairTexto } from "../services/ocrApi";

export default function HomeScreen({ navigation }) {
  const [imagem, setImagem] = useState(null);
  const [carregando, setCarregando] = useState(false);
  const [resultado, setResultado] = useState(null);
  const [erro, setErro] = useState(null);

  // ── Abrir câmara ────────────────────────────────────────────────────────────
  const abrirCamera = async () => {
    const permissao = await ImagePicker.requestCameraPermissionsAsync();
    if (!permissao.granted) {
      Alert.alert("Permissão necessária", "Precisa de permitir o acesso à câmara.");
      return;
    }

    const resultado = await ImagePicker.launchCameraAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.9,
      allowsEditing: true,
    });

    if (!resultado.canceled) {
      setImagem(resultado.assets[0].uri);
      setResultado(null);
      setErro(null);
    }
  };

  // ── Abrir galeria ───────────────────────────────────────────────────────────
  const abrirGaleria = async () => {
    const permissao = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permissao.granted) {
      Alert.alert("Permissão necessária", "Precisa de permitir o acesso à galeria.");
      return;
    }

    const resultado = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.9,
      allowsEditing: true,
    });

    if (!resultado.canceled) {
      setImagem(resultado.assets[0].uri);
      setResultado(null);
      setErro(null);
    }
  };

  // ── Processar imagem ────────────────────────────────────────────────────────
  const processar = async () => {
    if (!imagem) return;
    setCarregando(true);
    setErro(null);
    setResultado(null);

    try {
      const dados = await extrairTexto(imagem);
      setResultado(dados);
    } catch (err) {
      setErro("Erro ao processar. Verifica se o servidor está activo.");
    } finally {
      setCarregando(false);
    }
  };

  return (
    <ScrollView style={estilos.container} contentContainerStyle={estilos.conteudo}>

      {/* Título */}
      <View style={estilos.header}>
        <Text style={estilos.titulo}>OCR — Leitura de Texto</Text>
        <Text style={estilos.subtitulo}>Inteligência Artificial · UCM</Text>
      </View>

      {/* Botões de selecção de imagem */}
      <View style={estilos.botoesImagem}>
        <TouchableOpacity style={[estilos.btn, estilos.btnCamera]} onPress={abrirCamera}>
          <Text style={estilos.btnTexto}>📷  Câmara</Text>
        </TouchableOpacity>

        <TouchableOpacity style={[estilos.btn, estilos.btnGaleria]} onPress={abrirGaleria}>
          <Text style={estilos.btnTexto}>🖼️  Galeria</Text>
        </TouchableOpacity>
      </View>

      {/* Preview da imagem */}
      {imagem && (
        <View style={estilos.previewContainer}>
          <Image source={{ uri: imagem }} style={estilos.preview} resizeMode="contain" />
        </View>
      )}

      {/* Botão processar */}
      {imagem && (
        <TouchableOpacity
          style={[estilos.btn, estilos.btnProcessar, carregando && estilos.btnDesactivado]}
          onPress={processar}
          disabled={carregando}
        >
          {carregando
            ? <ActivityIndicator color="white" />
            : <Text style={estilos.btnTexto}>Extrair Texto</Text>
          }
        </TouchableOpacity>
      )}

      {/* Erro */}
      {erro && (
        <View style={estilos.erroBox}>
          <Text style={estilos.erroTexto}>{erro}</Text>
        </View>
      )}

      {/* Resultado */}
      {resultado && (
        <View style={estilos.resultadoBox}>
          {/* Métricas */}
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

          {/* Texto extraído */}
          <Text style={estilos.resultadoTitulo}>Texto Extraído</Text>
          <View style={estilos.textoBox}>
            <ScrollView nestedScrollEnabled style={{ maxHeight: 300 }}>
              <Text style={estilos.textoExtraido}>
                {resultado.texto || "Nenhum texto detectado"}
              </Text>
            </ScrollView>
          </View>

          {/* Info do ficheiro guardado */}
          {resultado.ficheiro_docx && (
            <Text style={estilos.docxInfo}>
              Guardado: {resultado.ficheiro_docx}
            </Text>
          )}
        </View>
      )}

    </ScrollView>
  );
}

// ── Estilos ──────────────────────────────────────────────────────────────────
const estilos = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#f5f5f5",
  },
  conteudo: {
    padding: 20,
    paddingBottom: 40,
  },
  header: {
    backgroundColor: "#1a56db",
    borderRadius: 12,
    padding: 20,
    marginBottom: 20,
  },
  titulo: {
    color: "white",
    fontSize: 20,
    fontWeight: "700",
    marginBottom: 4,
  },
  subtitulo: {
    color: "rgba(255,255,255,0.8)",
    fontSize: 13,
  },
  botoesImagem: {
    flexDirection: "row",
    gap: 12,
    marginBottom: 16,
  },
  btn: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
  },
  btnCamera: {
    backgroundColor: "#1a56db",
  },
  btnGaleria: {
    backgroundColor: "#059669",
  },
  btnProcessar: {
    backgroundColor: "#7c3aed",
    marginBottom: 16,
  },
  btnDesactivado: {
    backgroundColor: "#9ca3af",
  },
  btnTexto: {
    color: "white",
    fontSize: 15,
    fontWeight: "600",
  },
  previewContainer: {
    backgroundColor: "white",
    borderRadius: 10,
    padding: 8,
    marginBottom: 16,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#e5e7eb",
  },
  preview: {
    width: "100%",
    height: 220,
    borderRadius: 8,
  },
  erroBox: {
    backgroundColor: "#fef2f2",
    borderWidth: 1,
    borderColor: "#fca5a5",
    borderRadius: 8,
    padding: 12,
    marginBottom: 16,
  },
  erroTexto: {
    color: "#dc2626",
    fontSize: 13,
  },
  resultadoBox: {
    backgroundColor: "white",
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: "#e5e7eb",
  },
  metricas: {
    flexDirection: "row",
    gap: 8,
    marginBottom: 12,
  },
  badge: {
    backgroundColor: "#eff6ff",
    borderWidth: 1,
    borderColor: "#bfdbfe",
    borderRadius: 20,
    paddingHorizontal: 12,
    paddingVertical: 4,
  },
  badgeTexto: {
    color: "#1d4ed8",
    fontSize: 12,
    fontWeight: "600",
  },
  resultadoTitulo: {
    fontSize: 15,
    fontWeight: "700",
    marginBottom: 10,
    color: "#111827",
  },
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
  docxInfo: {
    marginTop: 10,
    fontSize: 11,
    color: "#9ca3af",
  },
});
