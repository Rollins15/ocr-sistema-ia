"""
Leitor OMR — folha azul UCM (único modelo).

Calibração: gabarito.json + referencia_canonica.png (FOLHA AZUL1.pdf).
Fotos da câmara podem ser P&B ou outra cor de impressão — usa escala de cinza + CLAHE.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger("uvicorn.error")

_DIR = Path(__file__).parent
_GABARITO_PATH = _DIR / "gabarito.json"

FASES_OMR = ("codigo", "disciplinas", "opcoes", "completo")
FASE_OMR_ORDEM = {"codigo": 1, "disciplinas": 2, "opcoes": 3, "completo": 4}
PROXIMA_FASE_OMR = {
    "codigo": "disciplinas",
    "disciplinas": "opcoes",
    "opcoes": None,
    "completo": None,
}

LIMIAR_ESCURO = 170
MARGEM_CELULA = 0.22
PCT_MIN_CODIGO = 11.0
PCT_MIN_CHECKBOX = 14.0
# Sub-janela interna da grelha 10x10 dentro do ROI bruto:
# remove rótulos laterais e caixas manuscritas acima da grelha.
CODIGO_GRID_X0_INSET = 0.00
CODIGO_GRID_X1_INSET = 0.98
CODIGO_GRID_Y0_INSET = 0.02
CODIGO_GRID_Y1_INSET = 0.92

# Na caixa do exame integrado, ignorar cabeçalho superior e rodapé inferior
# antes de dividir em 9 opções.
EXAME_DISC_Y_TOP_INSET = 0.06
EXAME_DISC_Y_BOTTOM_INSET = 0.11


def _carregar_gabarito() -> Dict[str, Any]:
    with open(_GABARITO_PATH, encoding="utf-8") as f:
        return json.load(f)


GAB = _carregar_gabarito()
TAMANHO_CANONICO: Tuple[int, int] = tuple(GAB["tamanho_canonica"])  # type: ignore


def normalizar_fase_omr(fase: Optional[str]) -> str:
    if not fase:
        return "codigo"
    f = str(fase).strip().lower()
    aliases = {
        "1": "codigo",
        "2": "disciplinas",
        "3": "opcoes",
        "fase1": "codigo",
        "fase2": "disciplinas",
        "fase3": "opcoes",
        "candidato": "codigo",
        "estudante": "codigo",
        "exame_integrado": "disciplinas",
        "perguntas": "opcoes",
    }
    f = aliases.get(f, f)
    return f if f in FASES_OMR else "codigo"


def _fase_atinge(fase: str, minimo: str) -> bool:
    if fase == "completo":
        return True
    return FASE_OMR_ORDEM.get(fase, 1) >= FASE_OMR_ORDEM.get(minimo, 1)


def _roi_pixels(imagem: np.ndarray, roi: List[float]) -> Tuple[int, int, int, int]:
    h, w = imagem.shape[:2]
    rx, ry, rw, rh = roi
    x1 = max(0, int(w * rx))
    y1 = max(0, int(h * ry))
    x2 = min(w, int(w * (rx + rw)))
    y2 = min(h, int(h * (ry + rh)))
    return x1, y1, x2, y2


def _cinza_folha(imagem_bgr: np.ndarray) -> np.ndarray:
    """Pré-processamento independente da cor (azul, P&B, sepia)."""
    if imagem_bgr.ndim == 2:
        cinza0 = imagem_bgr
    else:
        # Neutraliza marcações vermelhas de destaque/desenho (comuns em screenshots),
        # para não contaminar o OMR das caixas e grelhas.
        hsv = cv2.cvtColor(imagem_bgr, cv2.COLOR_BGR2HSV)
        mask_red1 = cv2.inRange(hsv, (0, 70, 70), (12, 255, 255))
        mask_red2 = cv2.inRange(hsv, (168, 70, 70), (179, 255, 255))
        mask_red = cv2.bitwise_or(mask_red1, mask_red2)
        img = imagem_bgr.copy()
        img[mask_red > 0] = (255, 255, 255)
        cinza0 = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cinza = cinza0
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(cinza)


def _ordenar_quad(pts: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1).ravel()
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def _encontrar_quad_folha(imagem_bgr: np.ndarray) -> Optional[np.ndarray]:
    h0, w0 = imagem_bgr.shape[:2]
    area_img = float(h0 * w0)
    g = _cinza_folha(imagem_bgr)
    blur = cv2.GaussianBlur(g, (5, 5), 0)
    bordas = cv2.Canny(blur, 50, 160)
    bordas = cv2.dilate(
        bordas, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)), iterations=1
    )
    cnts, _ = cv2.findContours(bordas, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        cnts = []
    proporcao = TAMANHO_CANONICO[1] / float(TAMANHO_CANONICO[0])
    for c in sorted(cnts, key=cv2.contourArea, reverse=True)[:15]:
        if cv2.contourArea(c) < 0.2 * area_img:
            continue
        peri = cv2.arcLength(c, True)
        for eps in (0.02, 0.025, 0.03, 0.035):
            approx = cv2.approxPolyDP(c, eps * peri, True)
            if len(approx) != 4:
                continue
            pts = approx.reshape(4, 2).astype(np.float32)
            rw, rh = cv2.boundingRect(pts)[2:]
            if rw < 10 or rh < 10:
                continue
            rprop = max(rw, rh) / float(min(rw, rh))
            if abs(rprop - proporcao) < 0.6:
                return pts

    # Fallback: segmentar "papel" claro (funciona mesmo em foto P&B).
    hsv = cv2.cvtColor(imagem_bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (0, 0, 110), (179, 90, 255))
    mask = cv2.morphologyEx(
        mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8), iterations=2
    )
    cnts2, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if cnts2:
        c2 = max(cnts2, key=cv2.contourArea)
        if cv2.contourArea(c2) > 0.2 * area_img:
            rect = cv2.minAreaRect(c2)
            box = cv2.boxPoints(rect).astype(np.float32)
            return box
    return None


def preparar_folha(imagem_bgr: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Alinha a folha ao tamanho canónico do PDF (funciona em foto P&B)."""
    meta: Dict[str, Any] = {
        "tamanho_original": [int(imagem_bgr.shape[1]), int(imagem_bgr.shape[0])],
        "gabarito": GAB["versao"],
    }
    img = imagem_bgr.copy()
    h, w = img.shape[:2]
    if w > h:
        img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        meta["rotacao_90"] = True
        h, w = img.shape[:2]

    quad = _encontrar_quad_folha(img)
    dst_w, dst_h = TAMANHO_CANONICO
    if quad is not None:
        rect = _ordenar_quad(quad)
        dst = np.array(
            [[0, 0], [dst_w - 1, 0], [dst_w - 1, dst_h - 1], [0, dst_h - 1]],
            dtype="float32",
        )
        m = cv2.getPerspectiveTransform(rect, dst)
        img = cv2.warpPerspective(
            img, m, (dst_w, dst_h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE
        )
        meta["perspectiva_corrigida"] = True
    else:
        img = cv2.resize(img, TAMANHO_CANONICO, interpolation=cv2.INTER_AREA)
        meta["perspectiva_corrigida"] = False

    meta["tamanho_final"] = [int(img.shape[1]), int(img.shape[0])]
    return img, meta


def _pct_escuro(cinza: np.ndarray, roi: List[float], margem: float = MARGEM_CELULA) -> float:
    x1, y1, x2, y2 = _roi_pixels(cinza, roi)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    patch = cinza[y1:y2, x1:x2]
    mh = max(1, int(patch.shape[0] * margem))
    mw = max(1, int(patch.shape[1] * margem))
    core = patch[mh:-mh, mw:-mw] if patch.shape[0] > 2 * mh and patch.shape[1] > 2 * mw else patch
    if core.size == 0:
        return 0.0
    return 100.0 * float(np.count_nonzero(core < LIMIAR_ESCURO)) / float(core.size)


def _score_tinta(cinza: np.ndarray, roi: List[float]) -> float:
    x1, y1, x2, y2 = _roi_pixels(cinza, roi)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    patch = cinza[y1:y2, x1:x2]
    mh = max(1, int(patch.shape[0] * 0.2))
    mw = max(1, int(patch.shape[1] * 0.2))
    core = patch[mh:-mh, mw:-mw] if patch.shape[0] > 2 * mh else patch
    if core.size == 0:
        return 0.0
    blur = cv2.GaussianBlur(core, (3, 3), 0)
    escuridao = 255.0 - float(np.mean(blur))
    _, bw = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    cob = 100.0 * float(np.count_nonzero(bw)) / float(bw.size)
    return escuridao * 0.62 + cob * 0.38


def _mask_tinta_sem_linhas(cinza: np.ndarray) -> np.ndarray:
    """
    Remove grelhas/linhas do formulário e devolve máscara binária da tinta.
    Útil para recortes em branco (evita falsos positivos por bordas).
    """
    if cinza.ndim != 2:
        raise ValueError("cinza deve ser 2D")
    blur = cv2.GaussianBlur(cinza, (3, 3), 0)
    _, bw = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    h, w = bw.shape[:2]
    # remove linhas horizontais e verticais (grelhas)
    kx = max(12, w // 10)
    ky = max(10, h // 12)
    kern_h = cv2.getStructuringElement(cv2.MORPH_RECT, (kx, 1))
    kern_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, ky))
    linhas_h = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kern_h)
    linhas_v = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kern_v)
    linhas = cv2.bitwise_or(linhas_h, linhas_v)
    tinta = cv2.subtract(bw, linhas)
    # limpa ruído
    tinta = cv2.morphologyEx(
        tinta, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    )
    return tinta


