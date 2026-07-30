"""
Amazonレビュー監視スクリプト
- config.json に登録した商品(ASIN)のレビューページを取得
- 前回チェック時になかった新しいレビューIDを検出
- 新着があれば ntfy.sh 経由でスマホへ通知
- 状態は state.json に保存(GitHub Actions側でコミットして永続化)
"""

import json
import os
import random
import sys
import time

import requests
from bs4 import BeautifulSoup

CONFIG_PATH = "config.json"
STATE_PATH = "state.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# 任意: ブロック対策用にスクレイピング用プロキシを使う場合はGitHub Secretsで
# PROXY_URL (例: http://user:pass@proxyhost:port) を設定してください
PROXY_URL = os.environ.get("PROXY_URL")
PROXIES = {"http": PROXY_URL, "https": PROXY_URL} if PROXY_URL else None


def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_reviews(asin, session):
    url = f"https://www.amazon.co.jp/product-reviews/{asin}/?sortBy=recent&reviewerType=all_reviews"
    resp = session.get(url, headers=HEADERS, proxies=PROXIES, timeout=20)

    if "captcha" in resp.text.lower() or resp.status_code in (503, 429):
        raise RuntimeError(f"ブロック/CAPTCHAの可能性 (status={resp.status_code})")

    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    reviews = []
    for div in soup.select('div[data-hook="review"]'):
        review_id = div.get("id", "")
        title_el = div.select_one(
            'a[data-hook="review-title"] span, span[data-hook="review-title"] span'
        )
        title = title_el.get_text(strip=True) if title_el else ""

        rating_el = div.select_one(
            'i[data-hook="review-star-rating"] span, '
            'i[data-hook="cmps-review-star-rating"] span'
        )
        rating = rating_el.get_text(strip=True) if rating_el else ""

        body_el = div.select_one('span[data-hook="review-body"] span')
        body = body_el.get_text(strip=True) if body_el else ""

        if review_id:
            reviews.append(
                {"id": review_id, "title": title, "rating": rating, "body": body[:300]}
            )
    return reviews


def notify(ntfy_topic, product_name, review):
    title = f"新着レビュー: {product_name}"
    message = f"{review['rating']}\n{review['title']}\n\n{review['body']}"
    try:
        requests.post(
            f"https://ntfy.sh/{ntfy_topic}",
            data=message.encode("utf-8"),
            headers={
                "Title": title.encode("utf-8"),
                "Priority": "default",
                "Tags": "star",
            },
            timeout=15,
        )
    except Exception as e:
        print(f"  通知送信失敗: {e}")


def main():
    config = load_json(CONFIG_PATH, {"products": []})
    state = load_json(STATE_PATH, {})

    ntfy_topic = os.environ.get("NTFY_TOPIC")
    if not ntfy_topic:
        print("エラー: 環境変数 NTFY_TOPIC が設定されていません")
        sys.exit(1)

    products = config.get("products", [])
    if not products:
        print("config.json に商品が登録されていません")
        sys.exit(0)

    session = requests.Session()
    any_error = False

    for product in products:
        asin = product["asin"]
        name = product.get("name", asin)
        print(f"チェック中: {name} ({asin})")

        try:
            reviews = fetch_reviews(asin, session)
        except Exception as e:
            print(f"  取得失敗: {e}")
            any_error = True
            time.sleep(random.uniform(8, 15))
            continue

        seen_ids = set(state.get(asin, []))
        current_ids = {r["id"] for r in reviews}
        new_reviews = [r for r in reviews if r["id"] not in seen_ids]

        # 初回実行時は「既存レビュー全部が新着」扱いにならないよう、
        # state に記録が無いASINは通知せず状態だけ保存する
        is_first_run = asin not in state

        if is_first_run:
            print(f"  初回登録: 既存レビュー {len(reviews)} 件を記録(通知はスキップ)")
        else:
            for r in new_reviews:
                print(f"  新着レビュー検知: {r['title']}")
                notify(ntfy_topic, name, r)

        state[asin] = list(seen_ids | current_ids)
        time.sleep(random.uniform(6, 12))

    save_json(STATE_PATH, state)
    print("完了")

    if any_error:
        # 失敗があっても state は保存済みなのでexit codeは0のままにしておく
        # (毎回Actionsが赤くなるのを避けるため)
        pass


if __name__ == "__main__":
    main()
