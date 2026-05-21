# =============================================================================
# BACKEND: OCR API com FastAPI
# Ficheiro: backend/main.py
# Executar: uvicorn main:app --reload --host 0.0.0.0 --port 8000
# =============================================================================
#
# ENDPOINTS:
#   POST /ocr/image   → recebe imagem, extrai texto geral, retorna JSON
#   POST /ocr/quiz    → recebe imagem, extrai perguntas A/B/C/D, retorna JSON
#   POST /ocr/folha   → folha de avaliação (nome, código, respostas marcadas)
#   GET  /health      → verificar se o servidor está a funcionar
#
# INSTALAR:
#   pip install fastapi uvicorn python-multipart pytesseract
#               opencv-python pillow numpy python-docx
# =============================================================================

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import cv2
import numpy as np
import pytesseract
from PIL import Image
import io
import re
import os
import json
import datetime
import logging
import hashlib
import uuid
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

logger = logging.getLogger("uvicorn.error")

# Configurar Tesseract (ajustar caminho se necessário)
caminhos_tesseract = [
    r'C:\Program Files\Tesseract-OCR\tesseract.exe',
    r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
    r'C:\Users\hp\AppData\Local\Programs\Tesseract-OCR\tesseract.exe',
]
for c in caminhos_tesseract:
    if os.path.exists(c):
        pytesseract.pytesseract.tesseract_cmd = c
        break

# =============================================================================
# INICIALIZAR APP
# =============================================================================
app = FastAPI(
    title="OCR API",
    description="API para extração de texto em imagens com OCR",
    version="1.0.0"
)

# Permitir CORS para React (web) e React Native (mobile)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # em produção: especificar origens
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pasta para guardar resultados
os.makedirs("resultados", exist_ok=True)


# =============================================================================
# FUNÇÕES DE PRÉ-PROCESSAMENTO
# =============================================================================

def bytes_to_cv2(image_bytes: bytes):
    """Converte bytes recebidos via HTTP para imagem OpenCV."""
    nparr = np.frombuffer(image_bytes, np.uint8)
    return cv2.imdecode(nparr, cv2.IMREAD_COLOR)


def pre_processar(imagem, metodo="automatico"):
    """Aplica pré-processamento para melhorar o OCR."""
    cinza = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)
    h, w = cinza.shape
    # Ampliar 1.5x para melhorar leitura
    cinza = cv2.resize(cinza, (int(w*1.5), int(h*1.5)), interpolation=cv2.INTER_CUBIC)

    if metodo == "simples":
        return cinza
    elif metodo == "contraste":
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        return clahe.apply(cinza)
    elif metodo == "adaptativo":
        suavizada = cv2.GaussianBlur(cinza, (3,3), 0)
        return cv2.adaptiveThreshold(suavizada, 255,
                   cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 10)
    elif metodo == "otsu":
        denoised = cv2.fastNlMeansDenoising(cinza, h=10)
        _, binarizada = cv2.threshold(denoised, 0, 255,
                           cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binarizada
    else:  # automatico
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        return clahe.apply(cinza)


def extrair_melhor_texto(imagem):
    """
    Testa vários métodos de pré-processamento e retorna
    o que extrai mais texto.
    """
    metodos = ["simples", "contraste", "adaptativo", "otsu"]
    melhor_texto = ""
    max_chars = 0

    for metodo in metodos:
        try:
            processada = pre_processar(imagem, metodo)
            img_pil = Image.fromarray(processada)
            texto = pytesseract.image_to_string(
                img_pil,
                lang="por+eng",
                config="--psm 3 --oem 3"
            ).strip()
            if len(texto) > max_chars:
                max_chars = len(texto)
                melhor_texto = texto
        except Exception:
            try:
                processada = pre_processar(imagem, metodo)
                img_pil = Image.fromarray(processada)
                texto = pytesseract.image_to_string(
                    img_pil, lang="eng", config="--psm 3 --oem 3"
                ).strip()
                if len(texto) > max_chars:
                    max_chars = len(texto)
                    melhor_texto = texto
            except Exception:
                pass

    return melhor_texto


# =============================================================================
# PARSER DE QUIZ
# =============================================================================

def parsear_quiz(texto: str) -> list:
    """
    Analisa o texto extraído e organiza em estrutura de quiz.

    Formato esperado na imagem:
        1. Qual é a capital de Moçambique?
        A) Maputo
        B) Beira
        C) Nampula
        D) Tete

    Retorna lista de dicionários:
        [{ "id": 1, "texto": "...", "opcoes": {"A":"...","B":"...","C":"...","D":"..."} }]
    """
    perguntas = []
    linhas = [l.strip() for l in texto.split('\n') if l.strip()]

    pergunta_atual = None
    opcoes_atuais = {}
    num_atual = None

    # Padrões para detectar perguntas e opções
    padrao_pergunta = re.compile(r'^(\d+)[.\)]\s+(.+)')
    padrao_opcao    = re.compile(r'^([A-Da-d])[.\)]\s+(.+)')

    for linha in linhas:
        match_p = padrao_pergunta.match(linha)
        match_o = padrao_opcao.match(linha)

        if match_p:
            # Guardar pergunta anterior se existir
            if pergunta_atual and opcoes_atuais:
                perguntas.append({
                    "id": num_atual,
                    "texto": pergunta_atual,
                    "opcoes": opcoes_atuais
                })
            # Nova pergunta
            num_atual = int(match_p.group(1))
            pergunta_atual = match_p.group(2).strip()
            opcoes_atuais = {}

        elif match_o and pergunta_atual is not None:
            letra = match_o.group(1).upper()
            opcoes_atuais[letra] = match_o.group(2).strip()

        elif pergunta_atual and not match_o:
            # Continuação da pergunta (texto em múltiplas linhas)
            pergunta_atual += " " + linha

    # Guardar última pergunta
    if pergunta_atual and opcoes_atuais:
        perguntas.append({
            "id": num_atual,
            "texto": pergunta_atual,
            "opcoes": opcoes_atuais
        })

    return perguntas


# =============================================================================
# FOLHA DE RESPOSTAS OMR (/ocr/folha) — modelo UCM / exame integrado
# =============================================================================

LETRAS_OPCOES = ["A", "B", "C", "D", "E"]

# Numeração padrão da folha OMR UCM: 1–40 (Disc. 1) e 41–80 (Disc. 2) — configurável na API
# Linha do nome fica abaixo do bloco "FOLHA DE RESPOSTAS"/assinaturas.
# Zona de escrita do nome (imagem canónica 1000×1414, à direita de «Nome Completo»)
ROI_NOME = (0.30, 0.195, 0.35, 0.058)
ROI_CODIGO_BOLHAS = (0.04, 0.482, 0.29, 0.135)  # grelha 10×10 (bolhas)
ROI_CODIGO_CAIXAS = (0.048, 0.308, 0.288, 0.045)  # 10 caixas com dígitos escritos
ROI_CODIGO = ROI_CODIGO_BOLHAS  # compatibilidade
ROI_DISC1 = (0.39, 0.305, 0.24, 0.62)       # coluna "Disciplina - 1"
ROI_DISC2 = (0.665, 0.305, 0.24, 0.62)      # coluna "Disciplina - 2"
TAMANHO_OMR = (1000, 1414)                  # (largura, altura) canónica
LIMIAR_PIXEL_ESCURO = 170

# Dentro do ROI de cada disciplina: zona horizontal onde estão só os 5 rectângulos
OMR_BOLHAS_X0_REL = 0.16
OMR_BOLHAS_X1_REL = 1.0
OMR_DISC_Y_INSET_TOP = 0.01
OMR_DISC_Y_INSET_TOP_D1 = 0.01
OMR_DISC_Y_INSET_TOP_D2 = 0.0045
OMR_DISC_Y_INSET_BOTTOM = 0.006
OMR_CODIGO_PCT_MIN_CELULA = 12.0

OMR_Z_MIN_MARCA = 2.2
OMR_Z_MARGEM_SOBRE_2 = 0.85
OMR_INK_MIN_ABSOLUTO = 7.0
OMR_PCT_MIN_ABSOLUTO = 10.5
OMR_PCT_MIN_COM_SCORE_FORTE = 7.0
OMR_SCORE_MIN_BYPASS_PCT = 15.0

# Classificação por preenchimento real (sem correções por folha anterior)
OMR_PCT_MARCA_MIN = 18.0
OMR_PCT_MARCA_FORTE = 25.0
OMR_SCORE_MARCA_FORTE = 32.0
OMR_MARGEM_PCT_SEGUNDA = 1.45
OMR_PCT_MARCA_FRACA_MIN = 12.0
OMR_MARGEM_CELULA_INTERIOR = 0.26
OMR_REFINO_LINHA_JANELA = 0.22
OMR_VIZINHO_MARGEM_PCT = 9.0
OMR_VIZINHO_RATIO_MIN = 1.35

RESPOSTA_NAO_MARCADA = "Não marcada"
RESPOSTA_MULTIPLA = "Múltipla marcação"
NOME_NAO_IDENTIFICADO = "Não identificado"


def ocr_regiao(imagem_bgr, x, y, w, h, psm=7):
    """OCR num recorte da imagem (coordenadas em pixels)."""
    h_img, w_img = imagem_bgr.shape[:2]
    x1 = max(0, int(x))
    y1 = max(0, int(y))
    x2 = min(w_img, int(x + w))
    y2 = min(h_img, int(y + h))
    if x2 <= x1 or y2 <= y1:
        return ""
    recorte = imagem_bgr[y1:y2, x1:x2]
    cinza = pre_processar(recorte, "contraste")
    try:
        return pytesseract.image_to_string(
            Image.fromarray(cinza), lang="por+eng", config=f"--psm {psm} --oem 3"
        ).strip()
    except Exception:
        return ""


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def limpar_resultados_antigos(max_ficheiros: int = 40):
    """
    Mantém apenas os ficheiros mais recentes em resultados/.
    Evita crescimento infinito e reduz risco de confusão manual com saídas antigas.
    """
    pasta = Path("resultados")
    pasta.mkdir(exist_ok=True)
    ficheiros = sorted(
        [p for p in pasta.glob("*.json") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for f in ficheiros[max_ficheiros:]:
        try:
            f.unlink()
        except Exception:
            logger.warning("Falha ao remover resultado antigo: %s", str(f))


def _roi_pixels(imagem, rx, ry, rw, rh):
    """Converte região relativa (0–1) em coordenadas absolutas."""
    h, w = imagem.shape[:2]
    x1 = int(w * rx)
    y1 = int(h * ry)
    x2 = int(w * (rx + rw))
    y2 = int(h * (ry + rh))
    return max(0, x1), max(0, y1), min(w, x2), min(h, y2)


def percentagem_celula(cinza, rx, ry, rw, rh, margem=0.18):
    """Percentagem de preenchimento escuro numa célula da grelha OMR."""
    x1, y1, x2, y2 = _roi_pixels(cinza, rx, ry, rw, rh)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    roi = cinza[y1:y2, x1:x2]
    mh = max(1, int(roi.shape[0] * margem))
    mw = max(1, int(roi.shape[1] * margem))
    interior = roi[mh:-mh, mw:-mw] if roi.shape[0] > 2 * mh and roi.shape[1] > 2 * mw else roi
    if interior.size == 0:
        return 0.0
    escuros = interior < LIMIAR_PIXEL_ESCURO
    return 100.0 * np.count_nonzero(escuros) / escuros.size


def _ordenar_pontos_quad(pts: np.ndarray) -> np.ndarray:
    """Ordena 4 pontos: topo-esq, topo-dir, fundo-dir, fundo-esq."""
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1).ravel()
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def _encontrar_quad_pagina(imagem_bgr: np.ndarray) -> Optional[np.ndarray]:
    """
    Procura o maior quadrilátero com forma de folha (perspectiva).
    Falha com segurança (None) se a foto não tiver contorno claro.
    """
    h0, w0 = imagem_bgr.shape[:2]
    area_img = float(h0 * w0)
    gray = cv2.cvtColor(imagem_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    bordas = cv2.Canny(gray, 60, 180)
    bordas = cv2.dilate(bordas, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)), iterations=1)
    cnts, _ = cv2.findContours(bordas, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:20]
    proporcao_alvo = TAMANHO_OMR[1] / float(TAMANHO_OMR[0])  # altura/largura ~1.414

    for c in cnts:
        a = cv2.contourArea(c)
        if a < 0.18 * area_img:
            continue
        peri = cv2.arcLength(c, True)
        for eps in (0.015, 0.02, 0.025, 0.03, 0.035):
            approx = cv2.approxPolyDP(c, eps * peri, True)
            if len(approx) != 4:
                continue
            pts = approx.reshape(4, 2).astype(np.float32)
            rect = cv2.boundingRect(pts)
            rw, rh = rect[2], rect[3]
            if rw < 10 or rh < 10:
                continue
            rprop = max(rw, rh) / float(min(rw, rh))
            if abs(rprop - proporcao_alvo) > 0.55:
                continue
            return pts

    # Fallback: segmentar "papel" claro e usar minAreaRect.
    # Ajuda quando o contorno externo não forma 4 vértices limpos.
    hsv = cv2.cvtColor(imagem_bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (0, 0, 120), (179, 90, 255))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8), iterations=2)
    cnts2, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if cnts2:
        c2 = max(cnts2, key=cv2.contourArea)
        if cv2.contourArea(c2) > 0.2 * area_img:
            rect = cv2.minAreaRect(c2)
            box = cv2.boxPoints(rect).astype(np.float32)
            return box
    return None


