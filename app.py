import cv2
import time
import threading
import subprocess
import numpy as np
from flask import Flask, Response, render_template

app = Flask(__name__)

# 1. rpicam-vid 명령 설정
# stdout으로 MJPEG 스트림을 직접 보냅니다.
command = [
    'rpicam-vid',
    '-t', '0',                 # 무한 실행
    '--width', '640',          # 해상도 (필요에 따라 조절)
    '--height', '480',
    '--inline',                # 헤더 정보를 매 프레임 포함
    '--nopreview',             # 미리보기 창 끄기
    '--codec', 'mjpeg',        # 처리 효율이 좋은 MJPEG 포맷
    '--framerate', '30',       # 프레임 레이트
    '-o', '-'                  # 표준 출력(stdout)으로 데이터 전송
]

# rpicam-vid 프로세스 시작
proc = subprocess.Popen(command, stdout=subprocess.PIPE, bufsize=10**6)

# 전역 변수 및 스레드 락 설정
global_frame = None
frame_lock = threading.Lock()

def capture_frames():
    """백그라운드 스레드: stdout에서 JPEG 데이터를 읽어 프레임 단위로 파싱"""
    global global_frame
    buffer = b""

    while True:
        # 프로세스로부터 스트림 데이터를 읽어옴
        chunk = proc.stdout.read(4096)
        if not chunk:
            break
        buffer += chunk

        # JPEG 프레임의 시작(0xffd8)과 끝(0xffd9) 지점을 검색
        start = buffer.find(b'\xff\xd8')
        end = buffer.find(b'\xff\xd9')

        if start != -1 and end != -1:
            # 프레임 추출
            jpg = buffer[start:end+2]
            # 추출된 부분은 버퍼에서 제거
            buffer = buffer[end+2:]

            with frame_lock:
                global_frame = jpg

# 프레임 캡처 스레드 시작
capture_thread = threading.Thread(target=capture_frames)
capture_thread.daemon = True
capture_thread.start()

def gen_frames():
    """웹 브라우저로 MJPEG 스트림 전송"""
    while True:
        with frame_lock:
            frame = global_frame

        if frame is None:
            time.sleep(0.01)
            continue

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        
        # CPU 점유율 조절을 위한 미세 지연
        time.sleep(0.03)

@app.route('/')
def index():
    """메인 페이지 (templates/index.html 필요)"""
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    """이미지 스트리밍 라우트"""
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    try:
        # 카메라 자원 중복 점유 방지를 위해 use_reloader=False 설정
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # 프로그램 종료 시 프로세스 안전하게 종료
        proc.terminate()
        print("Camera process terminated.")
