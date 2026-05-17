import sys
# 1. ros2 run 실행 시 가상환경 패키지를 최우선으로 강제 참조하여 YOLO 인식 에러 방지
sys.path.insert(0, '/home/k/venv/ros/lib/python3.12/site-packages')

import cv2
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import TwistStamped
from ultralytics import YOLO
import numpy as np
import urllib.request
import threading
import time

class HandFollowerNode(Node):
    def __init__(self):
        super().__init__('hand_follower_controller')
        self.publisher = self.create_publisher(TwistStamped, '/cmd_vel', 10)
        
        # [필수 확인] 가위바위보/손바닥 모델 가중치 파일 경로
        self.model = YOLO('/home/k/Desktop/rps_project/best2.pt').to('cuda')
        
        self.latest_frame = None
        self.stopped = False
        
        # 이미지 제어 파라미터 (Flask 카메라 640x480 기준)
        self.target_width = 640
        self.center_x = self.target_width // 2
        
        # 제어 게인 (Gain) 세팅 (로봇이 너무 둔하거나 급하게 움직이면 조절)
        self.linear_gain = 0.0015  
        self.angular_gain = 0.0025 
        self.desired_hand_area = 35000 # 목표 손 크기 (픽셀 면적)
        
        self.current_cmd = TwistStamped()
        self.current_cmd.header.frame_id = 'base_link'
        
        # 터틀봇 영상 스트리밍 서버 주소
        self.flask_url = "http://10.10.14.16:5000/video_feed"
        self.thread = threading.Thread(target=self.fetch_frames, daemon=True)
        self.thread.start()
        
        self.create_timer(0.05, self.control_loop)
        self.get_logger().info("=== [새 패키지] 손바닥 추종 제어 노드 시작 ===")

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
            self.get_logger().error(f"영상 수신 에러: {e}")

    def control_loop(self):
        if self.latest_frame is None:
            return

        results = self.model(self.latest_frame, imgsz=320, verbose=False, conf=0.4)
        hand_detected = False
        track_info = "Searching Target..."

        if len(results[0].boxes) > 0:
            box = results[0].boxes[0]
            cls = int(box.cls[0])
            label = self.model.names[cls]
            
            # 'paper'(보) 혹은 'palm'(손바닥) 감지 시 추종 시작
            if 'paper' in label.lower() or 'palm' in label.lower():
                hand_detected = True
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                
                hand_center_x = (x1 + x2) // 2
                hand_area = (x2 - x1) * (y2 - y1)
                
                # 오차 계산 및 P 제어 기반 속도 산출
                error_x = self.center_x - hand_center_x 
                error_dist = self.desired_hand_area - hand_area
                
                self.current_cmd.twist.angular.z = error_x * self.angular_gain
                
                linear_vel = error_dist * self.linear_gain
                self.current_cmd.twist.linear.x = -np.clip(linear_vel, -0.12, 0.12)
                
                if abs(error_dist) < 5000:
                    self.current_cmd.twist.linear.x = 0.0
                    
                track_info = f"Tracking.. Area: {hand_area}"

        if not hand_detected:
            self.stop_cmd()
            track_info = "Target Lost (Stopped)"

        self.current_cmd.header.stamp = self.get_clock().now().to_msg()
        self.publisher.publish(self.current_cmd)
        self.show_window(results, track_info)

    def stop_cmd(self):
        self.current_cmd.twist.linear.x = 0.0
        self.current_cmd.twist.angular.z = 0.0

    def show_window(self, results, track_info):
        frame = results[0].plot()
        cv2.line(frame, (self.center_x, 0), (self.center_x, 480), (255, 0, 0), 1)
        cv2.putText(frame, track_info, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.imshow("Hand Follower", frame)
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
    node = HandFollowerNode()
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
