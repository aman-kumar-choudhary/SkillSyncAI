# app/services/ai_monitoring.py
import cv2
import numpy as np
import mediapipe as mp
import threading
import time
import base64
from datetime import datetime
import json
from bson import ObjectId
import os

class AIMonitoringService:
    def __init__(self):
        self.is_monitoring = False
        self.violations = []
        self.current_frame = None
        self.violation_count = 0
        self.max_violations = 10  # Increased for notifications instead of blocking
        self.last_face_position = None
        self.face_disappearance_start = None
        self.max_face_disappearance_time = 5
        
        # For real-time notifications
        self.active_notifications = []
        self.notification_callbacks = []
        
        # Initialize MediaPipe with better error handling
        self.face_detection = None
        self.face_mesh = None
        self.pose = None
        
        self._initialize_mediapipe()
        
        self.cap = None
        self.monitoring_thread = None
        self.camera_retry_count = 0
        self.max_camera_retries = 3
        self.user_id = None
        self.quiz_id = None

    def _initialize_mediapipe(self):
        """Initialize MediaPipe with comprehensive error handling"""
        try:
            # Set environment variables to optimize performance
            os.environ['MEDIAPIPE_GPU'] = '0'
            os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
            os.environ['OPENCV_OPENGL_RENDERER'] = '0'
            os.environ['OPENCV_VIDEOIO_PRIORITY_MSMF'] = '0'
            
            print("Initializing MediaPipe...")
            
            # Initialize with lower confidence thresholds for better detection
            self.face_detection = mp.solutions.face_detection.FaceDetection(
                model_selection=0, 
                min_detection_confidence=0.5
            )
            
            self.face_mesh = mp.solutions.face_mesh.FaceMesh(
                max_num_faces=1, 
                refine_landmarks=True,
                min_detection_confidence=0.5, 
                min_tracking_confidence=0.5,
                static_image_mode=False
            )
            
            self.pose = mp.solutions.pose.Pose(
                min_detection_confidence=0.5, 
                min_tracking_confidence=0.5,
                static_image_mode=False
            )
            
            print("MediaPipe initialized successfully")
            
        except Exception as e:
            print(f"Error initializing MediaPipe: {e}")
            self.face_detection = None
            self.face_mesh = None
            self.pose = None

    def _test_camera_access(self):
        """Test if camera can be opened and read"""
        print("Testing camera access...")
        backends = [cv2.CAP_ANY, cv2.CAP_V4L2, cv2.CAP_DSHOW]
        indices = [0, 1, 2]
        
        for backend in backends:
            for idx in indices:
                try:
                    print(f"Trying camera index {idx} with backend {backend}")
                    cap = cv2.VideoCapture(idx, backend)
                    if cap.isOpened():
                        ret, frame = cap.read()
                        cap.release()
                        if ret and frame is not None:
                            print(f"Camera found at index {idx} with backend {backend}")
                            return True, idx, backend
                except Exception as e:
                    print(f"Error testing camera {idx}: {e}")
                    continue
        
        print("No working camera found")
        return False, None, None

    def start_monitoring(self, user_id, quiz_id):
        if self.is_monitoring:
            print("AI monitoring already running")
            return True

        # Check if MediaPipe is initialized
        if not self.face_detection:
            print("MediaPipe not initialized, attempting reinitialization...")
            self._initialize_mediapipe()
            if not self.face_detection:
                print("Failed to initialize MediaPipe")
                return False

        # Test camera first
        print("Starting camera test...")
        success, idx, backend = self._test_camera_access()
        if not success:
            print("Camera test failed")
            return False

        self.is_monitoring = True
        self.violations = []
        self.violation_count = 0
        self.user_id = user_id
        self.quiz_id = quiz_id
        self.camera_retry_count = 0
        self.active_notifications = []  # Clear previous notifications

        # Initialize camera
        try:
            print(f"Initializing camera at index {idx} with backend {backend}")
            self.cap = cv2.VideoCapture(idx, backend)
            if not self.cap.isOpened():
                print("Failed to open camera")
                return False
                
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS, 15)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            # Start thread
            self.monitoring_thread = threading.Thread(target=self._monitoring_loop)
            self.monitoring_thread.daemon = True
            self.monitoring_thread.start()

            print(f"AI monitoring started for {user_id}")
            return True
            
        except Exception as e:
            print(f"Error starting monitoring: {e}")
            self.is_monitoring = False
            if self.cap:
                self.cap.release()
                self.cap = None
            return False

    def stop_monitoring(self):
        print("Stopping AI monitoring...")
        self.is_monitoring = False
        
        # Stop camera
        if self.cap:
            self.cap.release()
            self.cap = None
        
        # Close MediaPipe solutions
        try:
            if self.face_detection: 
                self.face_detection.close()
            if self.face_mesh: 
                self.face_mesh.close()
            if self.pose: 
                self.pose.close()
        except Exception as e:
            print(f"Error closing MediaPipe: {e}")
        
        cv2.destroyAllWindows()
        print("AI monitoring stopped")

    def _monitoring_loop(self):
        print("Starting monitoring loop...")
        consecutive_no_face = 0
        max_no_face = 30
        frame_count = 0
        read_errors = 0
        max_errors = 5

        while self.is_monitoring:
            try:
                if not self.cap or not self.cap.isOpened():
                    if not self._reinitialize_camera():
                        break
                    continue

                ret, frame = self.cap.read()
                if not ret:
                    read_errors += 1
                    if read_errors >= max_errors:
                        if not self._reinitialize_camera():
                            break
                        read_errors = 0
                    time.sleep(0.1)
                    continue

                read_errors = 0
                self.current_frame = frame
                frame_count += 1

                # Process every 3rd frame to reduce CPU load
                if frame_count % 3 != 0:
                    time.sleep(0.033)
                    continue

                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                violations = self._analyze_frame(rgb_frame, frame)

                if any('no_face' in v['type'] for v in violations):
                    consecutive_no_face += 1
                else:
                    consecutive_no_face = 0

                if consecutive_no_face >= max_no_face:
                    self._record_violation("prolonged_face_absence", "Face missing too long")
                    consecutive_no_face = 0

                time.sleep(0.033)  # ~30 FPS
                
            except Exception as e:
                print(f"Error in monitoring loop: {e}")
                time.sleep(0.1)

    def _reinitialize_camera(self):
        if self.cap:
            self.cap.release()
            self.cap = None
            
        self.camera_retry_count += 1
        if self.camera_retry_count > self.max_camera_retries:
            print("Max camera reinitialization attempts reached")
            return False
            
        print(f"Reinitializing camera (attempt {self.camera_retry_count})")
        time.sleep(1)
        
        success, idx, backend = self._test_camera_access()
        if success:
            try:
                self.cap = cv2.VideoCapture(idx, backend)
                return self.cap.isOpened()
            except Exception as e:
                print(f"Error reinitializing camera: {e}")
                return False
        return False

    def _analyze_frame(self, rgb_frame, original_frame):
        violations = []
        if not self.face_detection:
            return violations

        try:
            # Face detection
            results = self.face_detection.process(rgb_frame)
            if results.detections:
                if len(results.detections) > 1:
                    self._record_violation("multiple_faces", f"{len(results.detections)} faces detected")
                    violations.append({'type': 'multiple_faces', 'count': len(results.detections)})
            
            # Analyze each detected face
                for detection in results.detections:
                    bbox = detection.location_data.relative_bounding_box
                    h, w, _ = original_frame.shape
                    x = int(bbox.xmin * w)
                    y = int(bbox.ymin * h)
                    width = int(bbox.width * w)
                    height = int(bbox.height * h)
                
                    # Ensure coordinates are within frame bounds
                    x = max(0, x)
                    y = max(0, y)
                    width = min(width, w - x)
                    height = min(height, h - y)
                
                    if width > 0 and height > 0:
                        face_region = rgb_frame[y:y+height, x:x+width]
                        if face_region.size > 0:
                            violations.extend(self._analyze_head_pose(face_region, original_frame))
                            violations.extend(self._analyze_gaze_direction(face_region))
            else:
            # Only record face absence if it's prolonged
                current_time = time.time()
                if self.face_disappearance_start is None:
                    self.face_disappearance_start = current_time
                elif current_time - self.face_disappearance_start > self.max_face_disappearance_time:
                    self._record_violation("face_not_visible", "Face not detected for prolonged period")
                    self.face_disappearance_start = None
                violations.append({'type': 'no_face'})
        
        # Object detection
            violations.extend(self._detect_suspicious_objects(original_frame))
        
        except Exception as e:
            print(f"Frame analysis error: {e}")
        
        return violations

    def _analyze_head_pose(self, face_region, original_frame):
        violations = []
        if not self.face_mesh:
            return violations
            
        try:
            results = self.face_mesh.process(face_region)
            if results.multi_face_landmarks:
                landmarks = results.multi_face_landmarks[0].landmark
                
                # Simple head pose estimation using eye and nose positions
                left_eye = landmarks[33]
                right_eye = landmarks[263]
                nose = landmarks[1]
                
                eye_center_x = (left_eye.x + right_eye.x) / 2
                eye_nose_y = abs((left_eye.y + right_eye.y) / 2 - nose.y)
                
                # Detect head turning
                if abs(eye_center_x - 0.5) > 0.3:
                    violations.append({'type': 'head_turn'})
                    self._record_violation("head_turn", "Suspicious head movement detected")
                
                # Detect looking down
                if eye_nose_y < 0.05:
                    violations.append({'type': 'looking_down'})
                    self._record_violation("looking_down", "Looking away from screen")
                    
        except Exception as e:
            print(f"Head pose analysis error: {e}")
            
        return violations

    def _analyze_gaze_direction(self, face_region):
        violations = []
        try:
            gray = cv2.cvtColor(face_region, cv2.COLOR_RGB2GRAY)
            h, w = gray.shape
            
            if h == 0 or w == 0: 
                return violations
                
            # Simple gaze detection using brightness distribution
            left_region = gray[:, :w//3] if w//3 > 0 else np.array([0])
            center_region = gray[:, w//3:2*w//3] if w//3 > 0 else np.array([0])
            right_region = gray[:, 2*w//3:] if w//3 > 0 else np.array([0])
            
            left_brightness = np.mean(left_region) if left_region.size > 0 else 0
            center_brightness = np.mean(center_region) if center_region.size > 0 else 0
            right_brightness = np.mean(right_region) if right_region.size > 0 else 0
            
            # Detect gaze direction
            if left_brightness > center_brightness * 1.5: 
                violations.append({'type': 'gaze_left'})
                self._record_violation("gaze_left", "Looking to the left")
                
            if right_brightness > center_brightness * 1.5: 
                violations.append({'type': 'gaze_right'})
                self._record_violation("gaze_right", "Looking to the right")
                
        except Exception as e:
            print(f"Gaze analysis error: {e}")
            
        return violations

    def _detect_suspicious_objects(self, frame):
        violations = []
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > 5000:  # Large objects
                    x, y, w, h = cv2.boundingRect(contour)
                    if y < frame.shape[0] * 0.3:  # Object in upper part of frame
                        violations.append({'type': 'suspicious_object'})
                        self._record_violation("suspicious_object", "Unauthorized object detected")
                        
        except Exception as e:
            print(f"Object detection error: {e}")
            
        return violations

    def add_notification_callback(self, callback):
        """Add callback for real-time notifications"""
        self.notification_callbacks.append(callback)

    def _send_notification(self, violation_type, description, severity="warning"):
        """Send real-time notification instead of blocking"""
        notification = {
            'violation_id': str(ObjectId()),
            'type': violation_type,
            'description': description,
            'severity': severity,
            'timestamp': datetime.now().isoformat(),
            'user_id': self.user_id,
            'quiz_id': self.quiz_id
        }
        
        self.active_notifications.append(notification)
        
        # Keep only last 10 notifications
        if len(self.active_notifications) > 10:
            self.active_notifications.pop(0)
        
        # Call registered callbacks
        for callback in self.notification_callbacks:
            try:
                callback(notification)
            except Exception as e:
                print(f"Error in notification callback: {e}")
        
        print(f"AI Monitoring Notification: {violation_type} - {description}")

    def _record_violation(self, v_type, desc):
        """Record violation but don't block - just notify"""
        try:
            violation_id = str(ObjectId())
            evidence = None
            
            # Capture evidence image
            if self.current_frame is not None:
                try:
                    resized = cv2.resize(self.current_frame, (320, 240))
                    _, buffer = cv2.imencode('.jpg', resized, [cv2.IMWRITE_JPEG_QUALITY, 50])
                    evidence = base64.b64encode(buffer).decode('utf-8')
                except Exception as e:
                    print(f"Error encoding evidence: {e}")
            
            violation = {
                'violation_id': violation_id,
                'user_id': self.user_id,
                'quiz_id': self.quiz_id,
                'type': v_type,
                'description': desc,
                'timestamp': datetime.now().isoformat(),
                'evidence': evidence,
                'violation_count': self.violation_count + 1,
                'action_taken': 'notified'  # Changed from 'blocked'
            }
            
            self.violations.append(violation)
            self.violation_count += 1
            
            # Send real-time notification
            severity = "critical" if v_type in ["multiple_faces", "suspicious_object"] else "warning"
            self._send_notification(v_type, desc, severity)
            
            # Store in database
            try:
                from app import get_db
                db_violation = violation.copy()
                db_violation['timestamp'] = datetime.now()
                get_db().ai_violations.insert_one(db_violation)
                print(f"Violation recorded: {v_type} - {desc}")
            except Exception as e:
                print(f"Error storing violation in database: {e}")
                
        except Exception as e:
            print(f"Error recording violation: {e}")

    def get_violation_summary(self):
        """Get summary of violations with error handling"""
        try:
            # Convert violations to JSON-serializable format
            serializable_violations = []
            for violation in self.violations[-10:]:  # Last 10 violations
                serializable_violation = violation.copy()
                # Ensure timestamp is string
                if 'timestamp' in serializable_violation and isinstance(serializable_violation['timestamp'], datetime):
                    serializable_violation['timestamp'] = serializable_violation['timestamp'].isoformat()
                serializable_violations.append(serializable_violation)
            
            return {
                'total_violations': self.violation_count,
                'violations': serializable_violations,
                'is_blocked': False  # Always false now since we're not blocking
            }
        except Exception as e:
            print(f"Error getting violation summary: {e}")
            return {
                'total_violations': 0,
                'violations': [],
                'is_blocked': False
            }

    def get_current_frame(self):
        """Get current frame as base64 with error handling"""
        try:
            if self.current_frame is not None:
                _, buffer = cv2.imencode('.jpg', self.current_frame)
                return base64.b64encode(buffer).decode('utf-8')
        except Exception as e:
            print(f"Error getting current frame: {e}")
        return None

    def get_active_notifications(self):
        """Get active notifications for the current session"""
        return self.active_notifications[-5:]  # Return last 5 notifications

    def clear_notifications(self):
        """Clear active notifications"""
        self.active_notifications.clear()

# Global instance
ai_monitoring_service = AIMonitoringService()