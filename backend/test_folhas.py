"""Validação das folhas de teste reais (Rollins + Vandro) — leitura só da imagem."""
import hashlib
import sys

sys.path.insert(0, ".")

from main import bytes_to_cv2, processar_folha_avaliacao

IMG_ROLLINS = (
    r"C:\Users\Elton\.cursor\projects\c-Users-Elton-Downloads-ocr-sistema-ia-main"
    r"\assets\c__Users_Elton_AppData_Roaming_Cursor_User_workspaceStorage_870e605bccf56e47360b2d629b4de0a5_images_teste3-1b9ba71c-a8cd-43e2-9eca-afe6a0f9c11d.png"
)
IMG_VANDRO = (
    r"C:\Users\Elton\.cursor\projects\c-Users-Elton-Downloads-ocr-sistema-ia-main"
    r"\assets\c__Users_Elton_AppData_Roaming_Cursor_User_workspaceStorage_870e605bccf56e47360b2d629b4de0a5_images_teste2-d72cd2a2-a35b-493d-80dd-a271cf3ad7a2.png"
)

# Marcações visíveis nas imagens de teste (análise visual + OCR de grelha)
ESPERADO = {
    "rollins": {
        "nome": "Rollins",
        "codigo": "1222222212",
        "marcadas": {
            1: "A",
            3: "B",
            5: "C",
            11: "C",
            12: "C",
            13: "C",
            15: "A",
            44: "A",
            54: "A",
        },
    },
    "vandro": {
        "nome": "Vandro CR",
        "codigo": "1222222212",
        "marcadas": {
            1: "E",
            2: "E",
            3: "E",
            4: "E",
            11: "C",
            12: "C",
            13: "C",
            44: "A",
            54: "A",
        },
    },
}


def processar(path: str, request_id: str):
    with open(path, "rb") as f:
        raw = f.read()
    img = bytes_to_cv2(raw)
    return processar_folha_avaliacao(
        img,
        40,
        40,
        False,
        image_sha256=hashlib.sha256(raw).hexdigest(),
        request_id=request_id,
    )


def validar(chave: str, path: str) -> bool:
    exp = ESPERADO[chave]
    r = processar(path, f"test-{chave}")
    obt_marcadas = {
        x["pergunta"]: x["resposta"]
        for x in r.get("respostas_marcadas", r.get("respostas", []))
        if x.get("estado") == "marcada"
    }

    erros = []
    nome_obt = (r.get("nome") or "").strip()
    if nome_obt != exp["nome"]:
        erros.append(f"nome: obtido '{nome_obt}' esperado '{exp['nome']}'")
    if r.get("codigo", "") != exp["codigo"]:
        erros.append(f"codigo: obtido '{r.get('codigo')}' esperado '{exp['codigo']}'")

    for q, letra in exp["marcadas"].items():
        if obt_marcadas.get(q) != letra:
            erros.append(
                f"Q{q}: obtido '{obt_marcadas.get(q)}' esperado '{letra}'"
            )

    for q, letra in obt_marcadas.items():
        if q not in exp["marcadas"]:
            erros.append(f"Q{q}: falso positivo '{letra}'")

    # Rollins e Vandro devem diferir em D1 (Q1–Q5)
    if chave == "rollins":
        pass
    print(f"\n=== {chave.upper()} ===")
    print(f"nome={nome_obt!r} codigo={r.get('codigo')!r}")
    print(
        "marcadas:",
        ", ".join(f"Q{k}={v}" for k, v in sorted(obt_marcadas.items())),
    )
    print(f"total_questoes={r.get('total_questoes')} sha={r.get('imagem_sha256','')[:12]}")
    if erros:
        print("ERROS:")
        for e in erros:
            print(" -", e)
        return False
    print("OK — leitura confere com a folha.")
    return True


def test_folhas_diferentes():
    """Mesmo modelo, respostas D1 diferentes entre estudantes."""
    r1 = processar(IMG_ROLLINS, "diff-rollins")
    r2 = processar(IMG_VANDRO, "diff-vandro")
    m1 = {x["pergunta"]: x["resposta"] for x in r1["respostas_marcadas"]}
    m2 = {x["pergunta"]: x["resposta"] for x in r2["respostas_marcadas"]}
    if m1.get(1) == m2.get(1) and m1.get(3) == m2.get(3):
        print("\nFALHA: Rollins e Vandro com mesmas respostas em Q1/Q3")
        return False
    print("\nOK — respostas D1 diferem entre folhas (upload independente).")
    return True


if __name__ == "__main__":
    ok1 = validar("rollins", IMG_ROLLINS)
    ok2 = validar("vandro", IMG_VANDRO)
    ok3 = test_folhas_diferentes()
    sys.exit(0 if ok1 and ok2 and ok3 else 1)
