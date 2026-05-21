# OCR inteligente — folhas de avaliação objectivas

## Estrutura

```
backend/
├── app/
│   ├── main.py      # API FastAPI (/corrigir)
│   ├── detector.py  # Quadrados e marcações (OpenCV)
│   ├── ocr.py       # Nome, código, texto (Tesseract)
│   └── utils.py     # Pré-processamento e ficheiros
├── uploads/         # Imagens recebidas
├── resultados/      # JSON gerados
└── requirements.txt
```

## Como funciona (passo a passo)

### 1. Pré-processamento (`utils.py`)

- Redimensiona imagens muito grandes (máx. 2000 px de largura).
- Converte para **escala de cinza** e aplica **blur** Gaussiano.
- **Threshold adaptativo** binário invertido para destacar contornos.
- **Correção de inclinação** leve com `minAreaRect` (até ~8°).

### 2. Detecção de quadrados (`detector.py`)

- `findContours` no binário.
- Filtra contornos com 4–6 vértices, área e **proporção ~quadrada**.
- Calcula **fill ratio**: percentagem de pixels escuros no interior.
- Se `fill_ratio ≥ 0.42` ou média muito baixa → quadrado **preenchido**.
- Separa:
  - **Código**: topo da folha, lado direito (caixas dos dígitos).
  - **Respostas**: corpo da folha, abaixo do cabeçalho.
- Agrupa quadrados por linha (eixo Y) → cada linha = uma pergunta.
- Ordena por X → posições A, B, C, D (E se existir).

### 3. OCR (`ocr.py`)

- **Nome**: recorte da zona “NOME COMPLETO”.
- **Código**: dígito a dígito nas caixas + fallback na região do código.
- **Perguntas**: texto completo com `psm 3` e parser regex (complementar).

### 4. API (`main.py`)

- `POST /corrigir` → JSON + gravação automática em `resultados/`.

## Executar

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Documentação interactiva: http://localhost:8000/docs

**Tesseract** deve estar instalado no Windows (caminhos em `utils.py`).

## Testar no Postman

1. Método: **POST**
2. URL: `http://localhost:8000/corrigir`
3. Body → **form-data**
4. Chave: `file` | Tipo: **File** | Valor: imagem da prova (JPG/PNG)
5. Enviar

Resposta esperada (exemplo):

```json
{
  "sucesso": true,
  "nome": "",
  "codigo": "2026000001",
  "respostas": [
    {"pergunta": 1, "resposta": "C"},
    {"pergunta": 2, "resposta": "B"},
    {"pergunta": 3, "resposta": "C"},
    {"pergunta": 4, "resposta": null},
    {"pergunta": 5, "resposta": null}
  ],
  "ficheiro_json": "resultados/correcao_20260519_120000.json"
}
```

## Teste rápido em Python

```bash
cd backend
python -m app.testar_imagem caminho/para/prova.jpg
```

## Melhorar precisão no futuro

| Melhoria | Benefício |
|----------|-----------|
| Template fixo por modelo de folha | Regiões exactas (nome/código/perguntas) |
| Treino YOLO para checkboxes | Menos falsos positivos |
| Deskew com Hough lines | Fotos muito inclinadas |
| Validação “só uma marca por pergunta” | Rejeitar marcações inválidas |
| OCR manuscrito (ex. TrOCR) | Nomes escritos à mão |
| Calibrar `limiar_ratio` por scanner | Ajuste fino preto/branco |
| `DEBUG_OCR=1` + `POST /corrigir/debug` | Ver quadrados detectados |

## Variáveis úteis

- `DEBUG_OCR=1` — activa `POST /corrigir/debug` (imagem anotada em `resultados/`).