def _celula_relativa(
    roi_base: List[float], col: int, row: int, n_cols: int, n_rows: int
) -> List[float]:
    rx, ry, rw, rh = roi_base
    cw, ch = rw / n_cols, rh / n_rows
    return [rx + col * cw, ry + row * ch, cw, ch]


def ler_codigo_candidato(cinza: np.ndarray) -> Dict[str, Any]:
    """Grelha 10×10 — um dígito por coluna (linhas 0–9)."""
    roi_grid_raw = GAB["roi"]["codigo_bolhas_10x10"]
    rx, ry, rw, rh = roi_grid_raw
    roi_grid = [
        rx + rw * CODIGO_GRID_X0_INSET,
        ry + rh * CODIGO_GRID_Y0_INSET,
        rw * (CODIGO_GRID_X1_INSET - CODIGO_GRID_X0_INSET),
        rh * (CODIGO_GRID_Y1_INSET - CODIGO_GRID_Y0_INSET),
    ]
    n_cols, n_rows = 10, 10
    digitos: List[str] = []
    detalhe_colunas: List[Dict[str, Any]] = []

    for col in range(n_cols):
        pcts = [
            _pct_escuro(cinza, _celula_relativa(roi_grid, col, row, n_cols, n_rows))
            for row in range(n_rows)
        ]
        idx = int(np.argmax(pcts))
        pct_max = float(pcts[idx])
        scores = [
            _score_tinta(cinza, _celula_relativa(roi_grid, col, row, n_cols, n_rows))
            for row in range(n_rows)
        ]
        if pct_max >= PCT_MIN_CODIGO or scores[idx] >= 16.0:
            digitos.append(str(idx))
            detalhe_colunas.append(
                {"coluna": col + 1, "digito": idx, "pct": round(pct_max, 1)}
            )
        else:
            digitos.append("")
            detalhe_colunas.append({"coluna": col + 1, "digito": None, "pct": round(pct_max, 1)})

    codigo = "".join(d for d in digitos if d != "")
    pcts_cols = [float(c["pct"]) for c in detalhe_colunas if c.get("digito") is not None]
    media_pct = float(np.mean(pcts_cols)) if pcts_cols else 0.0
    colunas_fortes = sum(1 for p in pcts_cols if p >= 12.0)
    codigo_valido = len(codigo) >= 8 and media_pct >= 18.0 and colunas_fortes >= 8
    return {
        "codigo": codigo if codigo_valido else "",
        "codigo_valido": codigo_valido,
        "digitos": digitos,
        "colunas": detalhe_colunas,
        "media_percentagem_colunas": round(media_pct, 1),
        "colunas_fortes": colunas_fortes,
        "roi": roi_grid,
        "fonte": "grelha_10x10",
    }


