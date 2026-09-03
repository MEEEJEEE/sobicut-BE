def _create_transaction(client, auth_headers):
    return client.post(
        "/transactions",
        json={
            "amount": 12000, "type": "expense", "category": "식비", "merchant": "스타벅스",
            "transaction_date": "2026-07-05", "transaction_time": "14:00",
        },
        headers=auth_headers,
    ).json()["id"]


def test_set_tags_and_read_back(client, auth_headers):
    tx_id = _create_transaction(client, auth_headers)

    res = client.post(f"/transactions/{tx_id}/tags", json={"tags": ["카페", "생일선물"]}, headers=auth_headers)
    assert res.status_code == 200

    detail = client.get(f"/transactions/{tx_id}", headers=auth_headers).json()
    assert set(detail["tags"]) == {"카페", "생일선물"}
    assert detail["emotion_tags"] == []  # 감정 태그와 완전히 별개


def test_set_tags_replaces_previous_set(client, auth_headers):
    tx_id = _create_transaction(client, auth_headers)

    client.post(f"/transactions/{tx_id}/tags", json={"tags": ["카페", "생일선물"]}, headers=auth_headers)
    client.post(f"/transactions/{tx_id}/tags", json={"tags": ["회식"]}, headers=auth_headers)

    detail = client.get(f"/transactions/{tx_id}", headers=auth_headers).json()
    assert detail["tags"] == ["회식"]


def test_set_tags_empty_list_clears_tags(client, auth_headers):
    tx_id = _create_transaction(client, auth_headers)

    client.post(f"/transactions/{tx_id}/tags", json={"tags": ["카페"]}, headers=auth_headers)
    client.post(f"/transactions/{tx_id}/tags", json={"tags": []}, headers=auth_headers)

    detail = client.get(f"/transactions/{tx_id}", headers=auth_headers).json()
    assert detail["tags"] == []


def test_set_tags_trims_whitespace_and_dedupes_and_skips_blanks(client, auth_headers):
    tx_id = _create_transaction(client, auth_headers)

    client.post(
        f"/transactions/{tx_id}/tags",
        json={"tags": [" 카페 ", "카페", "", "   ", "생일선물"]},
        headers=auth_headers,
    )

    detail = client.get(f"/transactions/{tx_id}", headers=auth_headers).json()
    assert sorted(detail["tags"]) == ["카페", "생일선물"] or sorted(detail["tags"]) == ["생일선물", "카페"]
    assert len(detail["tags"]) == 2


def test_set_tags_no_length_limit(client, auth_headers):
    tx_id = _create_transaction(client, auth_headers)
    long_tag = "친구랑 오랜만에 만나서 저녁 먹고 카페까지 간 날" * 5  # 50자 넘는 긴 태그

    res = client.post(f"/transactions/{tx_id}/tags", json={"tags": [long_tag]}, headers=auth_headers)
    assert res.status_code == 200

    detail = client.get(f"/transactions/{tx_id}", headers=auth_headers).json()
    assert detail["tags"] == [long_tag]


def test_set_tags_rejected_for_other_users_transaction(client, auth_headers):
    tx_id = _create_transaction(client, auth_headers)

    client.post(
        "/auth/signup",
        json={
            "email": "other@test.com", "password": "test1234", "nickname": "다른유저",
            "residence_type": "자취", "income_level": "30-60",
        },
    )
    other_login = client.post("/auth/login", json={"email": "other@test.com", "password": "test1234"})
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    res = client.post(f"/transactions/{tx_id}/tags", json={"tags": ["몰래"]}, headers=other_headers)
    assert res.status_code == 404


def test_tags_do_not_affect_impulse_score(client, auth_headers):
    tx_id = _create_transaction(client, auth_headers)
    before = client.get(f"/transactions/{tx_id}", headers=auth_headers).json()["impulse_score"]

    client.post(
        f"/transactions/{tx_id}/tags",
        json={"tags": ["충동적인 소비였음", "완전 홧김비용"]},
        headers=auth_headers,
    )

    after = client.get(f"/transactions/{tx_id}", headers=auth_headers).json()["impulse_score"]
    assert before == after
