"""Calibra ROIs no PDF de referência (gabarito manual assistido por contornos)."""
import json
from pathlib import Path

import cv2

REF = Path(__file__).parent / "referencia_canonica.png"
OUT = Path(__file__).parent / "gabarito.json"

W_CAN, H_CAN = 1191, 1684

DISCIPLINAS_EXAME_1 = [
    "Matemática III",
    "Matemática II",
    "Matemática III",
    "Português I",
    "Biologia II",
    "Matemática I",
    "Português III",
    "Biologia I",
    "Matemática II",
]
DISCIPLINAS_EXAME_2 = [
    "Geografia II",
    "Desenho",
    "Química II",
    "História",
    "Física II",
    "Física I",
    "Geografia I",
    "Química I",
    "Português II",
]


def main():
    img = cv2.imread(str(REF))
    h, w = img.shape[:2]
    # ROIs estabilizadas no template FOLHA AZUL1 (e validadas com foto real).
    roi_bolhas = (0.0250, 0.5300, 0.3000, 0.1600)
    roi_caixas = (0.0250, 0.4950, 0.3000, 0.0300)
    roi_exame_d1 = (0.0450, 0.7500, 0.1728, 0.1500)
    roi_exame_d2 = (0.2322, 0.7500, 0.1728, 0.1500)
    roi_resp_d1 = (0.4000, 0.2800, 0.2600, 0.6400)
    roi_resp_d2 = (0.6800, 0.2800, 0.2600, 0.6400)

    gabarito = {
        "versao": "folha_azul_1",
        "fonte_pdf": "FOLHA AZUL1.pdf",
        "tamanho_canonica": [W_CAN, H_CAN],
        "notas": (
            "Gabarito calibrado em referencia_canonica.png. Fotos P&B: CLAHE + perspectiva. "
            "Regenerar: python folha_azul/calibrar_gabarito.py"
        ),
        "roi": {
            "codigo_bolhas_10x10": [round(x, 4) for x in roi_bolhas],
            "codigo_caixas_manuscritas": [round(x, 4) for x in roi_caixas],
            "exame_integrado_disciplina_1": [round(x, 4) for x in roi_exame_d1],
            "exame_integrado_disciplina_2": [round(x, 4) for x in roi_exame_d2],
            "respostas_disciplina_1": [round(x, 4) for x in roi_resp_d1],
            "respostas_disciplina_2": [round(x, 4) for x in roi_resp_d2],
        },
        "exame_integrado": {
            "disciplina_1": DISCIPLINAS_EXAME_1,
            "disciplina_2": DISCIPLINAS_EXAME_2,
            "n_opcoes_por_coluna": len(DISCIPLINAS_EXAME_1),
        },
        "codigo": {"colunas": 10, "digitos_por_coluna": 10},
        "respostas": {
            "n_disciplina_1": 40,
            "n_disciplina_2": 40,
            "opcoes": ["A", "B", "C", "D", "E"],
        },
        "fases": ["codigo", "disciplinas", "opcoes", "completo"],
    }
    OUT.write_text(json.dumps(gabarito, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Escrito", OUT)
    print(json.dumps(gabarito["roi"], indent=2))


if __name__ == "__main__":
    main()
