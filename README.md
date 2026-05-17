# turtle_yolo_control & turtle_hand_follower

<!-- 시스템 전체 사진 -->
<!-- ![시스템 구성](assets/imgs/system_overview.jpg) -->

## 프로젝트 개요

본 프로젝트는 대한상공회의소 서울기술교육센터 AI 융합 로봇 SW 개발자 2기 과정 중  
**ROS 2 기반 터틀봇 제어 수업 프로젝트**로 진행되었습니다.

TurtleBot3 내부의 Raspberry Pi 카메라로 촬영한 영상을 Flask 서버로 스트리밍하고,  
**YOLO11 기반 손 제스처 인식**을 통해 TurtleBot3를 실시간으로 제어하는 두 가지 모드를 구현하였습니다.

- **`turtle_yolo_control`** : 가위바위보 제스처에 따라 전진 / 회전 / 정지 명령을 수행하는 제스처 제어 모드
- **`turtle_hand_follower`** : 손바닥(보)을 인식하여 로봇이 손을 자동으로 추종하는 핸드 팔로워 모드

---

## 주요 기능

시스템은 **TurtleBot3 내부 Raspberry Pi의 카메라 스트리밍 서버**와 **제어 PC의 ROS 2 노드** 두 파트로 구성됩니다.

### 1. 카메라 스트리밍 서버 (`app.py` — TurtleBot3 내부 Raspberry Pi에서 실행)

TurtleBot3에 탑재된 Raspberry Pi 카메라 영상을 네트워크를 통해 실시간으로 스트리밍합니다.  
`rpicam-vid`를 subprocess로 실행하여 MJPEG 포맷의 영상을 stdout으로 수신하고,  
JPEG 마커(`0xFFD8` ~ `0xFFD9`)를 기준으로 프레임 단위로 파싱한 뒤  
Flask의 `/video_feed` 엔드포인트를 통해 제어 PC로 전송합니다.  
캡처와 스트리밍은 별도 스레드로 분리되어 CPU 점유율을 최소화합니다.

### 2. 가위바위보 제어 모드 (`turtle_cam_yolo.py` — 제어 PC에서 실행)

Flask 서버에서 MJPEG 스트림을 수신하여 YOLO11 모델로 실시간 추론을 수행합니다.  
인식된 제스처는 아래와 같이 TurtleBot3의 이동 명령으로 변환됩니다.

| 제스처 | linear.x | angular.z | 동작 |
|:---:|:---:|:---:|:---:|
| ✊ 바위 (Rock) | 0.0 | 0.0 | 즉시 정지 (긴급 중단) |
| 🖐 보 (Paper) | 0.15 | 0.0 | 직진 |
| ✌️ 가위 (Scissors) | 0.0 | -0.8 | 우회전 |

오인식 방지를 위해 **3단계 FSM(유한 상태 머신)** 을 적용하였습니다.  
0.5초 이상 동일한 제스처가 유지될 경우에만 동작을 확정하며, 확정된 명령은 4.5초간 유지됩니다.  
바위(Rock)는 어떤 상태에서도 최우선으로 감지되어 즉시 로봇을 정지시킵니다.

```
IDLE ──(제스처 감지)──▶ RECOGNIZING ──(0.5초 유지)──▶ EXECUTING ──(4.5초 경과)──▶ IDLE
 ▲                                                                                    │
 └──────────────────────── 바위(Rock) 감지 시 즉시 복귀 ◀───────────────────────────────┘
```

### 3. 핸드 팔로워 모드 (`hand_follower_node.py` — 제어 PC에서 실행)

손바닥(보, `paper`)이 감지되면 카메라 프레임 내의 손 위치와 크기를 기반으로  
**P(비례) 제어**를 적용하여 로봇이 손을 자동으로 추종합니다.

- **좌우 제어 (angular.z)** : 프레임 중앙과 손 중심의 X축 오차를 이용해 회전 속도 산출
- **전후 제어 (linear.x)** : 목표 손 면적(`35000 px`)과 현재 손 크기의 차이로 전후진 속도 산출
- 손이 사라지거나 다른 제스처가 감지되면 즉시 정지

```
손 중심 X 오차  ──▶  angular.z = 오차 × 0.0025  (angular_gain)
손 크기 오차    ──▶  linear.x  = 오차 × 0.0015  (linear_gain)  [최대 ±0.12 m/s]
```

