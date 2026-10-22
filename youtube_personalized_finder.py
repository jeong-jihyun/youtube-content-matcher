"""
유튜브 맞춤형 콘텐츠 파인더
==========================

이 스크립트가 하는 일을 순서대로 설명하면:

1. 구글 테이크아웃(Google Takeout)으로 내려받은 '유튜브 시청 기록' 파일을 읽는다.
   -> 내가 어떤 영상을 봤는지 알아야, 내 관심사가 뭔지 짐작할 수 있으니까.
2. 시청한 영상 제목들에서 자주 등장하는 단어(키워드)를 뽑아낸다.
   -> 이게 곧 "나의 관심사 프로필"이 된다.
3. 그 키워드들로 유튜브를 실제로 검색한다 (YouTube Data API 사용).
   -> 내가 좋아할 만한 새 영상 후보들을 모으는 단계.
4. 검색된 영상 제목이 내 관심사 프로필과 얼마나 겹치는지 점수를 매긴다.
   -> 점수가 높을수록 "나한테 맞는 영상"이라고 판단.
5. 점수와 함께 링크를 CSV 파일로 저장한다.
6. 점수들이 어떻게 분포하는지 히스토그램(그래프)으로 보여준다.
   -> "내가 찾은 영상들이 대체로 얼마나 잘 맞는지" 한눈에 보기 위해서.

필요한 준비물
-------------
1) Google Takeout에서 내려받은 watch-history.json
   - takeout.google.com 접속
   - "전체 선택 해제" 후 "YouTube 및 YouTube Music"만 체크
   - "모든 YouTube 데이터 포함"에서 "기록"만 선택 (용량 줄이기)
   - 내보내기 형식은 JSON 선택 -> 내려받은 zip 안에 watch-history.json 있음

2) YouTube Data API v3 키
   - console.cloud.google.com 접속 -> 새 프로젝트 생성
   - "API 및 서비스" -> "라이브러리" -> "YouTube Data API v3" 검색 후 사용 설정
   - "사용자 인증 정보" -> "API 키 만들기" -> 키 복사해서 아래 API_KEY에 붙여넣기
   - 무료 할당량으로 하루 약 100번 정도 검색 가능 (키워드 15개면 충분)

3) 필요한 라이브러리 설치
   pip install requests matplotlib
"""

import json
import os
import re
import csv
import time
from collections import Counter

import requests
import matplotlib
matplotlib.use("Agg")  # 화면 없는 환경에서도 그래프 파일 저장 가능하게
import matplotlib.pyplot as plt
from matplotlib import font_manager

# ----------------------------
# 0. 설정값 (여기만 수정하면 됨)
# ----------------------------
# API 키는 코드에 적지 말고 환경변수 YOUTUBE_API_KEY 로 넣는 것을 권장합니다.
API_KEY = os.environ.get("YOUTUBE_API_KEY", "여기에_유튜브_API_키_입력")
WATCH_HISTORY_FILE = "watch-history.json"   # 테이크아웃에서 받은 파일 경로
TOP_KEYWORD_COUNT = 15        # 관심사 키워드 몇 개 뽑을지
RESULTS_PER_KEYWORD = 10      # 키워드 하나당 검색결과 몇 개 가져올지
OUTPUT_CSV = "matched_videos.csv"
OUTPUT_CHART = "match_distribution.png"

# 흔해서 관심사 판단에 도움 안 되는 단어들 (필요하면 계속 추가하세요)
STOPWORDS = {
    "영상", "브이로그", "shorts", "the", "official", "mv", "ep", "full",
    "이", "그", "저", "것", "수", "를", "을", "은", "는", "에", "의", "가",
    "with", "and", "for", "to", "of", "in", "on", "재생목록에", "추가된", "동영상",
    # 한국어 계정 시청 기록의 꼬리말("...을(를) 시청했습니다.")과 주소 조각
    "시청했습니다", "https", "http", "www", "youtube", "com", "watch",
}


