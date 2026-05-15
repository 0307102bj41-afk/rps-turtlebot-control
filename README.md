# turtle_yolo_control

<!-- 단체사진 또는 시스템 전체 사진 -->
<!-- ![단체사진](assets/imgs/team.jpg) -->

## 프로젝트 개요

본 프로젝트는 대한상공회의소 서울기술교육센터 AI 융합 로봇 SW 개발자 2기 과정 중  
**ROS 2 기반 터틀봇 제어 수업 프로젝트**로 진행되었습니다.

Raspberry Pi 카메라로 촬영한 영상을 Flask 서버로 스트리밍하고,  
**YOLO11 기반 가위바위보 제스처 인식**을 통해 TurtleBot을 실시간으로 자율 제어하는 시스템입니다.

손 제스처 하나로 로봇의 주행 방향을 직관적으로 명령할 수 있으며,  
오인식 방지를 위한 FSM(유한 상태 머신) 구조를 적용하여 안정적인 동작을 구현하였습니다.

---

## 주요 기능

시스템은 크게 **카메라 스트리밍 서버**와 **ROS 2 제어 노드** 두 파트로 구성되어 동작합니다.

### 1. 카메라 스트리밍 서버 (`app.py`)

Raspberry Pi에 연결된 카메라 영상을 네트워크를 통해 실시간으로 스트리밍합니다.  
`rpicam-vid`를 subprocess로 실행하여 MJPEG 포맷의 영상을 stdout으로 수신하고,  
JPEG 마커(`0xFFD8` ~ `0xFFD9`)를 기준으로 프레임을 파싱한 뒤  
Flask의 `/video_feed` 엔드포인트를 통해 제어 PC로 전송합니다.  
캡처와 스트리밍은 별도 스레드로 분리되어 CPU 점유율을 최소화합니다.

### 2. ROS 2 제어 노드 (`turtle_cam_yolo.py`)

Flask 서버에서 MJPEG 스트림을 수신하여 YOLO11 모델로 실시간 추론을 수행합니다.  
인식된 제스처는 아래와 같이 TurtleBot의 이동 명령으로 변환됩니다.

| 제스처 | 동작 |
|:---:|:---:|
| ✊ 바위 (Rock) | 즉시 정지 (긴급 중단) |
| 🖐 보 (Paper) | 직진 |
| ✌️ 가위 (Scissors) | 우회전 |

오인식 방지를 위해 **3단계 FSM(유한 상태 머신)** 을 적용하였습니다.  
0.5초 이상 동일한 제스처가 유지될 경우에만 동작을 확정하며, 확정된 명령은 4.5초간 유지됩니다.  
바위(Rock)는 어떤 상태에서도 최우선으로 감지되어 즉시 로봇을 정지시킵니다.

```
IDLE ──(제스처 감지)──▶ RECOGNIZING ──(0.5초 유지)──▶ EXECUTING ──(4.5초 경과)──▶ IDLE
 ▲                                                                                    │
 └──────────────────────── 바위(Rock) 감지 시 즉시 복귀 ◀──────────────────────────────┘
```

---

## 시연 모습

### 전체 시스템 구성

<!-- ![전체 시스템](assets/imgs/system_overview.jpg) -->

### 주행 시연

<!-- ![주행 시연](assets/gifs/demo.gif) -->

### 제스처 인식 화면

<!-- ![제스처 인식](assets/imgs/yolo_window.jpg) -->

---

## 개발 환경 및 기술

### 하드웨어 (Hardware)

- **로봇 플랫폼** : TurtleBot3 (ROS 2 Humble)
- **카메라** : Raspberry Pi Camera Module
- **카메라 호스트** : Raspberry Pi

### 소프트웨어 및 개발 환경 (Software & Environment)

- **사용 언어** : Python 3.10
- **로봇 미들웨어** : ROS 2 Humble
- **딥러닝 프레임워크** : Ultralytics YOLO11
- **웹 서버** : Flask
- **영상 처리** : OpenCV

### 주요 기술 (Key Technologies)

- **YOLO11** : 가위바위보 제스처 실시간 분류 (GPU 가속, confidence 0.5 이상 채택)
- **MJPEG 스트리밍** : Raspberry Pi → Flask → ROS 2 노드 간 영상 전송
- **FSM (유한 상태 머신)** : IDLE / RECOGNIZING / EXECUTING 3단계 상태 제어로 오인식 방지
- **ROS 2 Topic** : `TwistStamped` 메시지를 `/cmd_vel` 토픽으로 20Hz 발행
- **멀티스레딩** : 프레임 수신과 YOLO 추론을 분리하여 처리 효율 향상

---

## 사용 모델

본 프로젝트는 **Gholamrezadar**가 공개한 YOLO11 가위바위보 감지 모델을 사용합니다.

- **모델 저장소** : [yolo11-rock-paper-scissors-detection](https://github.com/Gholamrezadar/yolo11-rock-paper-scissors-detection)
- **모델 파일** : `weights/yolo11-rps-detection.pt`
- **학습 데이터** : Roboflow Rock Paper Scissors Dataset
- **베이스 모델** : YOLO11n (Ultralytics) / 25 epochs / Tesla T4 GPU

모델 다운로드 후 `turtle_cam_yolo.py`의 경로를 실제 저장 위치로 수정하세요:

```python
self.model = YOLO('/your/path/to/yolo11-rps-detection.pt').to('cuda')
```

---

## 빌드 및 실행 방법

### 1단계 — Raspberry Pi: 카메라 스트리밍 서버 실행

```bash
pip install flask opencv-python
python app.py
```

### 2단계 — 제어 PC: ROS 2 패키지 빌드

```bash
cp -r turtle_yolo_control ~/ros2_ws/src/
cd ~/ros2_ws
colcon build --packages-select turtle_yolo_control
source install/setup.bash
```

### 3단계 — 노드 실행

```bash
ros2 run turtle_yolo_control yolo_control_node
```

> `turtle_cam_yolo.py` 내 `self.flask_url`을 실제 Raspberry Pi IP로 수정하세요.  
> 예: `http://192.168.0.10:5000/video_feed`

---

## 프로젝트 디렉토리 구조

```
turtle_yolo_control/
│
├─ app.py                              # Raspberry Pi 카메라 스트리밍 서버 (Flask)
│
└─ turtle_yolo_control/                # ROS 2 패키지
   ├─ package.xml                      # 패키지 의존성 선언
   ├─ setup.py                         # 패키지 설치 및 entry_point 등록
   ├─ setup.cfg                        # 빌드 설정
   ├─ resource/
   │  └─ turtle_yolo_control           # ament 인덱스 리소스 마커
   ├─ test/
   │  ├─ test_copyright.py
   │  ├─ test_flake8.py
   │  └─ test_pep257.py
   └─ turtle_yolo_control/
      ├─ __init__.py
      └─ turtle_cam_yolo.py            # 메인 ROS 2 노드 (YOLO 추론 및 모터 제어)
```

---

## 팀원 소개 및 역할 분담

<!-- 팀원 사진 -->
<!-- ![팀원](assets/imgs/team.jpg) -->

**한지호**
- 역할 : ROS 2 노드 개발, YOLO 연동 및 FSM 설계, 카메라 스트리밍 구현

> 역할 및 팀원 정보는 실제 내용으로 수정해주세요.