def _ler_coluna_checkbox(
    cinza: np.ndarray,
    roi_col: List[float],
    nomes: List[str],
) -> Dict[str, Any]:
    n = len(nomes)
    pcts: List[float] = []
    y0 = roi_col[1] + roi_col[3] * EXAME_DISC_Y_TOP_INSET
    h_eff = roi_col[3] * (1.0 - EXAME_DISC_Y_TOP_INSET - EXAME_DISC_Y_BOTTOM_INSET)
    for i in range(n):
        cell = [
            roi_col[0],
            y0 + h_eff * (i / n),
            roi_col[2],
            h_eff / n,
        ]
        pcts.append(_pct_escuro(cinza, cell, margem=0.18))

    ordenado = sorted(enumerate(pcts), key=lambda x: x[1], reverse=True)
    i0, p0 = ordenado[0]
    i1, p1 = ordenado[1] if len(ordenado) > 1 else (0, 0.0)

    marcada = None
    estado = "nao_marcada"
    # Limiar absoluto levemente mais baixo para fotos com marca suave,
    # mantendo separação forte para evitar falso positivo em folha em branco.
    if p0 >= 10.0 and (p0 >= p1 * 1.35 or (p0 - p1) >= 5.0):
        marcada = nomes[i0]
        estado = "marcada"
    elif p0 >= 10.0 and p1 >= 10.0 and p0 < p1 * 1.35:
        estado = "multipla_marcacao"

    linhas = [
        {
            "indice": i + 1,
            "nome": nomes[i],
            "percentagem_preenchimento": round(pcts[i], 1),
            "marcada": i == i0 and estado == "marcada",
        }
        for i in range(n)
    ]
    return {
        "disciplina_escolhida": marcada,
        "indice_escolhido": (i0 + 1) if estado == "marcada" else None,
        "estado": estado,
        "linhas": linhas,
    }


