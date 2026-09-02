"""카카오 로그인: 프론트(카카오 JS SDK)가 발급받은 access_token을 그대로 받아서
카카오 사용자 정보 API로 검증한다. 별도의 REST API 키/Client Secret 없이도
access_token 자체가 카카오 서버에서 검증되므로 백엔드 설정이 단순하다.
"""
import httpx

KAKAO_USERINFO_URL = "https://kapi.kakao.com/v2/user/me"


class KakaoAuthError(Exception):
    """카카오 access_token이 유효하지 않거나 사용자 정보 조회에 실패한 경우"""


def fetch_kakao_user(access_token: str) -> dict:
    try:
        response = httpx.get(
            KAKAO_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=5.0,
        )
    except httpx.HTTPError as e:
        raise KakaoAuthError("카카오 서버 요청에 실패했습니다.") from e

    if response.status_code != 200:
        raise KakaoAuthError("유효하지 않은 카카오 액세스 토큰입니다.")

    data = response.json()
    kakao_account = data.get("kakao_account") or {}

    return {
        "kakao_id": str(data["id"]),
        "email": kakao_account.get("email"),
        "email_verified": bool(kakao_account.get("is_email_verified")),
    }
