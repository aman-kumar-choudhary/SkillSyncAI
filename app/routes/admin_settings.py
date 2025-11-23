import os
import json
import logging
from flask import Blueprint, render_template, request, jsonify, current_app, session
from functools import wraps
from bson import ObjectId
from datetime import datetime
import requests

# Setup logging
logger = logging.getLogger(__name__)

# Create blueprint
admin_settings_bp = Blueprint('admin_settings', __name__)

def admin_required(f):
    """Decorator to require admin authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user is logged in
        if 'user_id' not in session and 'username' not in session:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
        user_role = session.get('role')
        if user_role not in ['admin', 'super_admin']:
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        return f(*args, **kwargs)
    return decorated_function

@admin_settings_bp.route('/settings')
@admin_required
def admin_settings():
    """Render the admin settings page"""
    try:
        from app.services.ai_review_sevice import ai_review_service
        
        # Get system statistics
        db = current_app.db
        total_questions = db.questions.count_documents({}) if db else 0
        total_quizzes = db.quizzes.count_documents({}) if db else 0
        total_users = db.users.count_documents({}) if db else 0
        
        # Check AI service status
        ai_enabled = ai_review_service.enabled if ai_review_service else False
        
        return render_template('admin_settings.html',
                             ai_enabled=ai_enabled,
                             total_questions=total_questions,
                             total_quizzes=total_quizzes,
                             total_users=total_users,
                             api_key_placeholder="••••••••" if ai_enabled else "")
                             
    except Exception as e:
        logger.error(f"Error loading admin settings: {str(e)}")
        # Return basic settings page even if there's an error
        return render_template('admin_settings.html',
                             ai_enabled=False,
                             total_questions=0,
                             total_quizzes=0,
                             total_users=0,
                             api_key_placeholder="")

@admin_settings_bp.route('/api/settings/ai/test', methods=['POST'])
@admin_required
def test_ai_api_key():
    """Test the Gemini API key"""
    try:
        data = request.get_json()
        api_key = data.get('api_key', '').strip()
        
        if not api_key:
            return jsonify({
                'success': False,
                'error': 'API key is required'
            }), 400
        
        # Test the API key by making a simple request to Gemini
        import google.generativeai as genai
        
        try:
            # Configure with the provided API key
            genai.configure(api_key=api_key)
            
            # Create a simple test request
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content("Say 'OK' if working")
            
            # If we get here, the API key is valid
            return jsonify({
                'success': True,
                'message': 'API key is valid and working',
                'response': response.text if hasattr(response, 'text') else 'OK'
            })
            
        except Exception as api_error:
            logger.error(f"Gemini API test failed: {str(api_error)}")
            return jsonify({
                'success': False,
                'error': f'API key validation failed: {str(api_error)}'
            }), 400
            
    except Exception as e:
        logger.error(f"Error testing AI API key: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }), 500

@admin_settings_bp.route('/api/settings/ai/update', methods=['POST'])
@admin_required
def update_ai_settings():
    """Update AI settings and API key"""
    try:
        data = request.get_json()
        api_key = data.get('api_key', '').strip()
        enable_ai = data.get('enable_ai', True)
        
        # Validate API key if AI is being enabled
        if enable_ai and not api_key:
            return jsonify({
                'success': False,
                'error': 'API key is required when enabling AI features'
            }), 400
        
        # Update environment variable and restart AI service
        from app.services.ai_review_sevice import ai_review_service
        
        if api_key:
            # Update the environment variable (in production, you might want to use a config file or database)
            os.environ['GEMINI_API_KEY'] = api_key
            
            # Reinitialize the AI service
            try:
                # Recreate the service instance
                ai_review_service.__init__()
                
                # Test the new configuration
                if enable_ai and not ai_review_service.enabled:
                    return jsonify({
                        'success': False,
                        'error': 'Failed to initialize AI service with the provided API key'
                    }), 400
                    
            except Exception as service_error:
                logger.error(f"Failed to reinitialize AI service: {str(service_error)}")
                return jsonify({
                    'success': False,
                    'error': f'Failed to initialize AI service: {str(service_error)}'
                }), 400
        
        # Save settings to database or config file
        db = current_app.db
        if db:
            # Get user identifier - use username for super admin, user_id for admin users
            user_identifier = session.get('username') or session.get('user_id')
            
            settings_update = {
                'ai_enabled': enable_ai,
                'ai_api_key_configured': bool(api_key),
                'updated_at': datetime.utcnow(),
                'updated_by': user_identifier
            }
            
            # Update or insert settings
            db.settings.update_one(
                {'name': 'ai_configuration'},
                {'$set': settings_update},
                upsert=True
            )
        
        # Log the settings update
        logger.info(f"AI settings updated by user {user_identifier}. AI enabled: {enable_ai}")
        
        return jsonify({
            'success': True,
            'message': 'AI settings updated successfully',
            'ai_enabled': ai_review_service.enabled if ai_review_service else False
        })
        
    except Exception as e:
        logger.error(f"Error updating AI settings: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }), 500

@admin_settings_bp.route('/api/settings/general', methods=['POST'])
@admin_required
def update_general_settings():
    """Update general application settings"""
    try:
        data = request.get_json()
        
        # Extract settings from request
        default_theme = data.get('default_theme', 'auto')
        items_per_page = data.get('items_per_page', 25)
        email_notifications = data.get('email_notifications', True)
        push_notifications = data.get('push_notifications', True)
        new_user_notifications = data.get('new_user_notifications', True)
        quiz_submission_notifications = data.get('quiz_submission_notifications', False)
        
        # Validate inputs
        if default_theme not in ['light', 'dark', 'auto']:
            return jsonify({
                'success': False,
                'error': 'Invalid theme selection'
            }), 400
        
        if items_per_page not in [10, 25, 50, 100]:
            return jsonify({
                'success': False,
                'error': 'Invalid items per page value'
            }), 400
        
        # Save to database
        db = current_app.db
        if db:
            # Get user identifier
            user_identifier = session.get('username') or session.get('user_id')
            
            general_settings = {
                'default_theme': default_theme,
                'items_per_page': items_per_page,
                'notifications': {
                    'email': email_notifications,
                    'push': push_notifications,
                    'new_users': new_user_notifications,
                    'quiz_submissions': quiz_submission_notifications
                },
                'updated_at': datetime.utcnow(),
                'updated_by': user_identifier
            }
            
            db.settings.update_one(
                {'name': 'general_settings'},
                {'$set': general_settings},
                upsert=True
            )
        
        # Log the update
        logger.info(f"General settings updated by user {user_identifier}")
        
        return jsonify({
            'success': True,
            'message': 'General settings updated successfully'
        })
        
    except Exception as e:
        logger.error(f"Error updating general settings: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }), 500

@admin_settings_bp.route('/api/settings/quiz', methods=['POST'])
@admin_required
def update_quiz_settings():
    """Update quiz-related settings"""
    try:
        data = request.get_json()
        
        # Extract quiz settings
        default_time_limit = int(data.get('default_time_limit', 30))
        passing_score = int(data.get('passing_score', 60))
        allow_retakes = data.get('allow_retakes', True)
        shuffle_questions = data.get('shuffle_questions', False)
        max_attempts = int(data.get('max_attempts', 3))
        require_full_screen = data.get('require_full_screen', True)
        disable_copy_paste = data.get('disable_copy_paste', False)
        monitor_tab_switching = data.get('monitor_tab_switching', False)
        
        # Validate inputs
        if default_time_limit < 1 or default_time_limit > 240:
            return jsonify({
                'success': False,
                'error': 'Time limit must be between 1 and 240 minutes'
            }), 400
        
        if passing_score < 0 or passing_score > 100:
            return jsonify({
                'success': False,
                'error': 'Passing score must be between 0 and 100'
            }), 400
        
        if max_attempts < 1 or max_attempts > 10:
            return jsonify({
                'success': False,
                'error': 'Max attempts must be between 1 and 10'
            }), 400
        
        # Save to database
        db = current_app.db
        if db:
            # Get user identifier
            user_identifier = session.get('username') or session.get('user_id')
            
            quiz_settings = {
                'default_time_limit': default_time_limit,
                'passing_score': passing_score,
                'behavior': {
                    'allow_retakes': allow_retakes,
                    'shuffle_questions': shuffle_questions
                },
                'security': {
                    'max_attempts': max_attempts,
                    'require_full_screen': require_full_screen,
                    'disable_copy_paste': disable_copy_paste,
                    'monitor_tab_switching': monitor_tab_switching
                },
                'updated_at': datetime.utcnow(),
                'updated_by': user_identifier
            }
            
            db.settings.update_one(
                {'name': 'quiz_settings'},
                {'$set': quiz_settings},
                upsert=True
            )
        
        logger.info(f"Quiz settings updated by user {user_identifier}")
        
        return jsonify({
            'success': True,
            'message': 'Quiz settings updated successfully'
        })
        
    except Exception as e:
        logger.error(f"Error updating quiz settings: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }), 500

@admin_settings_bp.route('/api/settings/security', methods=['POST'])
@admin_required
def update_security_settings():
    """Update security settings"""
    try:
        data = request.get_json()
        
        # Extract security settings
        session_timeout = int(data.get('session_timeout', 120))
        require_strong_passwords = data.get('require_strong_passwords', True)
        enable_2fa = data.get('enable_2fa', False)
        encrypt_sensitive_data = data.get('encrypt_sensitive_data', True)
        automatic_backup = data.get('automatic_backup', False)
        log_admin_activities = data.get('log_admin_activities', True)
        
        # Validate inputs
        if session_timeout < 5 or session_timeout > 1440:
            return jsonify({
                'success': False,
                'error': 'Session timeout must be between 5 and 1440 minutes'
            }), 400
        
        # Save to database
        db = current_app.db
        if db:
            # Get user identifier
            user_identifier = session.get('username') or session.get('user_id')
            
            security_settings = {
                'authentication': {
                    'session_timeout': session_timeout,
                    'require_strong_passwords': require_strong_passwords,
                    'enable_2fa': enable_2fa
                },
                'data_protection': {
                    'encrypt_sensitive_data': encrypt_sensitive_data,
                    'automatic_backup': automatic_backup,
                    'log_admin_activities': log_admin_activities
                },
                'updated_at': datetime.utcnow(),
                'updated_by': user_identifier
            }
            
            db.settings.update_one(
                {'name': 'security_settings'},
                {'$set': security_settings},
                upsert=True
            )
        
        logger.info(f"Security settings updated by user {user_identifier}")
        
        return jsonify({
            'success': True,
            'message': 'Security settings updated successfully'
        })
        
    except Exception as e:
        logger.error(f"Error updating security settings: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }), 500

@admin_settings_bp.route('/api/settings/system-info')
@admin_required
def get_system_info():
    """Get system information and statistics"""
    try:
        db = current_app.db
        
        if not db:
            return jsonify({
                'success': False,
                'error': 'Database connection not available'
            }), 500
        
        # Get counts from database
        total_questions = db.questions.count_documents({})
        total_quizzes = db.quizzes.count_documents({})
        total_users = db.users.count_documents({})
        active_quizzes = db.quizzes.count_documents({'status': 'active'})
        pending_reviews = db.questions.count_documents({'status': 'pending_review'})
        
        # Get recent activity
        recent_activity = list(db.activity_log.find(
            {},
            {'_id': 0, 'action': 1, 'timestamp': 1, 'user_id': 1}
        ).sort('timestamp', -1).limit(5))
        
        # Get system settings
        ai_settings = db.settings.find_one({'name': 'ai_configuration'}) or {}
        general_settings = db.settings.find_one({'name': 'general_settings'}) or {}
        
        return jsonify({
            'success': True,
            'system_info': {
                'total_questions': total_questions,
                'total_quizzes': total_quizzes,
                'total_users': total_users,
                'active_quizzes': active_quizzes,
                'pending_reviews': pending_reviews,
                'ai_enabled': ai_settings.get('ai_enabled', False),
                'default_theme': general_settings.get('default_theme', 'auto'),
                'server_time': datetime.utcnow().isoformat()
            },
            'recent_activity': recent_activity
        })
        
    except Exception as e:
        logger.error(f"Error getting system info: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }), 500

@admin_settings_bp.route('/api/settings/danger/clear-data', methods=['POST'])
@admin_required
def clear_system_data():
    """Clear all system data (dangerous operation)"""
    try:
        data = request.get_json()
        confirmation = data.get('confirmation', '')
        
        # Require explicit confirmation
        if confirmation != 'DELETE_ALL_DATA':
            return jsonify({
                'success': False,
                'error': 'Confirmation phrase required'
            }), 400
        
        db = current_app.db
        if not db:
            return jsonify({
                'success': False,
                'error': 'Database connection not available'
            }), 500
        
        # Get user info for logging
        user_identifier = session.get('username') or session.get('user_id')
        
        # Log this dangerous operation
        logger.warning(f"User {user_identifier} initiated system data clearance")
        
        # In a real application, you might want to:
        # 1. Create a backup first
        # 2. Only allow super admins to perform this
        # 3. Implement a soft delete system instead
        
        # For safety, we'll just return success without actually deleting
        # Uncomment the following lines only if you're sure:
        """
        # Clear collections (be extremely careful!)
        db.questions.delete_many({})
        db.quizzes.delete_many({})
        db.quiz_results.delete_many({})
        db.user_sessions.delete_many({})
        # Don't delete admin users and settings
        """
        
        # Log the action
        db.activity_log.insert_one({
            'user_id': user_identifier,
            'action': 'system_data_clearance',
            'timestamp': datetime.utcnow(),
            'details': 'User attempted to clear all system data'
        })
        
        return jsonify({
            'success': True,
            'message': 'System data clearance initiated (safety measures prevent actual deletion in this demo)'
        })
        
    except Exception as e:
        logger.error(f"Error during data clearance: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }), 500

@admin_settings_bp.route('/api/settings/export-data', methods=['POST'])
@admin_required
def export_system_data():
    """Export all system data"""
    try:
        db = current_app.db
        if not db:
            return jsonify({
                'success': False,
                'error': 'Database connection not available'
            }), 500
        
        # Get export format
        data = request.get_json()
        export_format = data.get('format', 'json')
        
        # Collect data from collections
        export_data = {
            'exported_at': datetime.utcnow().isoformat(),
            'exported_by': session.get('username') or session.get('user_id'),
            'collections': {}
        }
        
        # Define collections to export
        collections_to_export = ['questions', 'quizzes', 'quiz_results', 'users', 'settings']
        
        for collection_name in collections_to_export:
            collection = getattr(db, collection_name)
            documents = list(collection.find({}, {'_id': 0}))
            export_data['collections'][collection_name] = documents
        
        # Log the export
        logger.info(f"Data export initiated by user {export_data['exported_by']}")
        
        return jsonify({
            'success': True,
            'message': 'Data export completed',
            'data': export_data,
            'format': export_format
        })
        
    except Exception as e:
        logger.error(f"Error exporting data: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }), 500