def ler_exame_integrado(cinza: np.ndarray) -> Dict[str, Any]:
    """Listas de checkboxes — Disciplina 1 e 2 (abaixo do código)."""
    roi1 = GAB["roi"]["exame_integrado_disciplina_1"]
    roi2 = GAB["roi"]["exame_integrado_disciplina_2"]
    nomes1 = GAB["exame_integrado"]["disciplina_1"]
    nomes2 = GAB["exame_integrado"]["disciplina_2"]

    d1 = _ler_coluna_checkbox(cinza, roi1, nomes1)
    d2 = _ler_coluna_checkbox(cinza, roi2, nomes2)
    d1["rotulo"] = "Exame integrado — Disciplina 1"
    d2["rotulo"] = "Exame integrado — Disciplina 2"

    return {
        "descricao": "Seleção de disciplinas do exame integrado (retângulo esquerdo da folha)",
        "disciplina_1": d1,
        "disciplina_2": d2,
    }


def ler_respostas_grelha(
    cinza: np.ndarray,
    n1: int,
    n2: int,
) -> Dict[str, Any]:
    """Fase 3 — grelha A–E (colunas direita). Implementação mínima; calibrar depois."""
    return {
        "aviso": "Grelha 1–80 em calibração fina no gabarito folha_azul.",
        "respostas": [],
        "respostas_marcadas": [],
        "total_questoes": n1 + n2,
    }


def ler_codigo_candidato_de_crop(codigo_bolhas_bgr: np.ndarray) -> Dict[str, Any]:
    """
    Versão para debug: recebe o crop apenas da grelha 10x10 (sem ROI),
    e divide diretamente em 10x10 células.
    """
    cinza = _cinza_folha(codigo_bolhas_bgr)
    h, w = cinza.shape[:2]
    n_cols, n_rows = 10, 10

    digitos: List[str] = []
    detalhe_colunas: List[Dict[str, Any]] = []

    for col in range(n_cols):
        escuridoes: List[float] = []
        for row in range(n_rows):
            # ROI normalizado dentro do crop
            roi = [
                (col / n_cols),
                (row / n_rows),
                1.0 / n_cols,
                1.0 / n_rows,
            ]
            x1, y1, x2, y2 = _roi_pixels(cinza, roi)
            patch = cinza[y1:y2, x1:x2]
            # usa só o centro da bolha (ignora bordas retangulares)
            mh = max(1, int(patch.shape[0] * 0.35))
            mw = max(1, int(patch.shape[1] * 0.35))
            core = (
                patch[mh:-mh, mw:-mw]
                if patch.shape[0] > 2 * mh and patch.shape[1] > 2 * mw
                else patch
            )
            if core.size == 0:
                escuridoes.append(0.0)
            else:
                escuridoes.append(255.0 - float(np.mean(core)))

        idx = int(np.argmax(escuridoes))
        esc_max = float(escuridoes[idx])
        med = float(np.median(escuridoes))
        ordenadas = sorted(escuridoes, reverse=True)
        esc_seg = float(ordenadas[1]) if len(ordenadas) > 1 else 0.0
        gap_top2 = esc_max - esc_seg
        delta = esc_max - med

        # Critério mais rígido para evitar dígitos espúrios em folha em branco.
        # Exige que a linha vencedora seja claramente mais escura que o 2.º lugar
        # e também muito acima da mediana da coluna.
        if esc_max >= 35.0 and delta >= 16.0 and gap_top2 >= 14.0:
            digitos.append(str(idx))
            detalhe_colunas.append(
                {"coluna": col + 1, "digito": idx, "pct": round(esc_max, 1)}
            )
        else:
            digitos.append("")
            detalhe_colunas.append({"coluna": col + 1, "digito": None, "pct": round(esc_max, 1)})

    codigo = "".join(d for d in digitos if d != "")

    pcts_cols = [float(c["pct"]) for c in detalhe_colunas if c.get("digito") is not None]
    media_pct = float(np.mean(pcts_cols)) if pcts_cols else 0.0
    colunas_fortes = sum(1 for p in pcts_cols if p >= 12.0)
    codigo_valido = len(codigo) >= 8 and media_pct >= 18.0 and colunas_fortes >= 8

    return {
        "codigo": codigo if codigo_valido else "",
        "codigo_valido": codigo_valido,
        "digitos": digitos,
        "colunas": detalhe_colunas,
        "media_percentagem_colunas": round(media_pct, 1),
        "colunas_fortes": colunas_fortes,
        "fonte": "debug_crop_grelha_10x10",
        "dimensoes_crop": [int(w), int(h)],
    }


