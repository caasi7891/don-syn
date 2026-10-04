# DON SYN

컴퓨터 키보드로 연주하는 Windows 로컬 신디사이저입니다.

## 실행

`run.bat`을 더블클릭합니다. 처음 실행하면 Python 가상환경과 필요한 라이브러리를 설치한 뒤 창을 엽니다.

직접 실행하려면 Python 3.9 이상이 필요합니다.

```bat
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py
```

## 연주

- 흰건반: `Z X C V B N M`, 높은 옥타브 `Q W E R T Y U I O P`
- 검은건반: `S D G H J`, 높은 쪽 `2 3 5 6 7 9 0`
- 옥타브: `←` `→` 또는 `-` `=`
- 서스테인: `Space`
- 피치: `↑` `↓`
- 모두 끄기: `Esc`

화면의 건반을 마우스로 누를 수도 있습니다. 오실레이터, 필터, 엔벨롭, LFO, 아르페지오, 스케일 잠금, 딜레이, 코러스, 리버브와 프리셋이 들어 있습니다. 녹음하면 `recordings` 폴더에 wav 파일이 저장됩니다.
