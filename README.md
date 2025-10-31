# `temp.csv` dataset overview

## 파일 개요
- 데이터 범위: 2023-10-16부터 2025-10-10까지 516개의 거래일.
- 종목: 삼성전자(005930.KS), Apple(AAPL), NVIDIA(NVDA)의 종가·고가·저가·시가·거래량.
- 헤더 구조: 첫 번째 줄은 가격 지표(예: Close, High), 두 번째 줄은 티커, 세 번째 줄은 날짜 열을 나타내는 `Date`.

## 분석 접근 방식
- 표준 `csv` 모듈을 사용해 다중 헤더를 `(티커_지표)` 형태의 단일 컬럼으로 변환했습니다.
- 각 거래일 데이터를 날짜 순으로 정렬한 뒤, 종목별로 다음 지표를 계산했습니다.
  - 최초/최종 종가와 기간 수익률
  - 평균·최대·최소 종가 및 해당 일자
  - 평균·최대 거래량 및 해당 일자
  - 일일 평균 변동폭(고가-저가)
- 요약 결과는 `analysis_summary.csv`에 저장했습니다.

### 재현 방법
아래 파이썬 예제는 `analysis_summary.csv`를 생성하는 핵심 절차를 보여줍니다.
```python
import csv
from datetime import datetime

with open("temp.csv", newline="") as f:
    rows = list(csv.reader(f))

columns = ["Date"] + [f"{metric_ticker[1]}_{metric_ticker[0]}" for metric_ticker in zip(rows[0][1:], rows[1][1:])]
records = []
for row in rows[3:]:
    if not row or not row[0]:
        continue
    record = {"Date": datetime.strptime(row[0], "%Y-%m-%d")}
    for name, value in zip(columns[1:], row[1:]):
        record[name] = float(value) if value else None
    records.append(record)

# 이후 records를 이용해 종목별 요약 통계를 계산하고 CSV로 저장합니다.
```

## 주요 지표 요약
| Ticker | Obs. | Close %Δ | Avg Close | Max Close (date) | Min Close (date) | Avg Vol (M) | Max Vol (M, date) | Avg Daily Range |
| --- | ---: | ---: | ---: | --- | --- | ---: | --- | ---: |
| 005930.KS | 482 | 45.72% | 66,471.53 | 94,400.00 (2025-10-10) | 48,968.97 (2024-11-14) | 19.48 | 57.69 (2024-01-11) | 1,379.43 |
| AAPL | 499 | 38.58% | 209.52 | 258.10 (2024-12-26) | 163.82 (2024-04-19) | 56.56 | 318.68 (2024-09-20) | 4.14 |
| NVDA | 499 | 297.59% | 115.60 | 192.57 (2025-10-09) | 40.30 (2023-10-26) | 325.12 | 1,142.27 (2024-03-08) | 4.14 |

## 해석 메모
- 세 종목 모두 같은 기간을 커버하지만, 삼성전자(005930.KS)는 현지 휴장일로 인해 482개 거래일만 존재합니다.
- NVDA는 기간 동안 약 298% 상승하며 가장 큰 누적 수익률을 기록했고, 최대 거래량은 2024-03-08에 11.4억 주로 집중되었습니다.
- Apple은 평균 거래량(5,655만 주)이 NVDA보다 낮지만, 2024-09-20에는 시장 이벤트로 추정되는 급격한 거래량 증가가 관측됩니다.
- 일일 변동폭은 005930.KS가 절대값 기준으로 가장 크며, 달러 표시 종목(AAPL, NVDA)은 평균 4달러 내외의 변동을 보였습니다.
