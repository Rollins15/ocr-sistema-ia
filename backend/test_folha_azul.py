"""Teste do gabarito folha azul (referência PDF + foto real opcional)."""
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import cv2
from folha_azul.leitor import processar_folha_azul

REF = Path(__file__).parent / "folha_azul" / "referencia_canonica.png"
FOTO_REAL = Path(
    r"C:\Users\hp\.cursor\projects\c-Users-hp-ocr-sistema\assets"
    r"\c__Users_hp_AppData_Roaming_Cursor_User_workspaceStorage_8fca7b53e1e1f8ba641048fd943265ec_images"
    r"_WhatsApp_Image_2026-06-02_at_01.29.01-d2eaf6ec-8d90-4e06-b58a-1c3831397604.png"
)

# Gabarito manual da foto real (retângulo vermelho)
ESPERADO_FOTO = {
    "codigo": "0131350201",
    "disciplina_1": "Matemática III",
    "disciplina_2": "Química II",
}


def _load(path: Path):
    raw = path.read_bytes()
    img = cv2.imdecode(__import__("numpy").frombuffer(raw, __import__("numpy").uint8), cv2.IMREAD_COLOR)
    return img, hashlib.sha256(raw).hexdigest()


def _run(path: Path, label: str, esperado: dict | None = None):
    if not path.exists():
        print(f"[SKIP] {label}: {path}")
        return True
    img, sha = _load(path)
    r = processar_folha_azul(img, fase="disciplinas", image_sha256=sha, request_id=label)
    print(f"\n=== {label} ===")
    print("codigo:", r.get("codigo"))
    ei = r.get("exame_integrado", {})
    d1 = ei.get("disciplina_1", {}).get("disciplina_escolhida")
    d2 = ei.get("disciplina_2", {}).get("disciplina_escolhida")
    print("exame D1:", d1)
    print("exame D2:", d2)
    if esperado:
        ok = True
        if r.get("codigo") != esperado.get("codigo"):
            print(" ERRO codigo")
            ok = False
        if d1 != esperado.get("disciplina_1"):
            print(" ERRO disciplina_1")
            ok = False
        if d2 != esperado.get("disciplina_2"):
            print(" ERRO disciplina_2")
            ok = False
        print("OK" if ok else "FALHOU")
        return ok
    return True


if __name__ == "__main__":
    ok = _run(REF, "pdf_referencia")
    ok2 = _run(FOTO_REAL, "foto_real", ESPERADO_FOTO)
    sys.exit(0 if ok and ok2 else 1)
