import sys
sys.path.append('/home/jihohan/venv/yolov3/lib/python3.12/site-packages')

import cv2
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import TwistStamped
from ultralytics import YOLO
import numpy as np
import urllib.request
import threading
import time

class TurtleBotControlNode(Node):
    def __init__(self):
        super().__init__('turtlebot_yolo_controller')
        self.publisher = self.create_publisher(TwistStamped, '/cmd_vel', 10)
        
        # 모델 경로 확인 (best2.pt 또는 새 모델)
        self.model = YOLO('/home/jihohan/best2.pt').to('cuda')
        
        self.latest_frame = None
        self.stopped = False
        
        # --- 상태 제어 변수 ---
        self.state = "IDLE"          # IDLE, RECOGNIZING, EXECUTING
        self.target_label = None     # 인식 중인 라벨
        self.state_start_time = 0    # 상태가 바뀐 시점
        self.current_cmd = TwistStamped()
        self.current_cmd.header.frame_id = 'base_link'
        
        self.flask_url = "http://10.10.14.16:5000/video_feed"
        self.thread = threading.Thread(target=self.fetch_frames, daemon=True)
        self.thread.start()
        
        self.create_timer(0.05, self.control_loop)
        self.get_logger().info("=== 지연 인식 및 동작 유지 노드 시작 ===")

    def fetch_frames(self):
        try:
            stream = urllib.request.urlopen(self.flask_url)
            bytes_data = b''
            while not self.stopped:
                bytes_data += stream.read(4096)
                a = bytes_data.find(b'\xff\xd8')
                b = bytes_data.find(b'\xff\xd9')
                if a != -1 and b != -1:
                    jpg = bytes_data[a:b+2]
                    bytes_data = bytes_data[b+2:]
                    self.latest_frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
        except Exception as e:
            self.get_logger().error(f"수신 에러: {e}")

    def control_loop(self):
            if self.latest_frame is None:
                return

            # 1. YOLO 추론
            results = self.model(self.latest_frame, imgsz=320, verbose=False, conf=0.5)
            detected_label = None
            if len(results[0].boxes) > 0:
                cls = int(results[0].boxes.cls[0])
                detected_label = self.model.names[cls]

            now = time.time()
            
            # [추가] 바위(Rock) 감지 시 긴급 중단 로직 (우선순위 1순위)
            if detected_label and 'rock' in detected_label.lower():
                if self.state != "IDLE":
                    self.get_logger().warn("바위 감지: 동작 즉시 중단!")
                self.state = "IDLE"
                self.target_label = "rock" # 시각화용
                self.stop_cmd()
            
            # 2. 상태 머신 (FSM) 로직
            elif self.state == "IDLE":
                if detected_label: # 바위가 아닌 다른 것이 보이기 시작함
                    self.state = "RECOGNIZING"
                    self.target_label = detected_label
                    self.state_start_time = now
                self.stop_cmd()

            elif self.state == "RECOGNIZING":
                if detected_label == self.target_label:
                    if now - self.state_start_time >= 0.5:
                        self.state = "EXECUTING"
                        self.state_start_time = now
                        self.get_logger().info(f"동작 확정: {self.target_label}")
                else:
                    self.state = "IDLE"
                self.stop_cmd()

            elif self.state == "EXECUTING":
                # 1.5초 동안 동작 유지 (도중에 Rock이 들어오면 위쪽 if문에서 이미 걸러짐)
                if now - self.state_start_time < 4.5:
                    self.set_move_cmd(self.target_label)
                else:
                    self.state = "IDLE"
                    self.get_logger().info("동작 종료")

            # 3. 메시지 발행
            self.current_cmd.header.stamp = self.get_clock().now().to_msg()
            self.publisher.publish(self.current_cmd)

            self.show_window(results, detected_label)

    def set_move_cmd(self, label):
        # 대소문자 구분 없이 비교
        l = label.lower()
        if 'rock' in l:
            self.current_cmd.twist.linear.x = 0.0
            self.current_cmd.twist.angular.z = 0.0
        elif 'paper' in l:
            self.current_cmd.twist.linear.x = 0.15
            self.current_cmd.twist.angular.z = 0.0
        elif 'scissors' in l:
            self.current_cmd.twist.linear.x = 0.0
            self.current_cmd.twist.angular.z = -0.8

    def stop_cmd(self):
        self.current_cmd.twist.linear.x = 0.0
        self.current_cmd.twist.angular.z = 0.0

    def show_window(self, results, detected_label):
        frame = results[0].plot()
        color = (0, 255, 0) if self.state == "EXECUTING" else (0, 255, 255)
        cv2.putText(frame, f"State: {self.state}", (10, 30), 1, 1.5, color, 2)
        cv2.putText(frame, f"Target: {self.target_label}", (10, 60), 1, 1.5, color, 2)
        cv2.imshow("YOLO Time-based Control", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            raise KeyboardInterrupt

    def stop_robot(self):
        self.stopped = True
        stop_msg = TwistStamped()
        stop_msg.header.frame_id = 'base_link'
        for _ in range(5):
            stop_msg.header.stamp = self.get_clock().now().to_msg()
            self.publisher.publish(stop_msg)
            time.sleep(0.1)
        cv2.destroyAllWindows()

def main(args=None):
    rclpy.init(args=args)
    node = TurtleBotControlNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.stop_robot()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()