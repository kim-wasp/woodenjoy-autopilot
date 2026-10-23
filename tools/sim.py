"""카드끼리 얼마나 비슷한지 계산 (32x40으로 줄여 밝기 차이 평균). 값이 작을수록 비슷함."""
import json
import sys

from PIL import Image


def pixels(path):
    im = Image.open(path).convert("L").resize((32, 40))
    return list(im.tobytes())


files = sys.argv[1:]
data = [pixels(f) for f in files]
out = []
for i in range(len(data)):
    for j in range(i + 1, len(data)):
        diff = sum(abs(a - b) for a, b in zip(data[i], data[j])) / len(data[i])
        out.append([i, j, diff])
print(json.dumps(out))
