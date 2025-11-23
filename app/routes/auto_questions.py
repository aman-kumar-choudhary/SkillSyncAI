from flask import Blueprint, request, jsonify
from app import get_db
from app.utils.decorators import admin_required
from app.utils.helpers import create_admin_notification, log_activity
from app.utils.resume_parser import resume_parser
from datetime import datetime
import os
import uuid
import requests
import random
from bson import ObjectId
import json

auto_questions_bp = Blueprint('auto_questions', __name__)

class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

class ResumeQuestionGenerator:
    def __init__(self):
        self.question_templates = self.load_question_templates()
    
    def load_question_templates(self):
        """Load predefined question templates for various technologies"""
        return {
            'python': [
                {
                    'text': "What is the primary use of Python in software development?",
                    'options': [
                        "Web development only",
                        "Data science, AI, web development, and automation",
                        "Mobile app development",
                        "System programming"
                    ],
                    'correct_answer': "Data science, AI, web development, and automation",
                    'explanation': "Python is versatile and used in data science, AI, web development, automation, and more."
                },
                {
                    'text': "Which of the following is NOT a Python web framework?",
                    'options': [
                        "Django",
                        "Flask",
                        "Spring",
                        "FastAPI"
                    ],
                    'correct_answer': "Spring",
                    'explanation': "Spring is a Java framework, while Django, Flask, and FastAPI are Python web frameworks."
                },
                {
                    'text': "What does PEP 8 refer to in Python?",
                    'options': [
                        "Python Enhancement Proposal for code style",
                        "A Python package manager",
                        "A Python web framework",
                        "A Python version number"
                    ],
                    'correct_answer': "Python Enhancement Proposal for code style",
                    'explanation': "PEP 8 is the style guide for Python code that promotes readability and consistency."
                }
            ],
            'javascript': [
                {
                    'text': "What is JavaScript primarily used for in web development?",
                    'options': [
                        "Server-side programming only",
                        "Adding interactivity to web pages",
                        "Database management",
                        "CSS styling"
                    ],
                    'correct_answer': "Adding interactivity to web pages",
                    'explanation': "JavaScript is mainly used for client-side scripting to make web pages interactive."
                },
                {
                    'text': "Which of the following is NOT a JavaScript framework?",
                    'options': [
                        "React",
                        "Angular",
                        "Vue",
                        "Django"
                    ],
                    'correct_answer': "Django",
                    'explanation': "Django is a Python web framework, not a JavaScript framework."
                }
            ],
            'java': [
                {
                    'text': "What is the main principle of Object-Oriented Programming in Java?",
                    'options': [
                        "Functional programming",
                        "Encapsulation, Inheritance, Polymorphism",
                        "Procedural programming",
                        "Template-based programming"
                    ],
                    'correct_answer': "Encapsulation, Inheritance, Polymorphism",
                    'explanation': "Java OOP is based on encapsulation, inheritance, and polymorphism principles."
                },
                {
                    'text': "Which of the following is NOT a Java access modifier?",
                    'options': [
                        "public",
                        "private",
                        "protected",
                        "internal"
                    ],
                    'correct_answer': "internal",
                    'explanation': "Java has public, private, protected, and default (package-private) access modifiers, but not 'internal'."
                }
            ],
            'react': [
                {
                    'text': "What is React primarily used for?",
                    'options': [
                        "Backend development",
                        "Building user interfaces",
                        "Database management",
                        "Mobile app development only"
                    ],
                    'correct_answer': "Building user interfaces",
                    'explanation': "React is a JavaScript library for building user interfaces, especially web applications."
                },
                {
                    'text': "What is JSX in React?",
                    'options': [
                        "A JavaScript testing framework",
                        "A syntax extension for JavaScript that looks like HTML",
                        "A state management library",
                        "A build tool for React"
                    ],
                    'correct_answer': "A syntax extension for JavaScript that looks like HTML",
                    'explanation': "JSX allows you to write HTML-like syntax in JavaScript code in React components."
                }
            ],
            'machine learning': [
                {
                    'text': "What is the difference between supervised and unsupervised learning?",
                    'options': [
                        "Supervised uses labeled data, unsupervised uses unlabeled data",
                        "Supervised is faster than unsupervised",
                        "Unsupervised uses labeled data, supervised uses unlabeled data",
                        "There is no difference"
                    ],
                    'correct_answer': "Supervised uses labeled data, unsupervised uses unlabeled data",
                    'explanation': "Supervised learning uses labeled training data, while unsupervised learning finds patterns in unlabeled data."
                }
            ],
            'sql': [
                {
                    'text': "What does SQL stand for?",
                    'options': [
                        "Structured Question Language",
                        "Structured Query Language", 
                        "Simple Query Language",
                        "System Query Language"
                    ],
                    'correct_answer': "Structured Query Language",
                    'explanation': "SQL stands for Structured Query Language, used for managing relational databases."
                },
                {
                    'text': "Which SQL clause is used to filter records?",
                    'options': [
                        "SELECT",
                        "FROM",
                        "WHERE",
                        "GROUP BY"
                    ],
                    'correct_answer': "WHERE",
                    'explanation': "The WHERE clause is used to filter records based on specified conditions."
                }
            ],
            'docker': [
                {
                    'text': "What is the main purpose of Docker?",
                    'options': [
                        "Virtual machine management",
                        "Containerization of applications",
                        "Network configuration",
                        "Database optimization"
                    ],
                    'correct_answer': "Containerization of applications",
                    'explanation': "Docker is used to containerize applications for consistent deployment across environments."
                }
            ],
            'aws': [
                {
                    'text': "What is Amazon S3 primarily used for?",
                    'options': [
                        "Running virtual servers",
                        "Object storage service",
                        "Database management",
                        "Content delivery network"
                    ],
                    'correct_answer': "Object storage service",
                    'explanation': "Amazon S3 is an object storage service for storing and retrieving any amount of data."
                }
            ],
            'git': [
                {
                    'text': "What is the purpose of 'git clone' command?",
                    'options': [
                        "To create a new branch",
                        "To copy a repository from remote to local",
                        "To commit changes",
                        "To merge branches"
                    ],
                    'correct_answer': "To copy a repository from remote to local",
                    'explanation': "git clone is used to create a local copy of a remote repository."
                }
            ]
        }
    
    def extract_keywords_from_resume(self, resume_text):
        """Extract keywords using the resume parser"""
        return resume_parser.extract_keywords(resume_text)
    
    def generate_questions_from_keywords(self, keywords, count=10, difficulty='intermediate', question_type='mixed'):
        """Generate questions based on extracted keywords"""
        questions = []
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            
            # Find matching templates for this keyword
            matching_templates = []
            for template_key, template_questions in self.question_templates.items():
                if template_key in keyword_lower:
                    matching_templates.extend(template_questions)
            
            # If no direct match, try partial matching
            if not matching_templates:
                for template_key in self.question_templates.keys():
                    if template_key in keyword_lower or keyword_lower in template_key:
                        matching_templates.extend(self.question_templates[template_key])
            
            # Add matching templates to questions
            for template in matching_templates[:2]:  # Max 2 questions per keyword
                if len(questions) >= count:
                    break
                    
                question_data = {
                    'text': template['text'],
                    'options': template['options'],
                    'correct_answer': template['correct_answer'],
                    'explanation': template.get('explanation', ''),
                    'keyword': keyword,
                    'source': 'auto_generated',
                    'difficulty': difficulty
                }
                questions.append(question_data)
        
        # If we don't have enough questions, add some general ones
        if len(questions) < count:
            general_questions = self.get_general_questions(count - len(questions))
            questions.extend(general_questions)
        
        return questions[:count]
    
    def get_general_questions(self, count):
        """Get general technical questions"""
        general_templates = [
            {
                'text': "What is version control primarily used for?",
                'options': [
                    "Tracking changes in source code",
                    "Managing computer hardware",
                    "Creating user interfaces", 
                    "Database backup"
                ],
                'correct_answer': "Tracking changes in source code",
                'explanation': "Version control systems like Git help track changes in source code during development.",
                'keyword': 'version control',
                'source': 'auto_generated',
                'difficulty': 'easy'
            },
            {
                'text': "What is the purpose of an API?",
                'options': [
                    "To create user interfaces",
                    "To allow software applications to communicate with each other",
                    "To manage databases",
                    "To write documentation"
                ],
                'correct_answer': "To allow software applications to communicate with each other",
                'explanation': "API (Application Programming Interface) enables different software systems to communicate.",
                'keyword': 'api',
                'source': 'auto_generated',
                'difficulty': 'intermediate'
            },
            {
                'text': "What is Agile methodology focused on?",
                'options': [
                    "Detailed upfront planning",
                    "Iterative development and customer feedback",
                    "Fixed scope and timeline",
                    "Comprehensive documentation"
                ],
                'correct_answer': "Iterative development and customer feedback",
                'explanation': "Agile methodology emphasizes iterative development, collaboration, and responding to change.",
                'keyword': 'agile',
                'source': 'auto_generated',
                'difficulty': 'intermediate'
            },
            {
                'text': "What is the main advantage of cloud computing?",
                'options': [
                    "Higher hardware costs",
                    "Scalability and cost-efficiency",
                    "Limited accessibility",
                    "Complex setup process"
                ],
                'correct_answer': "Scalability and cost-efficiency",
                'explanation': "Cloud computing provides scalable resources and pay-as-you-go pricing model.",
                'keyword': 'cloud computing',
                'source': 'auto_generated',
                'difficulty': 'intermediate'
            }
        ]
        
        return general_templates[:count]

