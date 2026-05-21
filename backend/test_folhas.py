"""Validação das folhas de teste reais (Rollins + Vandro)."""
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

ESPERADO = {
    "rollins": {
        "nome": "Rollins",
        "codigo": "1222222214",
        "respostas": {1: "A", 3: "B", 5: "C", 8: "C", 10: "C", 12: "C", 14: "A", 44: "A", 53: "A"},
    },
    "vandro": {
        "nome": "Vandro CR",
        "codigo": "1222222212",
        "respostas": {
            1: "E",
            2: "E",
            3: "E",
            4: "E",
            5: "E",
            8: "C",
            10: "C",
            11: "C",
            12: "C",
            13: "A",
            44: "B",
            53: "B",
        },
    },
}


def sha_arquivo(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def processar(path: str):
    with open(path, "rb") as f:
        raw = f.read()
    img = bytes_to_cv2(raw)
    return processar_folha_avaliacao(
        img, 40, 40, False, image_sha256=hashlib.sha256(raw).hexdigest()
    )


def validar(chave: str, path: str) -> bool:
    exp = ESPERADO[chave]
    r = processar(path)
    obt = {x["pergunta"]: x["resposta"] for x in r.get("respostas", [])}

    erros = []
    nome_obt = (r.get("nome") or "").strip()
    if not nome_obt:
        erros.append(f"nome: não lido — esperado '{exp['nome']}'")
    elif nome_obt.lower() != exp["nome"].lower():
        erros.append(f"nome: obtido '{nome_obt}' esperado '{exp['nome']}'")
    if r.get("codigo", "") != exp["codigo"]:
        erros.append(f"codigo: obtido '{r.get('codigo')}' esperado '{exp['codigo']}'")

    for q, letra in exp["respostas"].items():
        if obt.get(q) != letra:
            erros.append(f"Q{q}: obtido '{obt.get(q)}' esperado '{letra}'")

    for q, letra in obt.items():
        if q not in exp["respostas"]:
            erros.append(f"Q{q}: falso positivo '{letra}'")

    print(f"\n=== {chave.upper()} ===")
    print(f"nome={nome_obt!r} codigo={r.get('codigo')!r} total={r.get('total_respostas')}")
    print("respostas:", ", ".join(f"Q{k}={v}" for k, v in sorted(obt.items())))
    if erros:
        print("ERROS:")
        for e in erros:
            print(" -", e)
        return False
    print("OK — todos os campos conferem.")
    return True


if __name__ == "__main__":
    ok1 = validar("rollins", IMG_ROLLINS)
    ok2 = validar("vandro", IMG_VANDRO)
    sys.exit(0 if ok1 and ok2 else 1)