---

### 가위바위보 제스처 제어

| | | |
| :---: | :---: | :---: |
| ![보에서 바위로](assets/gifs/paper_to_rock.gif) | ![가위 동작](assets/gifs/scissor.gif) | ![보 동작](assets/gifs/paper.gif) |
| **보 ➡️ 바위 (정지)** | **가위 (우회전)** | **보 (전진)** |

### 핸드 팔로워

<!-- ![핸드 팔로워](assets/gifs/hand_follower.gif) -->

---

## 개발 환경 및 기술

### 하드웨어 (Hardware)

- **로봇 플랫폼** : TurtleBot3 
- **카메라** : Raspberry Pi Camera Module (640×480, 30fps, MJPEG)
- **카메라 호스트** : TurtleBot3 내장 Raspberry Pi

### 소프트웨어 및 개발 환경 (Software & Environment)

- **사용 언어** : Python 3.12
- **로봇 미들웨어** : ROS 2 Jazzy
- **딥러닝 프레임워크** : Ultralytics YOLO11
- **웹 서버** : Flask (MJPEG 스트리밍)
- **영상 처리** : OpenCV

### 주요 기술 (Key Technologies)

- **YOLO11** : 가위바위보 제스처 실시간 분류 (GPU 가속, confidence threshold 적용)
- **MJPEG 스트리밍** : TurtleBot3 Raspberry Pi → Flask → 제어 PC ROS 2 노드 간 HTTP 영상 전송
- **FSM (유한 상태 머신)** : IDLE / RECOGNIZING / EXECUTING 3단계로 오인식 방지
- **P 제어 (비례 제어)** : 손 위치·크기 오차 기반 자율 추종 속도 산출
- **ROS 2 Topic** : `TwistStamped` 메시지를 `/cmd_vel` 토픽으로 20Hz 발행
- **멀티스레딩** : 프레임 수신과 YOLO 추론을 분리하여 처리 효율 향상

---

## 사용 모델

본 프로젝트는 **Gholamrezadar**가 공개한 YOLO11 가위바위보 감지 모델을 사용합니다.

- **모델 저장소** : [yolo11-rock-paper-scissors-detection](https://github.com/Gholamrezadar/yolo11-rock-paper-scissors-detection)
- **모델 파일** : `weights/yolo11-rps-detection.pt`
- **학습 데이터** : Roboflow Rock Paper Scissors Dataset
- **베이스 모델** : YOLO11n (Ultralytics) / 25 epochs / Tesla T4 GPU

---

---

## 프로젝트 디렉토리 구조

본 프로젝트의 파일은 아래와 같이 두 곳에 나뉘어 위치합니다.

### TurtleBot3 내부 Raspberry Pi

```
~/ (홈 디렉토리)
└─ app.py                                    # 카메라 스트리밍 Flask 서버
                                             # (TurtleBot3 부팅 시 또는 수동으로 실행)
```

### 제어 PC

```
~/Desktop/
└─ yolo11-rps-detection.pt                  # YOLO11 가위바위보 모델 가중치 파일

~/turtlebot3_ws/src/
├─ turtle_yolo_control/                      # 가위바위보 제스처 제어 패키지
│  ├─ package.xml                            # 패키지 의존성 선언
│  ├─ setup.py                               # entry_point: yolo_control_node
│  ├─ setup.cfg
│  ├─ resource/
│  │  └─ turtle_yolo_control
│  ├─ test/
│  │  ├─ test_copyright.py
│  │  ├─ test_flake8.py
│  │  └─ test_pep257.py
│  └─ turtle_yolo_control/
│     ├─ __init__.py
│     └─ turtle_cam_yolo.py                  # FSM 기반 제스처 제어 노드
│
└─ turtle_hand_follower/                     # 핸드 팔로워 패키지
   ├─ package.xml                            # 패키지 의존성 선언
   ├─ setup.py                               # entry_point: run_follower
   ├─ setup.cfg
   ├─ resource/
   │  └─ turtle_hand_follower
   ├─ test/
   │  ├─ test_copyright.py
   │  ├─ test_flake8.py
   │  └─ test_pep257.py
   └─ turtle_hand_follower/
      ├─ __init__.py
      └─ hand_follower_node.py               # P제어 기반 손 추종 노드
```

