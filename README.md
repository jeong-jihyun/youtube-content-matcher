# youtube-content-matcher

내 유튜브 시청 기록을 기반으로 관심사 키워드를 뽑아내고,
그 키워드로 유튜브를 검색해 나에게 맞는 영상을 점수화하여 찾아주는 스크립트입니다.

## 동작 순서
1. 구글 테이크아웃(watch-history.json)에서 시청 기록을 읽는다.
2. 시청 제목들에서 자주 나온 단어를 뽑아 "관심사 키워드"로 삼는다.
3. 그 키워드로 YouTube Data API 검색을 실행한다.
4. 검색 결과 제목이 관심사와 얼마나 겹치는지 점수를 매긴다.
5. 결과를 CSV로 저장하고, 점수 분포를 히스토그램으로 그린다.

## 준비물
- Google Takeout에서 내려받은 `watch-history.json`
- YouTube Data API v3 키
- `pip install requests matplotlib`

## 실행
스크립트 상단 `API_KEY`, `WATCH_HISTORY_FILE` 값을 채운 뒤:
```
python youtube_personalized_finder.py
```