def ler_exame_integrado_disciplina_de_crop(
    disciplina_crop_bgr: np.ndarray,
    nomes: List[str],
) -> Dict[str, Any]:
    """
    Versão para debug: recebe o crop apenas da coluna de checkboxes
    (9 opções) e divide verticalmente em n opções.
    """
    cinza = _cinza_folha(disciplina_crop_bgr)
    h, w = cinza.shape[:2]
    tinta = _mask_tinta_sem_linhas(cinza)
    n = len(nomes)
    pcts: List[float] = []
    for i in range(n):
        # só a zona direita onde estão as caixas (evita texto à esquerda)
        roi = [0.72, i / n, 0.28, 1.0 / n]
        x1, y1, x2, y2 = _roi_pixels(tinta, roi)
        patch = tinta[y1:y2, x1:x2]
        mh = max(1, int(patch.shape[0] * 0.25))
        mw = max(1, int(patch.shape[1] * 0.25))
        core = (
            patch[mh:-mh, mw:-mw]
            if patch.shape[0] > 2 * mh and patch.shape[1] > 2 * mw
            else patch
        )
        pct = 100.0 * float(np.count_nonzero(core)) / float(core.size) if core.size else 0.0
        pcts.append(pct)

    ordenado = sorted(enumerate(pcts), key=lambda x: x[1], reverse=True)
    i0, p0 = ordenado[0]
    i1, p1 = ordenado[1] if len(ordenado) > 1 else (0, 0.0)

    marcada = None
    estado = "nao_marcada"
    if p0 >= 1.0 and p0 >= max(p1 * 1.6, p1 + 0.8):
        marcada = nomes[i0]
        estado = "marcada"
    elif p0 >= 1.0 and p1 >= 1.0 and p0 < p1 * 1.6:
        estado = "multipla_marcacao"

    linhas = [
        {
            "indice": i + 1,
            "nome": nomes[i],
            "percentagem_preenchimento": round(pcts[i], 1),
            "marcada": i == i0 and estado == "marcada",
        }
        for i in range(n)
    ]

    return {
        "disciplina_escolhida": marcada,
        "indice_escolhido": (i0 + 1) if estado == "marcada" else None,
        "estado": estado,
        "linhas": linhas,
        "fonte": "debug_crop_disciplina",
        "dimensoes_crop": [int(w), int(h)],
    }


