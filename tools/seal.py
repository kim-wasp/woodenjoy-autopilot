"""민감한 점검 결과를 공개 저장소에 올리기 전에 잠가요 (공개키로 암호화, 여는 열쇠는 저장소 밖에만 있어요)
  python3 tools/seal.py <입력 파일> <출력 .enc>
"""
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

pub = serialization.load_pem_public_key((Path(__file__).parent / "report_pub.pem").read_bytes())
data = Path(sys.argv[1]).read_bytes()
key, nonce = AESGCM.generate_key(256), os.urandom(12)
ek = pub.encrypt(key, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
Path(sys.argv[2]).write_bytes(len(ek).to_bytes(2, "big") + ek + nonce + AESGCM(key).encrypt(nonce, data, None))
print("잠금 완료", sys.argv[2])
