# routes/ai_monitoring.py
from flask import Blueprint, request, jsonify, session
from app.services.ai_monitoring import ai_monitoring_service
from app.utils.decorators import login_required
import time
import traceback
from datetime import datetime

ai_monitoring_bp = Blueprint('ai_monitoring', __name__)

@ai_monitoring_bp.route('/api/ai_monitoring/start', methods=['POST'])
@login_required
def start_ai_monitoring():
    try:
        data = request.get_json() or {}
        quiz_id = data.get('quiz_id') or session.get('quiz_id')
        if not quiz_id:
            quiz_id = f"temp_{session.get('scholar_id')}_{int(time.time())}"
        
        user_id = session.get('scholar_id')
        if not user_id:
            return jsonify({"success": False, "error": "Unauthorized"}), 401

        # Test camera access
        success, idx, backend = ai_monitoring_service._test_camera_access()
        if not success:
            return jsonify({
                "success": False,
                "error": "Camera is in use by another app or not working. Please close Zoom/Teams and try again."
            }), 500

        if ai_monitoring_service.start_monitoring(user_id, quiz_id):
            return jsonify({
                "success": True,
                "message": "AI monitoring started",
                "monitoring_active": True,
                "quiz_id": quiz_id
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to initialize camera. Please try again."
            }), 500
    except Exception as e:
        print(f"Error starting AI monitoring: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500

@ai_monitoring_bp.route('/api/ai_monitoring/stop', methods=['POST'])
@login_required
def stop_ai_monitoring():
    try:
        ai_monitoring_service.stop_monitoring()
        return jsonify({"success": True, "message": "Stopped"})
    except Exception as e:
        print(f"Error stopping AI monitoring: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@ai_monitoring_bp.route('/api/ai_monitoring/status', methods=['GET'])
@login_required
def get_status():
    try:
        # Check if AI monitoring service is properly initialized
        if not hasattr(ai_monitoring_service, 'face_detection') or not ai_monitoring_service.face_detection:
            return jsonify({
                "success": False,
                "error": "AI monitoring not properly initialized"
            }), 500

        status_data = {
            "is_monitoring": ai_monitoring_service.is_monitoring,
            "violation_summary": ai_monitoring_service.get_violation_summary(),
            "current_frame": ai_monitoring_service.get_current_frame(),
            "active_notifications": ai_monitoring_service.get_active_notifications()
        }
        
        return jsonify({
            "success": True,
            "status": status_data
        })
    except Exception as e:
        print(f"Error getting AI monitoring status: {str(e)}")
        print(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": f"Failed to get monitoring status: {str(e)}"
        }), 500

@ai_monitoring_bp.route('/api/ai_monitoring/notifications', methods=['GET'])
@login_required
def get_notifications():
    """Get recent notifications for the current user"""
    try:
        user_id = session.get('scholar_id')
        notifications = ai_monitoring_service.get_active_notifications()
        
        # Filter notifications for current user
        user_notifications = [
            n for n in notifications 
            if n.get('user_id') == user_id
        ]
        
        return jsonify({
            "success": True,
            "notifications": user_notifications[-10:]  # Last 10 notifications
        })
    except Exception as e:
        print(f"Error getting notifications: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@ai_monitoring_bp.route('/api/ai_monitoring/clear_notifications', methods=['POST'])
@login_required
def clear_notifications():
    """Clear notifications for current user"""
    try:
        ai_monitoring_service.clear_notifications()
        return jsonify({"success": True, "message": "Notifications cleared"})
    except Exception as e:
        print(f"Error clearing notifications: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@ai_monitoring_bp.route('/api/ai_monitoring/violations', methods=['GET'])
@login_required
def get_violations():
    try:
        from app import get_db
        
        user_id = session.get('scholar_id')
        quiz_id = request.args.get('quiz_id')
        recent = request.args.get('recent', 'false').lower() == 'true'
        
        query = {"user_id": user_id}
        if quiz_id: 
            query["quiz_id"] = quiz_id
        
        if recent:
            # Get only recent violations (last 1 hour)
            one_hour_ago = datetime.now().timestamp() - 3600
            query["timestamp"] = {"$gte": datetime.fromtimestamp(one_hour_ago)}
        
        violations_cursor = get_db().ai_violations.find(query, {'_id': 0, 'evidence': 0}).sort('timestamp', -1).limit(50)
        violations = list(violations_cursor)
        
        # Convert to JSON-serializable format
        serializable_violations = []
        for violation in violations:
            # Convert ObjectId to string if it exists
            if '_id' in violation:
                violation['_id'] = str(violation['_id'])
            # Convert datetime to string
            if 'timestamp' in violation and isinstance(violation['timestamp'], datetime):
                violation['timestamp'] = violation['timestamp'].isoformat()
            serializable_violations.append(violation)
        
        return jsonify({
            "success": True, 
            "violations": serializable_violations
        })
    except Exception as e:
        print(f"Error getting violations: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500

@ai_monitoring_bp.route('/api/ai_monitoring/admin/violations', methods=['GET'])
@login_required
def get_admin_violations():
    """Get violations for admin dashboard (all users)"""
    try:
        from app import get_db
        
        # Check if user is admin
        if session.get('role') != 'admin':
            return jsonify({"success": False, "error": "Unauthorized"}), 403
        
        recent = request.args.get('recent', 'true').lower() == 'true'
        
        query = {}
        if recent:
            # Get only recent violations (last 1 hour)
            one_hour_ago = datetime.now().timestamp() - 3600
            query["timestamp"] = {"$gte": datetime.fromtimestamp(one_hour_ago)}
        
        violations_cursor = get_db().ai_violations.find(query, {'_id': 0, 'evidence': 0}).sort('timestamp', -1).limit(100)
        violations = list(violations_cursor)
        
        # Convert to JSON-serializable format
        serializable_violations = []
        for violation in violations:
            if '_id' in violation:
                violation['_id'] = str(violation['_id'])
            if 'timestamp' in violation and isinstance(violation['timestamp'], datetime):
                violation['timestamp'] = violation['timestamp'].isoformat()
            serializable_violations.append(violation)
        
        return jsonify({
            "success": True, 
            "violations": serializable_violations
        })
    except Exception as e:
        print(f"Error getting admin violations: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500