def processar_recortes_debug(
    debug_dir: Path,
    fase: str = "disciplinas",
) -> Dict[str, Any]:
    """
    Lê manualmente recortes colocados em debug_dir com nomes:
      - aligned.png (opcional)
      - codigo_bolhas_10x10.png
      - exame_integrado_disciplina_1.png
      - exame_integrado_disciplina_2.png

    Retorna apenas o que for relevante para a fase.
    """
    fase_norm = normalizar_fase_omr(fase)

    out: Dict[str, Any] = {
        "modelo_folha": "folha_azul_ucm",
        "debug_dir": str(debug_dir),
        "fase": fase_norm,
    }

    def _achar(nome_base: str) -> Optional[Path]:
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            p = debug_dir / f"{nome_base}{ext}"
            if p.exists():
                return p
        return None

    aligned_path = _achar("aligned")
    if aligned_path:
        out["debug_aligned_existe"] = True
        out["debug_aligned_ficheiro"] = aligned_path.name

    # Código
    if _fase_atinge(fase_norm, "codigo"):
        p_code = _achar("codigo_bolhas_10x10")
        img = cv2.imread(str(p_code)) if p_code else None
        if img is None:
            out["codigo_erro"] = "Falta codigo_bolhas_10x10.(png|jpg|jpeg|webp)"
        else:
            cod = ler_codigo_candidato_de_crop(img)
            out["codigo_candidato"] = cod
            out["codigo"] = cod["codigo"]
            out["codigo_crop_ficheiro"] = p_code.name if p_code else None

    # Disciplinas
    if _fase_atinge(fase_norm, "disciplinas"):
        p_d1 = _achar("exame_integrado_disciplina_1")
        p_d2 = _achar("exame_integrado_disciplina_2")
        img1 = cv2.imread(str(p_d1)) if p_d1 else None
        img2 = cv2.imread(str(p_d2)) if p_d2 else None
        if img1 is None:
            out["disciplina_1_erro"] = "Falta exame_integrado_disciplina_1.(png|jpg|jpeg|webp)"
        if img2 is None:
            out["disciplina_2_erro"] = "Falta exame_integrado_disciplina_2.(png|jpg|jpeg|webp)"

        if img1 is not None:
            d1 = ler_exame_integrado_disciplina_de_crop(img1, GAB["exame_integrado"]["disciplina_1"])
            d1["rotulo"] = "Exame integrado — Disciplina 1"
            d1["ficheiro_crop"] = p_d1.name if p_d1 else None
        else:
            d1 = None
        if img2 is not None:
            d2 = ler_exame_integrado_disciplina_de_crop(img2, GAB["exame_integrado"]["disciplina_2"])
            d2["rotulo"] = "Exame integrado — Disciplina 2"
            d2["ficheiro_crop"] = p_d2.name if p_d2 else None
        else:
            d2 = None

        out["exame_integrado"] = {"disciplina_1": d1, "disciplina_2": d2}

    return out


def processar_folha_azul(
    imagem_bgr: np.ndarray,
    fase: str = "codigo",
    n_disciplina_1: int = 40,
    n_disciplina_2: int = 40,
    image_sha256: Optional[str] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    fase = normalizar_fase_omr(fase)
    prep, meta_prep = preparar_folha(imagem_bgr)
    cinza = _cinza_folha(prep)

    out: Dict[str, Any] = {
        "modelo_folha": "folha_azul_ucm",
        "gabarito_versao": GAB["versao"],
        "fase": fase,
        "fases_disponiveis": list(FASES_OMR),
        "proxima_fase": PROXIMA_FASE_OMR.get(fase),
        "preparacao_imagem": meta_prep,
        "imagem_sha256": image_sha256 or "",
    }
    if request_id:
        out["request_id"] = request_id

    if _fase_atinge(fase, "codigo"):
        cod = ler_codigo_candidato(cinza)
        out["codigo_candidato"] = cod
        out["codigo"] = cod["codigo"]
        if not cod["codigo_valido"]:
            out.setdefault("avisos", []).append(
                "Código do candidato incompleto. Enquadre a grelha 10×10 e use boa luz."
            )

    if _fase_atinge(fase, "disciplinas"):
        out["exame_integrado"] = ler_exame_integrado(cinza)

    if _fase_atinge(fase, "opcoes"):
        resp = ler_respostas_grelha(cinza, n_disciplina_1, n_disciplina_2)
        out["respostas"] = resp["respostas"]
        out["respostas_marcadas"] = resp["respostas_marcadas"]
        out["total_questoes"] = resp["total_questoes"]
        if resp.get("aviso"):
            out.setdefault("avisos", []).append(resp["aviso"])

    if not meta_prep.get("perspectiva_corrigida"):
        out.setdefault("avisos", []).append(
            "Contorno da folha não detectado; usado redimensionamento. Mostre as quatro bordas na foto."
        )

    logger.info(
        "folha_azul | fase=%s codigo=%s request=%s",
        fase,
        out.get("codigo", ""),
        request_id or "-",
    )
    return out
