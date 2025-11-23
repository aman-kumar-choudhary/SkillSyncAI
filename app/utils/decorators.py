from functools import wraps
from flask import session, redirect, url_for, abort, make_response, flash
from app.utils.helpers import ROLES
from app.models.user_models import users_collection

def login_required(f):
    """Decorator to require login for any user"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user is logged in
        if 'username' not in session and 'scholar_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('auth.login'))
        
        # Check if user is blocked (for students)
        if session.get('role') == 'student':
            user = users_collection.find_one({'scholar_id': session['scholar_id']})
            if user and user.get('blocked', False):
                session.clear()
                flash('Your account has been blocked. Please contact administrator.', 'error')
                return redirect(url_for('auth.login'))
        
        # Set cache control headers to prevent back button issues
        response = make_response(f(*args, **kwargs))
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        response.headers['X-Accel-Expires'] = '0'
        return response
    return decorated_function

def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user is logged in as admin
        if 'role' not in session:
            flash('Administrator access required.', 'error')
            return redirect(url_for('auth.admin_login'))
        
        # Allow super admin and admin users
        user_role = session.get('role')
        if user_role not in ['admin', 'faculty', 'coordinator', 'moderator']:
            flash('Administrator access required.', 'error')
            return redirect(url_for('auth.admin_login'))
        
        return f(*args, **kwargs)
    return decorated_function

def student_required(f):
    """Decorator to require student access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'scholar_id' not in session or session.get('role') != 'student':
            flash('Student access required.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def permission_required(permission):
    """Decorator to check if user has specific permission"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get('user_type') == 'super_admin':
                return f(*args, **kwargs)
            
            user_permissions = session.get('permissions', [])
            if permission not in user_permissions:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def role_required(min_role_level):
    """Decorator to check if user has minimum role level"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get('user_type') == 'super_admin':
                return f(*args, **kwargs)
            
            user_role = session.get('role')
            user_level = ROLES.get(user_role, {}).get('level', 0)
            
            if user_level < min_role_level:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def faculty_required(f):
    """Decorator to require faculty access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'role' not in session:
            flash('Faculty access required.', 'error')
            return redirect(url_for('auth.admin_login'))
        
        user_role = session.get('role')
        if user_role not in ['admin', 'faculty']:
            flash('Faculty access required.', 'error')
            return redirect(url_for('auth.admin_login'))
        
        return f(*args, **kwargs)
    return decorated_function

def coordinator_required(f):
    """Decorator to require coordinator access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'role' not in session:
            flash('Coordinator access required.', 'error')
            return redirect(url_for('auth.admin_login'))
        
        user_role = session.get('role')
        if user_role not in ['admin', 'coordinator']:
            flash('Coordinator access required.', 'error')
            return redirect(url_for('auth.admin_login'))
        
        return f(*args, **kwargs)
    return decorated_function

def no_cache(f):
    """Decorator to set no-cache headers"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        response = f(*args, **kwargs)
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    return decorated_function