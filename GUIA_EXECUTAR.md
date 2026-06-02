# Como executar o sistema

## 1. Backend

Abra um terminal na pasta `backend` e execute:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

O ambiente virtual já foi criado em `backend/.venv` usando Python 3.11.

Se precisar reinstalar as dependências:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Depois teste no navegador:

```text
http://localhost:8000/health
```

A documentação da API fica em:

```text
http://localhost:8000/docs
```

## 2. Frontend web completo

Use a pasta `web-frontend2`, porque ela contém a interface completa com Texto Geral, Quiz e Folha de Avaliação.

Abra outro terminal na pasta `web-frontend2` e execute:

```powershell
npm install
npm start
```

O frontend abre em:

```text
http://localhost:3000
```

## 3. Folha OMR — leitura por fases (recomendado pelo docente)

No Postman ou no frontend, envie `POST /ocr/folha` com `multipart/form-data`:

| Ordem | Campo `fase` | O que lê |
|-------|----------------|----------|
| 1 | `codigo` | Código do candidato/estudante (grelha 10×10) |
| 2 | `disciplinas` | Código + exame integrado Disc. 1 e 2 (nº perguntas, alinhamento) |
| 3 | `opcoes` | Código + disciplinas + opção A–E por pergunta |
| — | `completo` | Tudo (inclui nome; valor por defeito) |

Exemplo (só código):

```text
POST http://localhost:8000/ocr/folha
file=<imagem>
fase=codigo
```

A resposta inclui `proxima_fase` (ex.: depois de `codigo` vem `disciplinas`).

## 4. Comunicação frontend/backend

O frontend está configurado para chamar o backend em:

```text
http://localhost:8000
```

Se precisar alterar, copie o ficheiro:

```text
web-frontend2/.env.example
```

para:

```text
web-frontend2/.env
```

e altere o valor:

```text
REACT_APP_API_URL=http://localhost:8000
```

Depois reinicie o `npm start`.

## 5. Requisitos importantes

O Tesseract OCR precisa estar instalado no Windows. Caminho comum:

```text
C:\Program Files\Tesseract-OCR\tesseract.exe
```

Se o OCR não funcionar, confirme se o Tesseract está instalado e se o idioma português está disponível.

## 6. App mobile (Expo) — paridade com a web

A pasta `mobile-app` tem os **3 modos**: Texto Geral, Quiz e Folha de Avaliação (igual ao `web-frontend2`).

```powershell
cd mobile-app
npm install
```

Configure o IP do backend (telemóvel físico na mesma Wi-Fi):

```text
mobile-app/.env
EXPO_PUBLIC_API_URL=http://SEU_IP_DO_PC:8000
```

Referências de URL:

| Dispositivo | URL típica |
|-------------|------------|
| Expo Web / iOS Simulator | `http://localhost:8000` |
| Emulador Android | `http://10.0.2.2:8000` |
| Telemóvel (Expo Go) | `http://192.168.x.x:8000` |

Iniciar:

```powershell
npx expo start
```

O ecrã mostra se o backend está ligado e permite câmara, galeria, copiar texto e ver as 80 linhas da folha OMR.
