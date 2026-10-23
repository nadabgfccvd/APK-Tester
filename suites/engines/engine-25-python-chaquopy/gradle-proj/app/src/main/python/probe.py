# probe.py — engine-25 (Tier A, A4): fonte Python REAL empacotada pelo
# Chaquopy (o plugin embute em assets/chaquopy/ e executa no runtime
# libpython3*.so). Executada pelo com.chaquo.python no RustyDroid.
ENGINE = "engine-25-python-chaquopy"
SEED = 20261022


def checksum() -> int:
    h = SEED
    for ch in ENGINE:
        h = (31 * h + ord(ch)) & 0xFFFFFFFF
    return h - 0x80000000 if h > 0x7FFFFFFF else h


if __name__ == "__main__":
    print(f"apktester:{ENGINE}:{checksum()}")