def load_watch_history(path: str):
    """1단계: 테이크아웃 시청 기록 파일을 읽어서 영상 제목 목록만 뽑아낸다."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    titles = []
    for item in data:
        title = item.get("title", "")
        # 테이크아웃 형식은 보통 "Watched <제목>" 으로 들어있어서 접두어를 떼어냄
        title = re.sub(r"^Watched\s+", "", title).strip()
        # 한국어 계정은 "<제목> 을(를) 시청했습니다." 형태라 꼬리말도 떼어냄
        title = re.sub(r"\s*을\(를\)\s*시청했습니다\.?$", "", title).strip()
        if title:
            titles.append(title)
    return titles


def tokenize(text: str):
    return [w for w in re.findall(r"[가-힣a-zA-Z0-9]+", text.lower()) if len(w) >= 2]


def extract_keywords(titles, top_n):
    """2단계: 영상 제목들에서 자주 나온 단어를 세어 '내 관심사 키워드'로 뽑는다."""
    counter = Counter()
    for title in titles:
        for w in tokenize(title):
            if w in STOPWORDS:
                continue
            counter[w] += 1

    top_keywords = [word for word, _ in counter.most_common(top_n)]
    return top_keywords, counter


def search_youtube(keyword, api_key, max_results):
    """3단계: 유튜브 검색 API를 호출해서 이 키워드로 영상을 찾는다."""
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "key": api_key,
        "q": keyword,
        "part": "snippet",
        "type": "video",
        "maxResults": max_results,
        "order": "relevance",
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json().get("items", [])


def score_video(title, keyword_counter):
    """4단계: 영상 제목에 내 관심사 키워드가 얼마나(그리고 얼마나 자주 봤던 단어인지) 들어있는지로 점수를 매긴다."""
    words = set(tokenize(title))
    return sum(keyword_counter[w] for w in words if w in keyword_counter)


def collect_matches(top_keywords, keyword_counter, api_key, results_per_keyword):
    """3~4단계를 합쳐서: 키워드별로 검색하고, 중복 제거하며, 점수까지 매긴 리스트를 만든다."""
    seen_ids = set()
    matched = []
    for kw in top_keywords:
        try:
            items = search_youtube(kw, api_key, results_per_keyword)
        except requests.RequestException as e:
            print(f"  ! '{kw}' 검색 실패: {e}")
            continue

        for item in items:
            vid = item["id"]["videoId"]
            if vid in seen_ids:
                continue
            seen_ids.add(vid)

            snippet = item["snippet"]
            title = snippet["title"]
            matched.append({
                "title": title,
                "channel": snippet["channelTitle"],
                "link": f"https://www.youtube.com/watch?v={vid}",
                "matched_keyword": kw,
                "score": score_video(title, keyword_counter),
            })
        time.sleep(0.2)  # API 너무 빨리 두드리지 않게 살짝 쉬기

    matched.sort(key=lambda x: x["score"], reverse=True)
    return matched


def save_csv(matched, path):
    """5단계: 결과를 CSV로 저장한다."""
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["title", "channel", "link", "matched_keyword", "score"])
        writer.writeheader()
        writer.writerows(matched)


def save_distribution_chart(matched, path):
    """6단계: 매칭 점수 분포를 히스토그램으로 그려서 저장한다."""
    scores = [m["score"] for m in matched]

    # 한글이 깨지지 않도록, 시스템에 있는 한글 지원 폰트를 찾아서 사용
    # (못 찾으면 글자가 네모로 깨지는 대신 영어 라벨로 대체)
    korean_font_found = False
    for font in ("NanumGothic", "Malgun Gothic", "AppleGothic"):
        if any(font.lower() in f.name.lower() for f in font_manager.fontManager.ttflist):
            plt.rcParams["font.family"] = font
            korean_font_found = True
            break
    plt.rcParams["axes.unicode_minus"] = False

    if korean_font_found:
        title, xlabel, ylabel = (
            "내 관심사와 검색 결과의 매칭 점수 분포",
            "매칭 점수 (높을수록 내 시청 기록과 많이 겹침)",
            "영상 개수",
        )
    else:
        title, xlabel, ylabel = (
            "Match Score Distribution (search results vs. my watch history)",
            "Match score (higher = closer to my watch history)",
            "Number of videos",
        )

    plt.figure(figsize=(8, 5))
    plt.hist(scores, bins=15, color="#4C72B0", edgecolor="white")
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def main():
    print("1단계: 시청 기록 불러오는 중...")
    titles = load_watch_history(WATCH_HISTORY_FILE)
    print(f"  -> 시청한 영상 {len(titles)}개 확인")

    print("2단계: 관심사 키워드 뽑는 중...")
    top_keywords, keyword_counter = extract_keywords(titles, TOP_KEYWORD_COUNT)
    print(f"  -> 뽑힌 키워드: {', '.join(top_keywords)}")

    print("3~4단계: 유튜브에서 관련 영상 검색하고 점수 매기는 중...")
    matched = collect_matches(top_keywords, keyword_counter, API_KEY, RESULTS_PER_KEYWORD)
    print(f"  -> 총 {len(matched)}개 영상 수집 (중복 제거 후)")

    print("5단계: 결과 CSV로 저장 중...")
    save_csv(matched, OUTPUT_CSV)
    print(f"  -> {OUTPUT_CSV} 에 저장 완료")

    print("6단계: 점수 분포 그래프 그리는 중...")
    save_distribution_chart(matched, OUTPUT_CHART)
    print(f"  -> {OUTPUT_CHART} 로 저장 완료")

    print("\n상위 10개 추천 영상:")
    for m in matched[:10]:
        print(f"  [{m['score']}점] {m['title']} - {m['link']}")


if __name__ == "__main__":
    main()
