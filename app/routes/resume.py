from flask import Blueprint, request, jsonify, session, send_file
from app import get_db
from app.utils.decorators import login_required, admin_required, student_required
from app.utils.helpers import create_admin_notification, log_activity
from datetime import datetime
import os
import uuid
from werkzeug.utils import secure_filename
from bson import ObjectId

resume_bp = Blueprint('resume', __name__)

# Configuration
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@resume_bp.route('/api/upload-resume', methods=['POST'])
@login_required
def upload_resume():
    """Upload student resume"""
    if 'resume' not in request.files:
        return jsonify({'success': False, 'error': 'No file selected'})
    
    file = request.files['resume']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'})
    
    if file and allowed_file(file.filename):
        # Check file size
        file.seek(0, 2)  # Seek to end to get size
        file_size = file.tell()
        file.seek(0)  # Reset file pointer
        if file_size > MAX_FILE_SIZE:
            return jsonify({'success': False, 'error': 'File size exceeds 5MB limit'})
        
        scholar_id = session.get('scholar_id')
        if not scholar_id:
            return jsonify({'success': False, 'error': 'User not logged in'})
        
        # Create uploads directory if it doesn't exist
        upload_dir = os.path.join('app', 'static', 'uploads', 'resumes')
        os.makedirs(upload_dir, exist_ok=True)
        
        # Generate unique filename
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{scholar_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_extension}"
        filename = secure_filename(unique_filename)
        file_path = os.path.join(upload_dir, filename)
        
        try:
            file.save(file_path)
            
            # Update user record in database
            db = get_db()
            db.users.update_one(
                {'scholar_id': scholar_id},
                {
                    '$set': {
                        'resume_filename': filename,
                        'resume_original_name': file.filename,
                        'resume_uploaded_at': datetime.now(),
                        'resume_processed': False,
                        'resume_keywords': []
                    }
                }
            )
            
            create_admin_notification(
                "Resume Uploaded",
                f"Student {scholar_id} uploaded a resume",
                "info",
                scholar_id
            )
            
            log_activity(
                "resume_uploaded",
                f"Resume uploaded: {file.filename}",
                scholar_id
            )
            
            return jsonify({
                'success': True, 
                'message': 'Resume uploaded successfully',
                'filename': file.filename
            })
            
        except Exception as e:
            return jsonify({'success': False, 'error': f'Error saving file: {str(e)}'})
    
    return jsonify({'success': False, 'error': 'Invalid file type. Allowed: PDF, DOC, DOCX'})

@resume_bp.route('/api/delete-resume', methods=['POST'])
@login_required
def delete_resume():
    """Delete student resume"""
    scholar_id = session.get('scholar_id')
    if not scholar_id:
        return jsonify({'success': False, 'error': 'User not logged in'})
    
    try:
        db = get_db()
        user = db.users.find_one({'scholar_id': scholar_id})
        
        if user and user.get('resume_filename'):
            # Delete file
            file_path = os.path.join('app', 'static', 'uploads', 'resumes', user['resume_filename'])
            if os.path.exists(file_path):
                os.remove(file_path)
            
            # Update database
            db.users.update_one(
                {'scholar_id': scholar_id},
                {
                    '$unset': {
                        'resume_filename': '',
                        'resume_original_name': '',
                        'resume_uploaded_at': '',
                        'resume_processed': '',
                        'resume_keywords': ''
                    }
                }
            )
            
            log_activity(
                "resume_deleted",
                "Resume deleted",
                scholar_id
            )
            
            return jsonify({'success': True, 'message': 'Resume deleted successfully'})
        else:
            return jsonify({'success': False, 'error': 'No resume found'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error deleting resume: {str(e)}'})

@resume_bp.route('/api/download-resume')
@login_required
def download_resume():
    """Download student resume"""
    scholar_id = session.get('scholar_id')
    if not scholar_id:
        return jsonify({'success': False, 'error': 'User not logged in'})
    
    db = get_db()
    user = db.users.find_one({'scholar_id': scholar_id})
    
    if user and user.get('resume_filename'):
        file_path = os.path.join('app', 'static', 'uploads', 'resumes', user['resume_filename'])
        if os.path.exists(file_path):
            return send_file(
                file_path,
                as_attachment=True,
                download_name=user['resume_original_name'] or user['resume_filename']
            )
    
    return jsonify({'success': False, 'error': 'Resume not found'})

@resume_bp.route('/api/students-with-resumes')
@admin_required
def get_students_with_resumes():
    """Get list of students with uploaded resumes for admin"""
    try:
        db = get_db()
        students = list(db.users.find(
            {'resume_filename': {'$exists': True, '$ne': None}},
            {
                'scholar_id': 1,
                'name': 1,
                'course': 1,
                'semester': 1,
                'resume_filename': 1,
                'resume_original_name': 1,
                'resume_uploaded_at': 1,
                'resume_processed': 1,
                'resume_keywords': 1
            }
        ).sort('resume_uploaded_at', -1))
        
        # Convert ObjectId and datetime for JSON serialization
        for student in students:
            student['_id'] = str(student['_id'])
            if student.get('resume_uploaded_at'):
                student['resume_uploaded_at'] = student['resume_uploaded_at'].isoformat()
        
        return jsonify({'success': True, 'students': students})
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error fetching students: {str(e)}'})