# Global question generator instance
question_generator = ResumeQuestionGenerator()

def serialize_document(doc):
    """Convert MongoDB document to JSON-serializable format"""
    if doc is None:
        return None
    
    if isinstance(doc, list):
        return [serialize_document(item) for item in doc]
    
    if isinstance(doc, dict):
        result = {}
        for key, value in doc.items():
            if isinstance(value, ObjectId):
                result[key] = str(value)
            elif isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, (list, dict)):
                result[key] = serialize_document(value)
            else:
                result[key] = value
        return result
    
    return doc

@auto_questions_bp.route('/api/generate-questions-from-resumes', methods=['POST'])
@admin_required
def generate_questions_from_resumes():
    """Generate questions from selected student resumes"""
    try:
        data = request.get_json()
        student_ids = data.get('student_ids', [])
        question_count = int(data.get('question_count', 10))
        difficulty = data.get('difficulty', 'intermediate')
        question_type = data.get('question_type', 'mixed')
        selected_keywords = data.get('selected_keywords', [])
        
        if not student_ids:
            return jsonify({'success': False, 'error': 'No students selected'})
        
        db = get_db()
        all_generated_questions = []
        
        for scholar_id in student_ids:
            # Get student and their resume data
            student = db.users.find_one({'scholar_id': scholar_id})
            if not student or not student.get('resume_filename'):
                continue
            
            # Extract text from resume file
            resume_path = os.path.join('app', 'static', 'uploads', 'resumes', student['resume_filename'])
            if not os.path.exists(resume_path):
                continue
            
            resume_text = resume_parser.extract_text(resume_path)
            if not resume_text:
                continue
            
            # Extract keywords from resume text
            resume_keywords = resume_parser.extract_keywords(resume_text)
            
            if not resume_keywords:
                continue
            
            # Update student record with extracted keywords
            db.users.update_one(
                {'scholar_id': scholar_id},
                {'$set': {
                    'resume_keywords': resume_keywords, 
                    'resume_processed': True,
                    'resume_text_extracted': True
                }}
            )
            
            # Use selected keywords or all keywords
            keywords_to_use = selected_keywords if selected_keywords else resume_keywords
            
            # Generate questions based on keywords
            questions = question_generator.generate_questions_from_keywords(
                keywords_to_use, 
                question_count, 
                difficulty, 
                question_type
            )
            
            # Save questions to database
            for question in questions:
                question_id = str(uuid.uuid4())
                question_data = {
                    'question_id': question_id,
                    'text': question['text'],
                    'options': question['options'],
                    'correct_answer': question['correct_answer'],
                    'difficulty': difficulty,
                    'tags': [question['keyword'], 'auto_generated', question_type],
                    'source': 'auto_generated',
                    'generated_from': scholar_id,
                    'status': 'pending_review',
                    'created_at': datetime.now(),
                    'ai_generated': True,
                    'explanation': question.get('explanation', '')
                }
                
                # Save to questions collection
                result = db.questions.insert_one(question_data)
                question_data['_id'] = str(result.inserted_id)
                all_generated_questions.append(serialize_document(question_data))
        
        create_admin_notification(
            "Questions Generated",
            f"Generated {len(all_generated_questions)} questions from {len(student_ids)} resumes",
            "success"
        )
        
        log_activity(
            "questions_auto_generated",
            f"Generated {len(all_generated_questions)} questions from resumes"
        )
        
        return jsonify({
            'success': True,
            'message': f'Successfully generated {len(all_generated_questions)} questions',
            'generated_count': len(all_generated_questions),
            'questions': all_generated_questions
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error generating questions: {str(e)}'})

@auto_questions_bp.route('/api/extract-keywords', methods=['POST'])
@admin_required
def extract_keywords():
    """Extract keywords from selected student resumes"""
    try:
        data = request.get_json()
        student_ids = data.get('student_ids', [])
        
        if not student_ids:
            return jsonify({'success': False, 'error': 'No students selected'})
        
        db = get_db()
        all_keywords = set()
        processed_students = 0
        
        for scholar_id in student_ids:
            student = db.users.find_one({'scholar_id': scholar_id})
            if not student or not student.get('resume_filename'):
                continue
            
            # Check if we already have keywords
            if student.get('resume_keywords'):
                all_keywords.update(student['resume_keywords'])
                processed_students += 1
                continue
            
            # Extract keywords from resume file
            resume_path = os.path.join('app', 'static', 'uploads', 'resumes', student['resume_filename'])
            if not os.path.exists(resume_path):
                continue
            
            resume_text = resume_parser.extract_text(resume_path)
            if not resume_text:
                continue
            
            keywords = resume_parser.extract_keywords(resume_text)
            if keywords:
                all_keywords.update(keywords)
                
                # Update student record
                db.users.update_one(
                    {'scholar_id': scholar_id},
                    {'$set': {
                        'resume_keywords': keywords,
                        'resume_processed': True,
                        'resume_text_extracted': True
                    }}
                )
                processed_students += 1
        
        return jsonify({
            'success': True,
            'keywords': list(all_keywords),
            'total_keywords': len(all_keywords),
            'processed_students': processed_students
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error extracting keywords: {str(e)}'})