"""VAPID 키 쌍을 생성해 .env에 넣을 수 있는 형태로 출력한다.

사용법:
    python scripts/generate_vapid_keys.py
"""
from py_vapid import Vapid
from py_vapid.utils import b64urlencode
from cryptography.hazmat.primitives import serialization


def main() -> None:
    vapid = Vapid()
    vapid.generate_keys()

    private_raw = vapid.private_key.private_numbers().private_value.to_bytes(32, "big")
    public_raw = vapid.public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )

    print("아래 두 줄을 .env에 추가하세요:\n")
    print(f"VAPID_PUBLIC_KEY={b64urlencode(public_raw)}")
    print(f"VAPID_PRIVATE_KEY={b64urlencode(private_raw)}")
    print("\nVAPID_PUBLIC_KEY는 프론트에서 pushManager.subscribe()의 applicationServerKey로 사용합니다.")


if __name__ == "__main__":
    main()
