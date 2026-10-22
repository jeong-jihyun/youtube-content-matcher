# youtube-content-matcher

**내 유튜브 시청 기록에서 관심사 키워드를 뽑아, 그 키워드로 유튜브를 검색하고 "나에게 맞는 정도"를 점수로 매겨 주는 파이썬 스크립트**입니다.

## 동작 순서

| 단계 | 하는 일 | 함수 |
| --- | --- | --- |
| 1 | 구글 테이크아웃의 `watch-history.json`에서 시청한 영상 제목을 읽음 | `load_watch_history` |
| 2 | 제목에서 자주 나온 단어를 세어 관심사 키워드 상위 15개를 뽑음 (흔한 단어는 제외) | `extract_keywords` |
| 3 | 키워드마다 YouTube Data API 검색 (키워드당 10개, 중복 영상 제거) | `search_youtube`, `collect_matches` |
| 4 | 결과 제목에 관심사 단어가 얼마나 겹치는지 점수화 (자주 본 단어일수록 가중) | `score_video` |
| 5 | 결과를 `matched_videos.csv`로 저장 (제목·채널·링크·검색 키워드·점수) | `save_csv` |
| 6 | 점수 분포를 `match_distribution.png` 히스토그램으로 저장 | `save_distribution_chart` |

실행이 끝나면 점수 상위 10개 영상이 화면에 출력됩니다.

## 준비물

| 항목 | 방법 |
| --- | --- |
| 시청 기록 | takeout.google.com → "YouTube 및 YouTube Music"만 선택 → 기록만 포함 → JSON 형식으로 내려받아 `watch-history.json`을 꺼냄 |
| API 키 | Google Cloud Console에서 프로젝트 생성 → "YouTube Data API v3" 사용 설정 → API 키 만들기 |
| 라이브러리 | `pip install requests matplotlib` |

## 실행

```bash
export YOUTUBE_API_KEY=발급받은키        # Windows(PowerShell): $env:YOUTUBE_API_KEY="발급받은키"
python youtube_personalized_finder.py
```

- `watch-history.json`은 스크립트와 같은 폴더에 두거나, 스크립트 위쪽의 `WATCH_HISTORY_FILE` 값을 고치세요.
- 키워드 개수·키워드당 검색 수(`TOP_KEYWORD_COUNT`, `RESULTS_PER_KEYWORD`)와 제외할 단어(`STOPWORDS`)도 같은 곳에서 바꿉니다.
- 검색 1회는 API 할당량 100을 쓰고 하루 기본 할당량이 10,000이므로, 하루 약 100번 검색할 수 있습니다. (키워드 15개면 한 번 실행에 15회)

## 결과 파일

| 파일 | 내용 |
| --- | --- |
| `matched_videos.csv` | 점수 높은 순으로 정렬한 추천 영상 목록 (엑셀에서 한글이 깨지지 않게 UTF-8 BOM으로 저장) |
| `match_distribution.png` | 점수 분포 그래프. 한글 폰트(NanumGothic, Malgun Gothic, AppleGothic)가 없으면 영어 제목으로 대체 |

시청 기록과 결과 파일은 개인 정보라 `.gitignore`에 들어 있어 저장소에 올라가지 않습니다.

## 개선 내역 (2026-10)

| 구분 | 문제 | 수정 내용 |
| --- | --- | --- |
| 키워드 품질 | 한국어 계정의 시청 기록은 제목이 `"<제목> 을(를) 시청했습니다."` 형태인데, 영어 `Watched ` 접두어만 처리해서 "시청했습니다" 같은 꼬리말이 관심사 키워드 1순위로 뽑힐 수 있었음. 삭제된 영상은 주소(`https://www.youtube.com/...`)가 제목으로 들어가 `https`, `www`, `youtube`, `com`도 키워드가 됨 | 꼬리말을 떼어 내고, 위 단어들을 제외 목록에 추가 |
| 키 관리 | API 키를 코드 상단에 직접 써야 했음 (실수로 올리기 쉬움) | 환경변수 `YOUTUBE_API_KEY`에서 읽도록 변경 (기존처럼 코드에 적어도 동작) |
| 오류 처리 | 검색 중 네트워크 오류(연결 끊김·시간 초과)가 나면 프로그램이 중간에 멈춤 (HTTP 오류만 건너뜀) | 모든 요청 오류를 건너뛰고 다음 키워드로 진행 |

## 확인한 것과 못한 것

- 확인함: 가짜 시청 기록과 가짜 API 응답으로 읽기 → 키워드 추출 → 점수화 → CSV·그래프 저장까지 실행했고, 한국어 꼬리말과 주소 제목이 키워드에서 빠지는 것을 확인했습니다.
- **확인하지 못함:** 이 작업 환경에서는 YouTube API에 접속할 수 없고 실제 시청 기록이 없어, 실제 API 호출과 실제 테이크아웃 파일로는 실행하지 못했습니다.

## 알아둘 점

- 점수는 "제목 단어가 내 시청 제목과 겹치는 정도"만 보는 단순한 방식입니다. 영상 내용이나 인기도는 반영하지 않습니다.
- 시청 기록 제목에서 단어를 가르는 방식이 단순해, 한국어 조사가 붙은 단어는 다른 단어로 세어질 수 있습니다.