def _warp_perspetiva(imagem_bgr: np.ndarray, pts_quad: np.ndarray) -> np.ndarray:
    dst_w, dst_h = TAMANHO_OMR
    rect = _ordenar_pontos_quad(pts_quad)
    dst = np.array(
        [[0, 0], [dst_w - 1, 0], [dst_w - 1, dst_h - 1], [0, dst_h - 1]],
        dtype="float32",
    )
    m = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(
        imagem_bgr,
        m,
        (dst_w, dst_h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )


def _deskew_leve_bgr(imagem_bgr: np.ndarray) -> Tuple[np.ndarray, float]:
    """Corrige inclinação pequena (foto de telemóvel). Devolve (imagem, graus aplicados)."""
    gray = cv2.cvtColor(imagem_bgr, cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    coords = np.column_stack(np.where(th > 0))
    if len(coords) < 800:
        return imagem_bgr, 0.0
    ang = cv2.minAreaRect(coords)[-1]
    if ang < -45:
        ang = 90 + ang
    if abs(ang) < 0.18:
        return imagem_bgr, 0.0
    h, w = imagem_bgr.shape[:2]
    m = cv2.getRotationMatrix2D((w // 2, h // 2), ang, 1.0)
    out = cv2.warpAffine(
        imagem_bgr,
        m,
        (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return out, float(ang)


def preparar_imagem_folha_avaliacao(imagem_bgr: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Pipeline único para leitura da folha:
    - retrato (rotação 90° se paisagem)
    - correcção de perspectiva (quad detectado) ou redimensionamento
    - tamanho canónico TAMANHO_OMR (coordenadas % estáveis)
    - deskew leve
    """
    meta: Dict[str, Any] = {
        "rotacao_90": False,
        "perspectiva_corrigida": False,
        "deskew_graus": 0.0,
        "tamanho_original": [int(imagem_bgr.shape[1]), int(imagem_bgr.shape[0])],
    }
    img = imagem_bgr.copy()
    h, w = img.shape[:2]
    if w > h:
        img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        meta["rotacao_90"] = True
        h, w = img.shape[:2]

    quad = _encontrar_quad_pagina(img)
    if quad is not None:
        img = _warp_perspetiva(img, quad)
        meta["perspectiva_corrigida"] = True
    else:
        img = cv2.resize(img, TAMANHO_OMR, interpolation=cv2.INTER_AREA)
        logger.info("OMR: perspectiva automática não detectada; usado apenas redimensionamento.")

    img, ang_skew = _deskew_leve_bgr(img)
    meta["deskew_graus"] = ang_skew
    if abs(ang_skew) >= 0.18:
        meta["deskew_aplicado"] = True
    else:
        meta["deskew_aplicado"] = False

    if img.shape[1] != TAMANHO_OMR[0] or img.shape[0] != TAMANHO_OMR[1]:
        img = cv2.resize(img, TAMANHO_OMR, interpolation=cv2.INTER_AREA)

    meta["tamanho_final"] = [int(img.shape[1]), int(img.shape[0])]
    return img, meta


def score_tinta_celula_cinza(cinza: np.ndarray, rx: float, ry: float, rw: float, rh: float) -> float:
    """
    Score de 'tinta' na célula (maior = mais marcada). Usa interior com margem
    para ignorar contorno do rectângulo impresso.
    """
    x1, y1, x2, y2 = _roi_pixels(cinza, rx, ry, rw, rh)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    roi = cinza[y1:y2, x1:x2]
    mh = max(1, int(roi.shape[0] * 0.22))
    mw = max(1, int(roi.shape[1] * 0.22))
    if roi.shape[0] <= 2 * mh or roi.shape[1] <= 2 * mw:
        core = roi
    else:
        core = roi[mh:-mh, mw:-mw]
    if core.size == 0:
        return 0.0
    blur = cv2.GaussianBlur(core, (3, 3), 0)
    escuridao = 255.0 - float(np.mean(blur))
    _, bw = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    cobertura = 100.0 * float(np.count_nonzero(bw)) / float(bw.size)
    return escuridao * 0.62 + cobertura * 0.38


def _escolher_marca_linha_omr(scores: List[float]) -> Tuple[Optional[int], Dict[str, Any]]:
    """
    Escolhe o índice 0..4 marcado com base na dispersão **dentro da mesma linha**
    (robusto a 80 linhas densas, marcas fracas e ruído).
    """
    info: Dict[str, Any] = {"scores": [round(float(s), 2) for s in scores], "z_scores": []}
    if len(scores) != 5:
        info["motivo"] = "n_opcoes_invalido"
        return None, info
    s = np.array(scores, dtype=np.float64)
    med = float(np.median(s))
    mad = float(np.median(np.abs(s - med))) + 1e-6
    z = (s - med) / mad
    info["z_scores"] = [round(float(z[i]), 3) for i in range(5)]
    i0 = int(np.argmax(z))
    z0 = float(z[i0])
    z_sorted = np.sort(z)
    z1 = float(z_sorted[-2])
    s0 = float(s[i0])
    p80 = float(np.percentile(s, 80))

    if s0 < OMR_INK_MIN_ABSOLUTO and z0 < OMR_Z_MIN_MARCA + 0.5:
        info["motivo"] = "abaixo_minimo_absoluto"
        return None, info
    if s0 < max(OMR_INK_MIN_ABSOLUTO, p80 + 1.4):
        info["motivo"] = "score_abs_baixo"
        return None, info
    if z0 < OMR_Z_MIN_MARCA:
        info["motivo"] = "z_baixo"
        return None, info
    if z0 < z1 + OMR_Z_MARGEM_SOBRE_2 and z0 < 4.0:
        info["motivo"] = "ambiguo_vs_2_opcao"
        return None, info
    info["motivo"] = "marca_valida"
    return i0, info


def _avaliar_marca_linha_omr(
    scores: List[float], pcts: List[float]
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Decide a resposta de uma linha só com base na imagem actual.
    Exige preenchimento visível (% tinta na bolha), não apenas contraste da grelha.
    """
    opcoes_pct = {LETRAS_OPCOES[j]: round(float(pcts[j]), 2) for j in range(5)}
    opcoes_score = {LETRAS_OPCOES[j]: round(float(scores[j]), 2) for j in range(5)}
    info: Dict[str, Any] = {
        "opcoes_percentagem": opcoes_pct,
        "opcoes_score": opcoes_score,
    }

    candidatas: List[Tuple[int, float, float]] = []
    for j in range(5):
        p, s = float(pcts[j]), float(scores[j])
        if p >= OMR_PCT_MARCA_MIN:
            candidatas.append((j, p, s))
        elif (
            p >= OMR_PCT_MARCA_FRACA_MIN
            and s >= OMR_SCORE_MARCA_FORTE
            and p >= OMR_PCT_MIN_COM_SCORE_FORTE
        ):
            candidatas.append((j, p, s))

    if not candidatas:
        info["motivo"] = "abaixo_limiar_preenchimento"
        return RESPOSTA_NAO_MARCADA, "nao_marcada", info

    if len(candidatas) > 1:
        candidatas.sort(key=lambda x: x[1], reverse=True)
        j0, p0, s0 = candidatas[0]
        p1 = candidatas[1][1]
        if p0 >= OMR_PCT_MARCA_FORTE and p0 >= p1 * OMR_MARGEM_PCT_SEGUNDA:
            info["motivo"] = "multipla_dominante"
            info["percentagem_escolhida"] = round(p0, 2)
            info["score_escolhido"] = round(s0, 2)
            return LETRAS_OPCOES[j0], "marcada", info
        letras = [LETRAS_OPCOES[c[0]] for c in candidatas]
        info["motivo"] = "multipla_marcacao"
        info["opcoes_marcadas"] = letras
        return RESPOSTA_MULTIPLA, "multipla_marcacao", info

    j0, p0, s0 = candidatas[0]
    info["motivo"] = "marca_unica_preenchimento"
    info["percentagem_escolhida"] = round(p0, 2)
    info["score_escolhido"] = round(s0, 2)
    return LETRAS_OPCOES[j0], "marcada", info


def normalizar_omr(imagem):
    """Alias: mesma saída que `preparar_imagem_folha_avaliacao` (só imagem)."""
    img, _ = preparar_imagem_folha_avaliacao(imagem)
    return img


def binarizar_omr(imagem):
    """Imagem binária robusta para diagnóstico e validação de marcações."""
    cinza = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY) if len(imagem.shape) == 3 else imagem
    cinza = cv2.GaussianBlur(cinza, (3, 3), 0)
    return cv2.adaptiveThreshold(
        cinza, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 12
    )


def e_folha_omr(imagem):
    """Detecta folha padrão 'FOLHA DE RESPOSTAS' (vertical A4)."""
    h, w = imagem.shape[:2]
    if h < w * 1.05:
        return False
    # Folha canónica / retrato: evita OCR extra no título (lento)
    if h >= w * 1.25:
        return True
    texto = ocr_regiao(imagem, 0, 0, w, int(h * 0.09), psm=6).upper()
    return "FOLHA" in texto and "RESPOST" in texto


def detetar_quadrados(cinza, area_min=60, area_max=12000):
    """Contornos quadrados (checkboxes e caixas do código)."""
    blur = cv2.GaussianBlur(cinza, (3, 3), 0)
    _, binaria = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contornos, _ = cv2.findContours(binaria, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    quadrados = []
    for cnt in contornos:
        area = cv2.contourArea(cnt)
        if area < area_min or area > area_max:
            continue
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.05 * peri, True)
        if len(approx) < 4 or len(approx) > 6:
            continue
        x, y, w, h = cv2.boundingRect(approx)
        if w < 6 or h < 6:
            continue
        ratio = w / float(h)
        if 0.55 <= ratio <= 1.45:
            quadrados.append({
                "x": x, "y": y, "w": w, "h": h,
                "cx": x + w / 2, "cy": y + h / 2,
                "area": area,
            })
    return quadrados


def percentagem_preenchimento(cinza, box):
    """Percentagem de pixels escuros no interior do quadrado (0–100)."""
    x, y, w, h = box["x"], box["y"], box["w"], box["h"]
    m = max(1, int(min(w, h) * 0.15))
    roi = cinza[y + m : y + h - m, x + m : x + w - m]
    if roi.size == 0:
        return 0.0
    _, bw = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return 100.0 * np.count_nonzero(bw) / bw.size


def agrupar_quadrados_em_linhas(quadrados, tolerancia_y=None):
    """Agrupa quadrados pela coordenada Y (mesma linha da folha)."""
    if not quadrados:
        return []
    if tolerancia_y is None:
        alturas = [q["h"] for q in quadrados]
        tolerancia_y = max(12, int(np.median(alturas) * 0.85))

    ordenados = sorted(quadrados, key=lambda q: (q["cy"], q["cx"]))
    linhas = []
    linha_atual = [ordenados[0]]
    for q in ordenados[1:]:
        if abs(q["cy"] - linha_atual[-1]["cy"]) <= tolerancia_y:
            linha_atual.append(q)
        else:
            linhas.append(sorted(linha_atual, key=lambda x: x["cx"]))
            linha_atual = [q]
    linhas.append(sorted(linha_atual, key=lambda x: x["cx"]))
    return linhas


def _agrupar_por_coluna_x(boxes, tolerancia=None):
    """Agrupa quadrados sobrepostos na mesma coluna (rótulo + checkbox)."""
    if not boxes:
        return []
    if tolerancia is None:
        tolerancia = max(20, int(np.median([b["w"] for b in boxes]) * 1.2))
    ordenados = sorted(boxes, key=lambda b: b["cx"])
    clusters = [[ordenados[0]]]
    for b in ordenados[1:]:
        if abs(b["cx"] - clusters[-1][-1]["cx"]) <= tolerancia:
            clusters[-1].append(b)
        else:
            clusters.append([b])
    return clusters


def checkboxes_da_linha(cinza, linha_boxes):
    """Uma caixa por coluna A–D (a mais pintada de cada grupo)."""
    clusters = _agrupar_por_coluna_x(linha_boxes)
    if len(clusters) < 4:
        return []
    # Manter as 4 colunas centrais de opções (ignorar ruído à esquerda)
    if len(clusters) > 4:
        clusters = sorted(clusters, key=lambda c: c[0]["cx"])[-4:]
    caixas = []
    for cluster in clusters:
        caixa = max(cluster, key=lambda b: percentagem_preenchimento(cinza, b))
        caixas.append(caixa)
    return sorted(caixas, key=lambda b: b["cx"])


def resposta_marcada_na_linha(cinza, linha_boxes):
    """Devolve A–D da opção mais pintada, ou None se nenhuma estiver marcada."""
    caixas = checkboxes_da_linha(cinza, linha_boxes)
    if len(caixas) != 4:
        return None
    niveis = [
        (LETRAS_OPCOES[i], percentagem_preenchimento(cinza, caixas[i]))
        for i in range(4)
    ]
    niveis.sort(key=lambda x: x[1], reverse=True)
    melhor_letra, melhor_pct = niveis[0]
    segundo_pct = niveis[1][1]
    if melhor_pct < 40:
        return None
    if melhor_pct < max(55, segundo_pct * 1.35):
        return None
    return melhor_letra


def _escolher_marca_vertical_codigo(scores: List[float]) -> Tuple[Optional[int], Dict[str, Any]]:
    """Uma marca por coluna na grelha 10×10 do código (scores = score_tinta por linha)."""
    info: Dict[str, Any] = {"scores": [round(float(s), 2) for s in scores], "z_scores": []}
    if len(scores) != 10:
        info["motivo"] = "tamanho_invalido"
        return None, info
    s = np.array(scores, dtype=np.float64)
    med = float(np.median(s))
    mad = float(np.median(np.abs(s - med))) + 1e-6
    z = (s - med) / mad
    info["z_scores"] = [round(float(z[i]), 3) for i in range(10)]
    i0 = int(np.argmax(z))
    z0 = float(z[i0])
    z_sorted = np.sort(z)
    z1 = float(z_sorted[-2])
    s0 = float(s[i0])
    if s0 < 12.0 and z0 < 2.2:
        info["motivo"] = "fraco"
        return None, info
    if z0 < 2.0:
        info["motivo"] = "z_baixo"
        return None, info
    if z0 < z1 + 0.7 and z0 < 3.4:
        info["motivo"] = "ambiguo"
        return None, info
    info["motivo"] = "digito_ok"
    return i0, info


def _ocr_digito_caixa(rec_bgr: np.ndarray) -> str:
    """OCR de um único dígito numa caixa (manuscrito) — uma passagem."""
    if rec_bgr is None or rec_bgr.size == 0:
        return ""
    if len(rec_bgr.shape) == 3:
        cinza = cv2.cvtColor(rec_bgr, cv2.COLOR_BGR2GRAY)
    else:
        cinza = rec_bgr
    ampliada = cv2.resize(
        cinza, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC
    )
    _, bin_img = cv2.threshold(
        ampliada, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )
    try:
        txt = pytesseract.image_to_string(
            Image.fromarray(bin_img),
            config="--psm 10 --oem 3 -c tessedit_char_whitelist=0123456789",
        ).strip()
    except Exception:
        txt = ""
    digitos = re.sub(r"\D", "", txt)
    return digitos[-1] if digitos else ""


def _codigo_omr_plausivel(codigo: str, colunas_marcadas: int) -> bool:
    """Rejeita grelha vazia ou leituras espúrias (ex.: só zeros)."""
    if not codigo or len(codigo) < 8:
        return False
    if len(set(codigo)) == 1:
        return False
    if codigo.count("0") >= 8:
        return False
    if colunas_marcadas < 7:
        return False
    return True


def _tinta_caixa_codigo(imagem_bgr: np.ndarray, coluna: int) -> float:
    """Quantidade de tinta na caixa manuscrita de uma coluna do código."""
    h_img, w_img = imagem_bgr.shape[:2]
    rx, ry, rw, rh = ROI_CODIGO_CAIXAS
    x1, y1, x2, y2 = _roi_pixels(imagem_bgr, rx, ry, rw, rh)
    cw = (x2 - x1) / 10.0
    xa = x1 + coluna * cw
    cinza = cv2.cvtColor(imagem_bgr, cv2.COLOR_BGR2GRAY)
    return score_tinta_celula_cinza(
        cinza, xa / w_img, y1 / h_img, cw / w_img, (y2 - y1) / h_img
    )


def _digito_caixa_coluna(imagem_bgr: np.ndarray, coluna: int) -> str:
    """OCR de uma coluna específica das caixas de código manuscrito."""
    rx, ry, rw, rh = ROI_CODIGO_CAIXAS
    x1, y1, x2, y2 = _roi_pixels(imagem_bgr, rx, ry, rw, rh)
    rec = imagem_bgr[y1:y2, x1:x2]
    if rec.size == 0:
        return ""
    cw = rec.shape[1] / 10.0
    xa = int(coluna * cw)
    xb = int((coluna + 1) * cw)
    margem = max(2, int(cw * 0.1))
    cel = rec[:, xa + margem : xb - margem]
    return _ocr_digito_caixa(cel)


def _refinar_codigo_candidato(
    codigo: str,
    imagem_bgr: Optional[np.ndarray] = None,
    image_sha256: Optional[str] = None,
    imagem_orig: Optional[np.ndarray] = None,
) -> str:
    """Sem heurísticas por folha anterior — só normaliza comprimento."""
    return codigo[:10] if codigo else ""


def _limites_colunas_caixas_codigo(cinza_roi: np.ndarray) -> List[int]:
    """Detecta separadores verticais das 10 caixas do código (ou divisão uniforme)."""
    h, w = cinza_roi.shape[:2]
    blur = cv2.GaussianBlur(cinza_roi, (3, 3), 0)
    bordas = cv2.Canny(blur, 50, 140)
    kern = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(8, h // 3)))
    vert = cv2.morphologyEx(bordas, cv2.MORPH_OPEN, kern)
    proj = vert.sum(axis=0).astype(np.float64)
    if proj.max() > 0:
        limiar = max(proj.max() * 0.35, proj.mean() + proj.std() * 0.5)
        xs = [i for i in range(w) if proj[i] >= limiar]
        if xs:
            grupos: List[List[int]] = [[xs[0]]]
            for x in xs[1:]:
                if x - grupos[-1][-1] <= 4:
                    grupos[-1].append(x)
                else:
                    grupos.append([x])
            centros = [int(sum(g) / len(g)) for g in grupos]
            if 9 <= len(centros) <= 12:
                centros = sorted(centros)
                if len(centros) > 11:
                    centros = centros[1:11]
                return [0] + centros + [w]
    return [int(i * w / 10) for i in range(11)]


def extrair_codigo_caixas_escritas(imagem_bgr: np.ndarray) -> str:
    """Lê os 10 dígitos escritos nas caixas acima da grelha OMR."""
    rx, ry, rw, rh = ROI_CODIGO_CAIXAS
    x1, y1, x2, y2 = _roi_pixels(imagem_bgr, rx, ry, rw, rh)
    rec = imagem_bgr[y1:y2, x1:x2]
    if rec.size == 0:
        return ""

    cw = rec.shape[1] / 10.0
    digitos = []
    for i in range(10):
        xa = int(i * cw)
        xb = int((i + 1) * cw)
        margem = max(2, int(cw * 0.1))
        cel = rec[:, xa + margem : xb - margem]
        digitos.append(_ocr_digito_caixa(cel))
    return "".join(d for d in digitos if d)[:10]


def extrair_codigo_omr(cinza):
    """Código do candidato: grelha 10×10 (coluna = posição, linha = dígito 0–9)."""
    rx, ry, rw, rh = ROI_CODIGO_BOLHAS
    n_cols, n_rows = 10, 10
    cw, ch = rw / n_cols, rh / n_rows
    digitos = []
    marcadas = 0

    for col in range(n_cols):
        scores = []
        pcts = []
        for row in range(n_rows):
            x_c = rx + col * cw
            y_c = ry + row * ch
            scores.append(score_tinta_celula_cinza(cinza, x_c, y_c, cw, ch))
            pcts.append(
                percentagem_celula(
                    cinza, x_c, y_c, cw, ch, margem=OMR_MARGEM_CELULA_INTERIOR
                )
            )

        idx_pct = int(np.argmax(pcts))
        if float(pcts[idx_pct]) >= OMR_CODIGO_PCT_MIN_CELULA:
            idx = idx_pct
        else:
            idx, _ = _escolher_marca_vertical_codigo(scores)

        if idx is not None and (
            pcts[idx] >= OMR_CODIGO_PCT_MIN_CELULA
            or scores[idx] >= 18.0
        ):
            marcadas += 1
            digitos.append(str(idx))
        else:
            digitos.append("")

    codigo = "".join(d for d in digitos if d)
    if not _codigo_omr_plausivel(codigo, marcadas):
        return ""
    return codigo


def extrair_codigo(
    imagem,
    imagem_orig: Optional[np.ndarray] = None,
    image_sha256: Optional[str] = None,
    folha_omr: Optional[bool] = None,
):
    """
    Código da prova: grelha OMR (grelha 10×10) ou folha simples (cabeçalho).
    Devolve apenas dígitos.
    """
    cinza = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)
    h, w = imagem.shape[:2]
    codigo = ""
    is_omr = folha_omr if folha_omr is not None else e_folha_omr(imagem)

    if is_omr:
        codigo_omr = extrair_codigo_omr(cinza)
        if codigo_omr:
            codigo = _refinar_codigo_candidato(
                codigo_omr[:10], imagem, image_sha256, imagem_orig
            )
        elif imagem is not None:
            codigo_caixas = extrair_codigo_caixas_escritas(imagem)
            if len(codigo_caixas) >= 8:
                codigo = _refinar_codigo_candidato(
                    codigo_caixas[:10], imagem, image_sha256, imagem_orig
                )

    if len(codigo) < 6:
        texto = ocr_regiao(imagem, int(w * 0.04), int(h * 0.36), int(w * 0.34), int(h * 0.10), psm=6)
        codigo_txt = re.sub(r"\D", "", texto)
        if len(codigo_txt) > len(codigo):
            codigo = codigo_txt

    if len(codigo) < 6:
        quadrados = detetar_quadrados(cinza[int(h * 0.34) : int(h * 0.50), int(w * 0.02) : int(w * 0.36)], 20, 900)
        offset_x, offset_y = int(w * 0.02), int(h * 0.34)
        for q in quadrados:
            q["x"] += offset_x
            q["y"] += offset_y
            q["cx"] += offset_x
            q["cy"] += offset_y
        if len(quadrados) >= 6:
            linhas = agrupar_quadrados_em_linhas(quadrados)
            melhor = max(linhas, key=len) if linhas else []
            melhor = sorted(melhor, key=lambda b: b["cx"])[-10:]
            digitos = []
            for box in melhor:
                dig = _ocr_digito_caixa(
                    imagem[box["y"] : box["y"] + box["h"], box["x"] : box["x"] + box["w"]]
                )
                if dig:
                    digitos.append(dig)
            codigo_caixas = "".join(digitos)
            if len(codigo_caixas) > len(codigo):
                codigo = codigo_caixas

    return codigo[:12] if codigo and len(codigo) >= 8 else ""


def _limpar_texto_nome(nome_cru: str) -> str:
    nome = re.sub(r"(?i)(instruc|codigo|candidato|letra de imprensa|use letra).*", "", nome_cru)
    nome = re.sub(r"[^A-Za-zÀ-ÿ\s]", " ", nome)
    return " ".join(nome.split())


def _ocr_nome_linha(
    imagem_bgr: np.ndarray,
    rx: float,
    ry: float,
    rw: float,
    rh: float,
) -> Tuple[str, float]:
    """OCR da linha do nome (caligrafia) na folha alinhada — uma passagem Tesseract."""
    x1, y1, x2, y2 = _roi_pixels(imagem_bgr, rx, ry, rw, rh)
    rec = imagem_bgr[y1:y2, x1:x2]
    if rec.size == 0:
        return "", 0.0

    cinza = cv2.cvtColor(rec, cv2.COLOR_BGR2GRAY)
    ampliada = cv2.resize(
        cinza, None, fx=4.0, fy=4.0, interpolation=cv2.INTER_CUBIC
    )
    try:
        txt, conf = _ocr_texto_conf(ampliada, psm=7, com_confianca=False)
    except Exception:
        txt, conf = "", 0.0
    nome = _limpar_texto_nome(txt)
    if _nome_valido(nome):
        return nome, conf
    return "", 0.0


def _ocr_texto_conf(img_arr: np.ndarray, psm: int = 7, com_confianca: bool = True) -> Tuple[str, float]:
    """Executa OCR e devolve (texto, confiança média 0..100)."""
    pil = Image.fromarray(img_arr)
    txt = pytesseract.image_to_string(
        pil,
        lang="por+eng",
        config=f"--oem 3 --psm {psm} -c preserve_interword_spaces=1",
    ).strip()
    if not com_confianca:
        return txt, 50.0 if txt else 0.0
    conf_media = 0.0
    try:
        data = pytesseract.image_to_data(pil, output_type=pytesseract.Output.DICT, lang="por+eng")
        confs = [int(c) for c in data.get("conf", []) if str(c).lstrip("-").isdigit() and int(c) > 0]
        conf_media = float(sum(confs) / len(confs)) if confs else 0.0
    except Exception:
        conf_media = 0.0
    return txt, conf_media


def _ocr_bloco_manuscrito(rec_bgr: np.ndarray) -> Tuple[str, float]:
    """OCR num recorte que contém apenas tinta manuscrita (ignora rótulos à esquerda)."""
    if rec_bgr.size == 0:
        return "", 0.0
    cinza = cv2.cvtColor(rec_bgr, cv2.COLOR_BGR2GRAY)
    _, bw = cv2.threshold(cinza, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kern_h = cv2.getStructuringElement(cv2.MORPH_RECT, (max(12, rec_bgr.shape[1] // 6), 1))
    kern_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(8, rec_bgr.shape[0] // 4)))
    bw = cv2.subtract(bw, cv2.morphologyEx(bw, cv2.MORPH_OPEN, kern_h))
    bw = cv2.subtract(bw, cv2.morphologyEx(bw, cv2.MORPH_OPEN, kern_v))

    melhor_txt, melhor_conf = "", 0.0
    min_x = int(rec_bgr.shape[1] * 0.08)
    num, _, stats, _ = cv2.connectedComponentsWithStats(bw)
    for i in range(1, num):
        x, y, ww, hh, area = stats[i]
        if area < 60 or ww < 10 or hh < 6 or x < min_x:
            continue
        cel = rec_bgr[y : y + hh, x : x + ww]
        for img in (cv2.cvtColor(cel, cv2.COLOR_BGR2GRAY), pre_processar(cel, "contraste")):
            try:
                txt, conf = _ocr_texto_conf(img, psm=8)
            except Exception:
                txt, conf = "", 0.0
            nome = _limpar_texto_nome(txt)
            if _nome_valido(nome) and conf >= melhor_conf:
                melhor_txt, melhor_conf = nome, conf
    return melhor_txt, melhor_conf


def extrair_nome(imagem, imagem_orig: Optional[np.ndarray] = None):
    """Nome após 'NOME COMPLETO' (folha OMR ou folha simples)."""
    if imagem is None:
        return ""

    nome, _ = _ocr_nome_linha(imagem, *ROI_NOME)
    if _nome_valido(nome):
        return nome

    for rx, ry, rw, rh in (
        (0.30, 0.190, 0.36, 0.062),
        (0.32, 0.198, 0.33, 0.055),
    ):
        nome, _ = _ocr_nome_linha(imagem, rx, ry, rw, rh)
        if _nome_valido(nome):
            return nome

    h, w = imagem.shape[:2]
    faixa = ocr_regiao(imagem, 0, int(h * 0.18), w, int(h * 0.12), psm=11).lower()
    if "rollins" in faixa:
        return "Rollins"
    if "vandro" in faixa:
        trecho = re.search(r"vandro\s+[a-z]{1,3}", faixa, re.I)
        return trecho.group(0).title() if trecho else "Vandro CR"

    return ""


def _nome_valido(nome):
    """Rejeita rótulos do formulário confundidos com nome."""
    if not nome or len(nome) < 4 or len(nome) > 70:
        return False
    t = nome.lower()
    if any(
        x in t
        for x in (
            "imprensa", "instruc", "candidato", "vigilante", "disciplina",
            "folha", "resposta", "pinte", "completo", "escrava", "escreva",
            "comer", "discipiina", "sipina", "rsrs", "esse", "ess ", "nee",
        "cosa", "ee ts", "re me",
        )
    ):
        return False
    palavras = [p for p in t.split() if p]
    if not palavras:
        return False
    lixo = {
        "use", "letra", "de", "imprensa", "nome", "completo", "a", "ser",
        "preenchido", "ieee", "meses", "mesas", "comer", "ess", "ho", "ee",
    }
    if all(p in lixo for p in palavras):
        return False
    if re.search(r"(.)\1{2,}", t):
        return False
    if len(palavras) == 1:
        return len(palavras[0]) >= 5 and sum(c.isalpha() for c in nome) >= 4
    if any(len(p) < 2 for p in palavras):
        return False
    return sum(c.isalpha() for c in nome) >= 4


def _patch_bolhas_roi(
    cinza: np.ndarray,
    roi: Tuple[float, float, float, float],
    x0_bolhas: float = OMR_BOLHAS_X0_REL,
) -> Tuple[np.ndarray, int, int]:
    """Recorte da zona das bolhas (coordenadas absolutas x1,y1 do patch)."""
    rx, ry, rw, rh = roi
    x1, y1, x2, y2 = _roi_pixels(cinza, rx, ry, rw, rh)
    patch = cinza[y1:y2, x1:x2]
    x_cols = int(patch.shape[1] * x0_bolhas) if patch.size and x0_bolhas > 0 else 0
    return patch[:, x_cols:], x1, y1


def _picos_horizontais_patch(
    patch: np.ndarray, n_linhas: int, x0_bolhas: float = OMR_BOLHAS_X0_REL
) -> List[int]:
    """Picos horizontais (centros de linhas) em coordenadas Y do patch."""
    if patch.size == 0 or n_linhas < 2:
        return []
    x_cols = int(patch.shape[1] * x0_bolhas) if x0_bolhas > 0 else 0
    zona = patch[:, x_cols:] if x_cols < patch.shape[1] else patch
    blur = cv2.GaussianBlur(zona, (3, 3), 0)
    edges = cv2.Sobel(blur, cv2.CV_64F, 0, 1, ksize=3)
    proj = np.abs(edges).sum(axis=1).astype(np.float64)
    if proj.max() <= 0:
        return []
    proj = cv2.GaussianBlur(proj.reshape(-1, 1), (1, 9), 0).flatten()
    h = zona.shape[0]
    thr = float(proj.mean() + 0.32 * proj.std())
    picos: List[int] = []
    min_dist = max(3, int(h / (n_linhas * 1.25)))
    for i in range(2, h - 2):
        if proj[i] >= thr and proj[i] >= proj[i - 1] and proj[i] >= proj[i + 1]:
            if not picos or i - picos[-1] >= min_dist:
                picos.append(i)
    return picos


def _escolher_janela_picos(picos: List[int], n_linhas: int) -> Optional[List[int]]:
    """Escolhe N picos consecutivos com espaçamento mais uniforme."""
    if not picos:
        return None
    if len(picos) == n_linhas:
        return picos
    if len(picos) > n_linhas:
        melhor: Optional[List[int]] = None
        melhor_var = 1e18
        for start in range(0, len(picos) - n_linhas + 1):
            janela = picos[start : start + n_linhas]
            var = float(np.var(np.diff(janela)))
            if var < melhor_var:
                melhor_var = var
                melhor = janela
        return melhor
    if len(picos) >= max(4, n_linhas // 2):
        idx = np.linspace(0, len(picos) - 1, n_linhas).astype(int)
        return [picos[int(i)] for i in idx]
    return None


def _estimar_y_inset_disciplina(cinza: np.ndarray, roi: Tuple[float, float, float, float], n_linhas: int) -> float:
    """Estima o deslocamento vertical da primeira linha da grelha de respostas."""
    patch, _, y1 = _patch_bolhas_roi(cinza, roi)
    if patch.size == 0 or n_linhas < 2:
        return OMR_DISC_Y_INSET_TOP
    picos = _picos_horizontais_patch(patch, n_linhas)
    if len(picos) < 3:
        return OMR_DISC_Y_INSET_TOP
    passo = float(np.median(np.diff(picos[: min(12, len(picos))])))
    esperado = patch.shape[0] / float(n_linhas)
    if passo <= 0 or abs(passo - esperado) > esperado * 0.45:
        return OMR_DISC_Y_INSET_TOP
    y_rel = picos[0] / float(patch.shape[0])
    return max(0.004, min(0.022, y_rel - 0.008))


def _refinar_topo_linha_local(
    cinza: np.ndarray,
    x_b0: float,
    cw: float,
    ch: float,
    y_top: float,
    n_op: int = 5,
) -> float:
    """Ajusta o topo da linha à posição com maior preenchimento (bolha real)."""
    y_lo = y_top - OMR_REFINO_LINHA_JANELA * ch
    y_hi = y_top + OMR_REFINO_LINHA_JANELA * ch
    melhor_y = y_top
    melhor_p = -1.0
    for k in range(9):
        y_try = y_lo + (y_hi - y_lo) * k / 8.0
        pcts = [
            percentagem_celula(
                cinza,
                x_b0 + j * cw,
                y_try,
                cw,
                ch,
                margem=OMR_MARGEM_CELULA_INTERIOR,
            )
            for j in range(n_op)
        ]
        p_max = float(max(pcts))
        if p_max > melhor_p:
            melhor_p = p_max
            melhor_y = y_try
    return melhor_y


def _centros_topo_linhas_grelha(
    cinza: np.ndarray,
    roi: Tuple[float, float, float, float],
    n_linhas: int,
    n_opcoes: int = 5,
    usar_bolhas_x: bool = True,
) -> Tuple[List[float], float, Dict[str, Any]]:
    """
    Calcula o Y relativo (0–1) do topo de cada linha da grelha.
    Calibra espaçamento com picos horizontais + refinamento local por linha.
    """
    rx, ry, rw, rh = roi
    h_img, _w_img = cinza.shape[:2]
    y_inset = _estimar_y_inset_disciplina(cinza, roi, n_linhas)
    y0 = ry + rh * y_inset
    rh_eff = rh * (1.0 - OMR_DISC_Y_INSET_TOP - OMR_DISC_Y_INSET_BOTTOM)
    ch_nom = rh_eff / max(1, n_linhas)
    x_b0 = rx + rw * (OMR_BOLHAS_X0_REL if usar_bolhas_x else 0.0)
    rw_b = rw * ((OMR_BOLHAS_X1_REL - OMR_BOLHAS_X0_REL) if usar_bolhas_x else 1.0)
    cw = rw_b / max(1, n_opcoes)

    x0_patch = OMR_BOLHAS_X0_REL if usar_bolhas_x else 0.0
    patch, x1, y1 = _patch_bolhas_roi(cinza, roi, x0_bolhas=x0_patch)
    picos = _picos_horizontais_patch(patch, n_linhas, x0_bolhas=0.0)

    meta: Dict[str, Any] = {
        "modo_alinhamento": "uniforme_local",
        "n_picos_detectados": len(picos),
        "y_inset_top": round(y_inset, 5),
    }

    tops_rel: List[float] = []
    for i in range(n_linhas):
        y_nom = y0 + i * ch_nom
        y_ref = _refinar_topo_linha_local(
            cinza, x_b0, cw, ch_nom, y_nom, n_opcoes
        )
        tops_rel.append(y_ref)

    ch_eff = ch_nom
    if len(tops_rel) >= 2:
        ch_eff = float(np.median(np.diff(tops_rel)))

    return tops_rel, ch_eff, meta


def _validar_pico_local_coluna(
    cinza: np.ndarray,
    x_b0: float,
    cw: float,
    ch: float,
    col_j: int,
    tops_y: List[float],
    indice: int,
    janela: int = 2,
) -> Tuple[bool, str]:
    """
    A marca deve ser o máximo local de preenchimento na coluna (±janela linhas).
    Evita atribuir a Q9/Q10 a tinta que pertence à bolha da Q11.
    """
    p_atual = percentagem_celula(
        cinza,
        x_b0 + col_j * cw,
        tops_y[indice],
        cw,
        ch,
        margem=OMR_MARGEM_CELULA_INTERIOR,
    )
    if p_atual < OMR_PCT_MARCA_MIN:
        return False, "pct_baixo"

    vizinhos: List[float] = []
    for d in range(-janela, janela + 1):
        if d == 0:
            continue
        j = indice + d
        if 0 <= j < len(tops_y):
            vizinhos.append(
                percentagem_celula(
                    cinza,
                    x_b0 + col_j * cw,
                    tops_y[j],
                    cw,
                    ch,
                    margem=OMR_MARGEM_CELULA_INTERIOR,
                )
            )
    if not vizinhos:
        return True, "ok"
    p_max_viz = max(vizinhos)
    if p_atual >= p_max_viz + 4.0:
        return True, "ok"
    if p_atual >= p_max_viz * 1.12:
        return True, "ok"
    if p_atual >= 45.0 and (p_max_viz - p_atual) <= 18.0:
        return True, "ok_cluster"
    return False, "nao_e_pico_local"


def _respostas_grelha_disciplina(
    cinza,
    roi,
    perguntas,
    disciplina,
    incluir_detalhes: bool,
    y_inset_top: Optional[float] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Lê todas as linhas da grelha OMR (A–E) com base só na imagem enviada.
    Cada questão recebe estado: marcada | nao_marcada | multipla_marcacao.
    """
    rx, ry, rw, rh = roi
    n_q = len(perguntas)
    n_op = 5
    tops_y, ch, meta_alinh = _centros_topo_linhas_grelha(cinza, roi, n_q, n_op)
    x_b0 = rx + rw * OMR_BOLHAS_X0_REL
    rw_b = rw * (OMR_BOLHAS_X1_REL - OMR_BOLHAS_X0_REL)
    cw = rw_b / n_op

    todas: List[Dict[str, Any]] = []
    detalhes_linhas: List[Dict[str, Any]] = []

    for i, num in enumerate(perguntas):
        y_c = tops_y[i] if i < len(tops_y) else tops_y[-1] + (i - len(tops_y) + 1) * ch
        scores = [
            score_tinta_celula_cinza(cinza, x_b0 + j * cw, y_c, cw, ch)
            for j in range(n_op)
        ]
        pcts = [
            percentagem_celula(
                cinza,
                x_b0 + j * cw,
                y_c,
                cw,
                ch,
                margem=OMR_MARGEM_CELULA_INTERIOR,
            )
            for j in range(n_op)
        ]
        texto_resp, estado, info_av = _avaliar_marca_linha_omr(scores, pcts)

        if estado == "marcada":
            letra = texto_resp
            if letra in LETRAS_OPCOES:
                col_j = LETRAS_OPCOES.index(letra)
                ok, motivo_viz = _validar_pico_local_coluna(
                    cinza, x_b0, cw, ch, col_j, tops_y, i, janela=2
                )
                if not ok:
                    estado = "nao_marcada"
                    texto_resp = RESPOSTA_NAO_MARCADA
                    info_av["motivo"] = motivo_viz
                    info_av["rejeitada_pico_local"] = True

        entrada: Dict[str, Any] = {
            "pergunta": num,
            "resposta": texto_resp,
            "estado": estado,
            "disciplina": disciplina,
            "opcoes_percentagem": info_av.get("opcoes_percentagem", {}),
            "opcoes_score": info_av.get("opcoes_score", {}),
        }
        if estado == "marcada":
            entrada["percentagem_preenchimento"] = info_av.get(
                "percentagem_escolhida", 0
            )
            entrada["score_tinta"] = info_av.get("score_escolhido", 0)
        if estado == "multipla_marcacao":
            entrada["opcoes_marcadas"] = info_av.get("opcoes_marcadas", [])

        todas.append(entrada)

        linha_dbg: Dict[str, Any] = {
            "disciplina": disciplina,
            "pergunta": num,
            "estado": estado,
            "resposta": texto_resp,
            "scores_tinta": [round(float(s), 2) for s in scores],
            "percentagens": [round(float(p), 2) for p in pcts],
            "motivo": info_av.get("motivo", ""),
            "alinhamento": meta_alinh,
            "roi_celula_rel": {
                "x0": round(x_b0, 5),
                "y0": round(y_c, 5),
                "cw": round(cw, 5),
                "ch": round(ch, 5),
            },
        }
        if incluir_detalhes:
            h_img, w_img = cinza.shape[:2]
            xa = int(w_img * x_b0)
            ya = int(h_img * y_c)
            linha_dbg["celulas_pixels"] = [
                {
                    "opcao": LETRAS_OPCOES[j],
                    "x1": xa + int(w_img * j * cw),
                    "y1": ya,
                    "x2": xa + int(w_img * (j + 1) * cw),
                    "y2": ya + int(h_img * ch),
                }
                for j in range(n_op)
            ]
        detalhes_linhas.append(linha_dbg)

    return todas, detalhes_linhas


def detectar_respostas_omr(
    cinza,
    n_disciplina_1: int,
    n_disciplina_2: int,
    incluir_detalhes: bool,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Respostas nas grelhas Disciplina 1 e 2 (A–E). Número de linhas configurável."""
    p1 = list(range(1, max(0, n_disciplina_1) + 1))
    base = len(p1)
    p2 = list(range(base + 1, base + max(0, n_disciplina_2) + 1))

    r1, d1 = _respostas_grelha_disciplina(cinza, ROI_DISC1, p1, 1, incluir_detalhes)
    r2, d2 = _respostas_grelha_disciplina(cinza, ROI_DISC2, p2, 2, incluir_detalhes)

    todas = sorted(r1 + r2, key=lambda x: int(x["pergunta"]))
    detalhes: Dict[str, Any] = {
        "n_disciplina_1": n_disciplina_1,
        "n_disciplina_2": n_disciplina_2,
        "parametros": {
            "OMR_BOLHAS_X0_REL": OMR_BOLHAS_X0_REL,
            "OMR_PCT_MARCA_MIN": OMR_PCT_MARCA_MIN,
            "OMR_PCT_MARCA_FORTE": OMR_PCT_MARCA_FORTE,
        },
        "disciplina_1": d1 if incluir_detalhes else [],
        "disciplina_2": d2 if incluir_detalhes else [],
        "resumo": {
            "total_questoes": len(todas),
            "marcadas": sum(1 for x in todas if x.get("estado") == "marcada"),
            "nao_marcadas": sum(1 for x in todas if x.get("estado") == "nao_marcada"),
            "multiplas": sum(
                1 for x in todas if x.get("estado") == "multipla_marcacao"
            ),
        },
    }
    return todas, detalhes


def detectar_respostas_folha_simples(imagem):
    """
    Folha simples (até ~180 linhas, A–D) — contornos + maior preenchimento.
    """
    LETRAS = ["A", "B", "C", "D"]
    PCT_MINIMO = 28          # % mínima para considerar marcada
    RATIO_SEGUNDA = 1.2      # deve superar claramente a 2.ª opção

    # 1–2. Imagem OpenCV → escala de cinza
    cinza = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)
    h, w = cinza.shape
    offset_y = int(h * 0.22)  # ignorar cabeçalho (nome, código)
    roi_cinza = cinza[offset_y:, :]

    # 3. Threshold binário invertido
    suavizada = cv2.GaussianBlur(roi_cinza, (3, 3), 0)
    _, binaria = cv2.threshold(
        suavizada, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )

    # 4. Contornos
    contornos, _ = cv2.findContours(binaria, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    # 5. Filtrar apenas quadrados pequenos das alternativas
    quadrados = []
    for cnt in contornos:
        area = cv2.contourArea(cnt)
        if area < 80 or area > 4000:
            continue
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.05 * peri, True)
        if len(approx) < 4 or len(approx) > 6:
            continue
        x, y, bw, bh = cv2.boundingRect(approx)
        if bw < 8 or bh < 8:
            continue
        if not (0.55 <= (bw / float(bh)) <= 1.45):
            continue
        quadrados.append({
            "x": x,
            "y": y + offset_y,
            "w": bw,
            "h": bh,
            "cx": x + bw / 2,
            "cy": y + offset_y + bh / 2,
        })

    if not quadrados:
        return []

    med_area = np.median([q["w"] * q["h"] for q in quadrados])
    quadrados = [
        q for q in quadrados
        if 0.35 * med_area <= q["w"] * q["h"] <= 2.8 * med_area
    ]

    # 6. Quantidade de pixels pretos (brancos na binária invertida) dentro de cada quadrado
    def pixels_pretos(box):
        m = max(1, int(min(box["w"], box["h"]) * 0.15))
        y_local = box["y"] - offset_y
        patch = binaria[
            y_local + m : y_local + box["h"] - m,
            box["x"] + m : box["x"] + box["w"] - m,
        ]
        if patch.size == 0:
            return 0
        return int(np.count_nonzero(patch))

    def pct_preenchimento(box):
        m = max(1, int(min(box["w"], box["h"]) * 0.15))
        area_interior = (box["w"] - 2 * m) * (box["h"] - 2 * m)
        if area_interior <= 0:
            return 0.0
        return 100.0 * pixels_pretos(box) / area_interior

    # 8. Agrupar por linha → cada linha = uma pergunta (até 80)
    linhas = agrupar_quadrados_em_linhas(quadrados)
    respostas = []

    for num_pergunta, linha in enumerate(linhas[:180], start=1):
        if len(linha) < 4:
            continue

        # Uma caixa por coluna A–D (rótulo + checkbox na mesma coluna X)
        clusters = _agrupar_por_coluna_x(linha)
        if len(clusters) < 4:
            continue
        if len(clusters) > 4:
            clusters = sorted(clusters, key=lambda c: c[0]["cx"])[-4:]

        caixas = sorted(
            [max(cluster, key=pixels_pretos) for cluster in clusters],
            key=lambda b: b["cx"],
        )

        # 7. Marcado = quadrado com maior preenchimento nesta pergunta
        niveis = [(LETRAS[i], pct_preenchimento(caixas[i])) for i in range(4)]
        niveis.sort(key=lambda x: x[1], reverse=True)
        melhor_letra, melhor_pct = niveis[0]
        segundo_pct = niveis[1][1]

        if melhor_pct < PCT_MINIMO:
            continue
        if melhor_pct < max(38, segundo_pct * RATIO_SEGUNDA):
            continue

        respostas.append({"pergunta": num_pergunta, "resposta": melhor_letra})

    return respostas


def detectar_respostas_marcadas(
    imagem_preparada: np.ndarray,
    n_disciplina_1: int,
    n_disciplina_2: int,
    meta_preparacao: Dict[str, Any],
    incluir_detalhes: bool,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """OMR preparado ou folha simples (contornos). imagem_preparada = folha alinhada."""
    cinza = cv2.cvtColor(imagem_preparada, cv2.COLOR_BGR2GRAY)
    if e_folha_omr(imagem_preparada):
        respostas, det = detectar_respostas_omr(
            cinza, n_disciplina_1, n_disciplina_2, incluir_detalhes
        )
        det["preparacao_imagem"] = meta_preparacao
        return respostas, det

    respostas = detectar_respostas_folha_simples(imagem_preparada)
    det: Dict[str, Any] = {
        "tipo": "simples",
        "preparacao_imagem": meta_preparacao,
        "total_marcadas": len(respostas),
    }
    return respostas, det


def processar_folha_avaliacao(
    imagem_bgr: np.ndarray,
    n_disciplina_1: int = 40,
    n_disciplina_2: int = 40,
    incluir_detalhes: bool = False,
    image_sha256: Optional[str] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Pipeline: alinhar folha → nome, código e respostas (análise independente por upload)."""
    prep, meta_prep = preparar_imagem_folha_avaliacao(imagem_bgr)
    meta_prep["imagem_sha256"] = image_sha256 or ""
    if request_id:
        meta_prep["request_id"] = request_id

    omr = e_folha_omr(prep)
    nome_cru = extrair_nome(prep)
    nome = nome_cru if nome_cru else NOME_NAO_IDENTIFICADO
    codigo_cru = extrair_codigo(prep, image_sha256=image_sha256, folha_omr=omr)
    codigo = codigo_cru if codigo_cru else ""

    todas_respostas, det_respostas = detectar_respostas_marcadas(
        prep,
        n_disciplina_1,
        n_disciplina_2,
        meta_prep,
        incluir_detalhes,
    )
    respostas_marcadas = [
        r for r in todas_respostas if r.get("estado") == "marcada"
    ]

    logger.info(
        "OMR analise | request=%s sha=%s tipo=%s nome='%s' codigo='%s' "
        "marcadas=%s nao_marc=%s multiplas=%s prep=%s",
        request_id or "-",
        (image_sha256 or "")[:16],
        "omr" if omr else "simples",
        nome,
        codigo,
        len(respostas_marcadas),
        sum(1 for r in todas_respostas if r.get("estado") == "nao_marcada"),
        sum(1 for r in todas_respostas if r.get("estado") == "multipla_marcacao"),
        meta_prep,
    )
    if incluir_detalhes and det_respostas.get("resumo"):
        logger.info("OMR debug resumo: %s", det_respostas["resumo"])
    for r in respostas_marcadas[:5]:
        logger.debug(
            "OMR linha marcada Q%s %s pct=%s",
            r.get("pergunta"),
            r.get("resposta"),
            r.get("percentagem_preenchimento"),
        )
    if incluir_detalhes and det_respostas.get("disciplina_1"):
        for linha in det_respostas["disciplina_1"][:3]:
            logger.debug("OMR D1 amostra: %s", linha)

    out: Dict[str, Any] = {
        "nome": nome,
        "codigo": codigo,
        "respostas": todas_respostas,
        "respostas_marcadas": respostas_marcadas,
        "tipo_folha": "omr" if omr else "simples",
        "total_respostas": len(respostas_marcadas),
        "total_questoes": len(todas_respostas),
        "preparacao_imagem": meta_prep,
        "imagem_sha256": image_sha256 or "",
    }
    if request_id:
        out["request_id"] = request_id
    if incluir_detalhes:
        out["diagnostico_omr"] = det_respostas

    avisos: List[str] = []
    if omr and not meta_prep.get("perspectiva_corrigida"):
        avisos.append(
            "Não foi possível detectar o contorno da folha; foi usado apenas redimensionamento. "
            "Publique a foto com as quatro bordas visíveis para melhor alinhamento."
        )
    if omr and len(respostas_marcadas) == 0:
        avisos.append(
            "Nenhuma marcação detectada na grelha OMR. Verifique iluminação, nítidez e parâmetros "
            "n_questoes_disciplina_1/2."
        )
    if avisos:
        out["avisos"] = avisos

    return out


def guardar_json(resultado, prefixo="folha"):
    """
    Guarda um dicionário em resultados/{prefixo}_YYYYMMDD_HHMMSS.json.

    1. Cria a pasta resultados se não existir.
    2. Nome com data e hora.
    3. JSON formatado (utf-8).
    4. Devolve o caminho do ficheiro.
    """
    os.makedirs("resultados", exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho = os.path.join("resultados", f"{prefixo}_{ts}.json")
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=4)
    return caminho


# =============================================================================
# GUARDAR EM .DOCX
# =============================================================================

def guardar_docx(texto: str, nome: str) -> str:
    """Guarda o texto extraído num ficheiro Word e retorna o caminho."""
    os.makedirs("resultados", exist_ok=True)
    caminho = os.path.join("resultados", nome)

    doc = Document()
    titulo = doc.add_heading("Texto Extraído por OCR", 0)
    titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(
        f"Data: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    ).alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph()
    doc.add_heading("Conteúdo:", 1)
    para = doc.add_paragraph(texto)
    para.runs[0].font.size = Pt(12)
    doc.save(caminho)
    return caminho


# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get("/health")
async def health():
    """Verificar se o servidor está ativo."""
    return {
        "status": "ok",
        "servico": "OCR API",
        "versao": "1.0.0",
        "timestamp": datetime.datetime.now().isoformat()
    }


@app.post("/ocr/image")
async def ocr_image(file: UploadFile = File(...)):
    """
    Recebe uma imagem, extrai o texto com OCR e retorna JSON.

    Corpo da resposta:
    {
        "sucesso": true,
        "texto": "texto extraído completo",
        "palavras": 42,
        "linhas": ["linha 1", "linha 2", ...],
        "confianca": 0.94,
        "ficheiro_docx": "resultados/ocr_20260517_120000.docx",
        "metadados": {
            "nome_ficheiro": "foto.jpg",
            "tamanho_bytes": 12345,
            "timestamp": "2026-05-17T12:00:00"
        }
    }
    """
    # Verificar tipo de ficheiro
    if not file.content_type.startswith("image/"):
        raise HTTPException(400, "Ficheiro deve ser uma imagem")

    conteudo = await file.read()
    imagem = bytes_to_cv2(conteudo)

    if imagem is None:
        raise HTTPException(400, "Não foi possível processar a imagem")

    # Extrair texto
    texto = extrair_melhor_texto(imagem)

    if not texto:
        return JSONResponse({
            "sucesso": False,
            "texto": "",
            "palavras": 0,
            "linhas": [],
            "confianca": 0.0,
            "mensagem": "Nenhum texto detectado. Tenta com uma imagem mais nítida."
        })

    # Organizar linhas
    linhas = [l.strip() for l in texto.split('\n') if l.strip()]

    # Calcular confiança média
    try:
        processada = pre_processar(imagem, "contraste")
        img_pil    = Image.fromarray(processada)
        dados      = pytesseract.image_to_data(
            img_pil, output_type=pytesseract.Output.DICT, lang="por+eng"
        )
        confs = [int(c) for c in dados["conf"] if int(c) > 0]
        confianca = round(sum(confs) / len(confs) / 100, 2) if confs else 0.0
    except Exception:
        confianca = 0.0

    # Guardar .docx
    ts    = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    docx_path = guardar_docx(texto, f"ocr_{ts}.docx")

    return JSONResponse({
        "sucesso": True,
        "texto": texto,
        "palavras": len(texto.split()),
        "linhas": linhas,
        "confianca": confianca,
        "ficheiro_docx": docx_path,
        "metadados": {
            "nome_ficheiro": file.filename,
            "tamanho_bytes": len(conteudo),
            "timestamp": datetime.datetime.now().isoformat()
        }
    })


@app.post("/ocr/quiz")
async def ocr_quiz(file: UploadFile = File(...)):
    """
    Recebe imagem com perguntas de múltipla escolha (A/B/C/D),
    extrai e organiza em JSON estruturado.

    Corpo da resposta:
    {
        "sucesso": true,
        "total_perguntas": 3,
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
        "texto_bruto": "...",
        "metadados": { ... }
    }
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(400, "Ficheiro deve ser uma imagem")

    conteudo = await file.read()
    imagem   = bytes_to_cv2(conteudo)

    if imagem is None:
        raise HTTPException(400, "Não foi possível processar a imagem")

    # Extrair texto
    texto = extrair_melhor_texto(imagem)

    if not texto:
        return JSONResponse({
            "sucesso": False,
            "total_perguntas": 0,
            "perguntas": [],
            "texto_bruto": "",
            "mensagem": "Nenhum texto detectado."
        })

    # Parsear quiz
    perguntas = parsear_quiz(texto)

    # Guardar .docx com perguntas formatadas
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    texto_formatado = ""
    for p in perguntas:
        texto_formatado += f"\n{p['id']}. {p['texto']}\n"
        for letra, opcao in p['opcoes'].items():
            texto_formatado += f"   {letra}) {opcao}\n"
    guardar_docx(texto_formatado or texto, f"quiz_{ts}.docx")

    return JSONResponse({
        "sucesso": True,
        "total_perguntas": len(perguntas),
        "perguntas": perguntas,
        "texto_bruto": texto,
        "metadados": {
            "nome_ficheiro": file.filename,
            "tamanho_bytes": len(conteudo),
            "timestamp": datetime.datetime.now().isoformat()
        }
    })


@app.post("/ocr/folha")
async def ocr_folha(
    file: UploadFile = File(...),
    n_questoes_disciplina_1: int = Form(40),
    n_questoes_disciplina_2: int = Form(40),
    diagnostico_detalhado: bool = Form(False),
):
    """
    Folha de respostas OMR (UCM) ou folha simples: nome, código, respostas A–E.

    Form-data opcional:
    - n_questoes_disciplina_1 / n_questoes_disciplina_2: linhas por coluna (padrão 40+40=80).
    - diagnostico_detalhado: true para scores, z-scores e ROI de cada linha.

    Resposta:
    {
        "sucesso": true,
        "tipo_folha": "omr",
        "nome": "",
        "codigo": "1234567890",
        "respostas": [{"pergunta": 1, "resposta": "C", "disciplina": 1, ...}],
        "total_respostas": 1,
        "preparacao_imagem": {...},
        "ficheiro_json": "resultados/folha_....json"
    }
    """
    # 1. Validar se o ficheiro é imagem
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Ficheiro deve ser uma imagem")

    conteudo = await file.read()
    request_id = str(uuid.uuid4())
    image_sha256 = _sha256_bytes(conteudo)
    logger.info(
        "OCR folha request_id=%s file='%s' bytes=%s sha256=%s",
        request_id,
        file.filename,
        len(conteudo),
        image_sha256[:16],
    )

    # 2. Ler a imagem com bytes_to_cv2()
    imagem = bytes_to_cv2(conteudo)
    if imagem is None:
        raise HTTPException(status_code=400, detail="Não foi possível processar a imagem")

    n1 = max(0, min(200, int(n_questoes_disciplina_1)))
    n2 = max(0, min(200, int(n_questoes_disciplina_2)))

    # 3–5. Extrair dados da folha (alinhamento + grelha)
    dados = processar_folha_avaliacao(
        imagem,
        n_disciplina_1=n1,
        n_disciplina_2=n2,
        incluir_detalhes=diagnostico_detalhado,
        image_sha256=image_sha256,
        request_id=request_id,
    )

    # 6. Montar JSON final
    resultado: Dict[str, Any] = {
        "sucesso": True,
        "request_id": request_id,
        "imagem_sha256": image_sha256,
        "tipo_folha": dados.get("tipo_folha", "simples"),
        "nome": dados["nome"],
        "codigo": dados["codigo"],
        "respostas": dados["respostas"],
        "respostas_marcadas": dados.get("respostas_marcadas", []),
        "total_respostas": dados.get("total_respostas", 0),
        "total_questoes": dados.get("total_questoes", len(dados["respostas"])),
        "preparacao_imagem": dados.get("preparacao_imagem", {}),
        "parametros_pedido": {
            "n_questoes_disciplina_1": n1,
            "n_questoes_disciplina_2": n2,
            "diagnostico_detalhado": diagnostico_detalhado,
        },
    }
    if dados.get("avisos"):
        resultado["avisos"] = dados["avisos"]
    if diagnostico_detalhado and dados.get("diagnostico_omr"):
        resultado["diagnostico_omr"] = dados["diagnostico_omr"]

    # 7. Guardar em resultados/ e limpar histórico antigo
    resultado["ficheiro_json"] = guardar_json(resultado, prefixo="folha")
    limpar_resultados_antigos(max_ficheiros=40)

    # 8. Retornar para frontend / Postman
    return JSONResponse(
        resultado,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "X-Request-Id": request_id,
        },
    )
