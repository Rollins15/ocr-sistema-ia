"""
Leitura por recortes manuais em backend/folha_azul/debug_foto/.

Recortes esperados (mesmos nomes):
  - aligned.png (opcional)
  - codigo_bolhas_10x10.png
  - exame_integrado_disciplina_1.png
  - exame_integrado_disciplina_2.png
"""

from pathlib import Path

import cv2  # noqa: F401

from folha_azul.leitor import processar_recortes_debug


def main():
    debug_dir = Path(__file__).parent / "folha_azul" / "debug_foto"

    r1 = processar_recortes_debug(debug_dir, fase="codigo")
    print("\n=== RECORTES: CÓDIGO ===")
    print("codigo=", r1.get("codigo"))
    print("codigo_candidato=", r1.get("codigo_candidato"))

    r2 = processar_recortes_debug(debug_dir, fase="disciplinas")
    print("\n=== RECORTES: DISCIPLINAS ===")
    ei = r2.get("exame_integrado", {})
    print("disciplina_1=", (ei.get("disciplina_1") or {}).get("disciplina_escolhida"))
    print("disciplina_2=", (ei.get("disciplina_2") or {}).get("disciplina_escolhida"))
    print("raw exame_integrado=", ei)


if __name__ == "__main__":
    main()

