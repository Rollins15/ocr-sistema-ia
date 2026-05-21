# OCR Sistema Completo
**Backend Python + Web React + Mobile React Native**
**Disciplina: Inteligência Artificial · UCM**

---

## Estrutura do Projecto

```
ocr_sistema/
├── backend/
│   ├── main.py              ← API FastAPI (todos os endpoints)
│   └── requirements.txt     ← dependências Python
│
├── web-frontend/
│   └── src/
│       ├── App.jsx           ← aplicação React principal
│       ├── App.css           ← estilos
│       └── services/
│           └── ocrApi.js     ← comunicação com o backend
│
└── mobile-frontend/
    ├── App.jsx               ← entry point React Native
    └── src/
        ├── screens/
        │   └── HomeScreen.jsx ← ecrã principal
        └── services/
            └── ocrApi.js      ← comunicação com o backend
```

---

## 1. BACKEND (FastAPI)

### Instalar
```bash
cd backend
pip install -r requirements.txt
```

### Executar
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Endpoints
| Método | URL | Descrição |
|--------|-----|-----------|
| GET | /health | Verificar servidor |
| POST | /ocr/image | Extrair texto geral |
| POST | /ocr/quiz | Extrair perguntas A/B/C/D |
| POST | /ocr/folha | Folha OMR (nome, código, respostas A–E) |

### Folha OMR (`POST /ocr/folha`)

Envie **multipart/form-data** com o campo `file` (imagem). Campos opcionais no mesmo form:

| Campo | Valor por omissão | Descrição |
|--------|-------------------|-----------|
| `n_questoes_disciplina_1` | 40 | Linhas na coluna «Disciplina 1» (questões 1..N). |
| `n_questoes_disciplina_2` | 40 | Linhas na coluna «Disciplina 2» (numeração continua após a coluna 1). |
| `diagnostico_detalhado` | false | Se `true`, inclui scores, z-scores e ROI por linha em `diagnostico_omr`. |

O backend **alinha a folha** (perspectiva com base no contorno, rotação, redimensionamento canónico) antes de aplicar as regiões em percentagem; isto evita desvios graves ao passar de poucas para 80 linhas.

### Documentação automática
Abrir no browser: **http://localhost:8000/docs**

### Exemplo de resposta /ocr/image
```json
{
  "sucesso": true,
  "texto": "Texto extraído completo...",
  "palavras": 42,
  "linhas": ["linha 1", "linha 2"],
  "confianca": 0.94,
  "ficheiro_docx": "resultados/ocr_20260517.docx",
  "metadados": {
    "nome_ficheiro": "foto.jpg",
    "tamanho_bytes": 12345,
    "timestamp": "2026-05-17T12:00:00"
  }
}
```

### Exemplo de resposta /ocr/quiz
```json
{
  "sucesso": true,
  "total_perguntas": 2,
  "perguntas": [
    {
      "id": 1,
      "texto": "Qual é a capital de Moçambique?",
      "opcoes": {
        "A": "Maputo",
        "B": "Beira",
        "C": "Nampula",
        "D": "Tete"
      }
    }
  ],
  "texto_bruto": "..."
}
```

---

## 2. WEB FRONTEND (React)

### Criar projecto React
```bash
npx create-react-app web-frontend
cd web-frontend
```

### Copiar ficheiros
- Substituir `src/App.jsx` pelo fornecido
- Substituir `src/App.css` pelo fornecido
- Criar `src/services/ocrApi.js` com o conteúdo fornecido

### Executar
```bash
npm start
```
Abre em: **http://localhost:3000**

### Funcionalidades
- **Modo Texto Geral**: carrega imagem → extrai texto → mostra com botão copiar
- **Modo Quiz**: carrega imagem com perguntas → extrai e mostra perguntas clicáveis A/B/C/D

---

## 3. MOBILE FRONTEND (React Native + Expo)

### Criar projecto Expo
```bash
npx create-expo-app mobile-frontend
cd mobile-frontend
```

### Instalar dependências
```bash
npx expo install expo-image-picker
npm install @react-navigation/native @react-navigation/stack
npx expo install react-native-screens react-native-safe-area-context
```

### Copiar ficheiros
- Substituir `App.jsx` pelo fornecido
- Criar pasta `src/screens/` e copiar `HomeScreen.jsx`
- Criar pasta `src/services/` e copiar `ocrApi.js`

### Configurar URL do backend
No ficheiro `src/services/ocrApi.js`:
```js
// Emulador Android:
const BASE_URL = "http://10.0.2.2:8000";

// Dispositivo físico (usar IP do teu PC):
const BASE_URL = "http://192.168.1.X:8000";

// iOS Simulator:
const BASE_URL = "http://localhost:8000";
```

### Executar
```bash
npx expo start
```
Scannear QR code com a app Expo Go no telemóvel.

### Funcionalidades
- Botão **Câmara**: abre câmara para tirar foto
- Botão **Galeria**: escolher imagem existente
- Preview da imagem seleccionada
- Botão **Extrair Texto**: envia para o backend e mostra resultado

---

## Fluxo completo

```
[Mobile/Web] → selecciona imagem
      ↓
[Frontend] → POST /ocr/image ou /ocr/quiz com FormData
      ↓
[Backend FastAPI] → recebe bytes da imagem
      ↓
[OpenCV] → pré-processamento (5 métodos automáticos)
      ↓
[Tesseract] → extrai texto bruto
      ↓
[Parser] → organiza em JSON (texto ou perguntas)
      ↓
[python-docx] → grava ficheiro .docx
      ↓
[Backend] → retorna JSON com texto + metadados
      ↓
[Frontend] → mostra resultado ao utilizador
```

---

## Notas

- O Tesseract deve estar instalado no PC onde corre o backend
- O backend guarda automaticamente um .docx em `backend/resultados/`
- Para imagens de quiz, usar fonte grande e perguntas bem formatadas
- Formato esperado para quiz:
  ```
  1. Qual é a pergunta?
  A) Opção A
  B) Opção B
  C) Opção C
  D) Opção D
  ```
