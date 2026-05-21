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

## 3. Comunicação frontend/backend

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

## 4. Requisitos importantes

O Tesseract OCR precisa estar instalado no Windows. Caminho comum:

```text
C:\Program Files\Tesseract-OCR\tesseract.exe
```

Se o OCR não funcionar, confirme se o Tesseract está instalado e se o idioma português está disponível.
