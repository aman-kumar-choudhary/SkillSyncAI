from app import get_db
from datetime import datetime

# Collection getters
def get_questions_collection():
    return get_db().questions

def get_question_review_collection():
    return get_db().question_review

def get_question_bank_collection():
    return get_db().question_bank

# Shortcut variables for easy access
questions_collection = get_questions_collection()
question_review_collection = get_question_review_collection()
question_bank_collection = get_question_bank_collection()

def add_ai_feedback_to_question(question_id: str, ai_feedback: dict):
    """Add AI feedback to a question in review"""
    return question_review_collection.update_one(
        {"question_id": question_id},
        {
            "$set": {
                "ai_feedback": ai_feedback,
                "ai_analyzed_at": datetime.now(),
                "status": "ai_reviewed"
            }
        }
    )

def mark_question_as_ai_processing(question_id: str):
    """Mark question as being processed by AI"""
    return question_review_collection.update_one(
        {"question_id": question_id},
        {
            "$set": {
                "ai_feedback": {"status": "processing"},
                "status": "ai_processing"
            }
        }
    )

def get_questions_needing_ai_review():
    """Get questions that need AI review"""
    return list(question_review_collection.find({
        "$or": [
            {"ai_feedback": {"$exists": False}},
            {"ai_feedback.status": {"$in": ["error", "ai_disabled"]}},
            {"status": "pending_review"}
        ]
    }))

def update_question_with_ai_suggestions(question_id: str, updated_data: dict):
    """Update question with AI-suggested changes"""
    return question_review_collection.update_one(
        {"question_id": question_id},
        {
            "$set": {
                **updated_data,
                "ai_applied": True,
                "ai_applied_at": datetime.now()
            }
        }
    )