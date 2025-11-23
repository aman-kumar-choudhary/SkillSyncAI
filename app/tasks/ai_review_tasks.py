import threading
import time
from datetime import datetime
from app.models.question_models import (
    question_review_collection, 
    add_ai_feedback_to_question,
    mark_question_as_ai_processing,
    get_questions_needing_ai_review
)
from app.services.ai_review_service import ai_review_service
import logging

logger = logging.getLogger(__name__)

class AIReviewProcessor:
    def __init__(self):
        self.is_processing = False
        self.processing_thread = None
        self.processed_count = 0
        self.error_count = 0
    
    def process_pending_questions(self):
        """Process all questions that need AI review"""
        if self.is_processing:
            logger.info("AI review already in progress")
            return
        
        self.is_processing = True
        self.processed_count = 0
        self.error_count = 0
        
        try:
            questions = get_questions_needing_ai_review()
            total_questions = len(questions)
            logger.info(f"Found {total_questions} questions needing AI review")
            
            for i, question in enumerate(questions):
                logger.info(f"Processing question {i+1}/{total_questions}: {question['question_id']}")
                self._process_single_question(question)
                
                # Add small delay to avoid rate limiting
                time.sleep(2)
                
            logger.info(f"AI review completed. Processed: {self.processed_count}, Errors: {self.error_count}")
            
        except Exception as e:
            logger.error(f"Error in AI review process: {str(e)}")
            self.error_count += 1
        finally:
            self.is_processing = False
    
    def _process_single_question(self, question):
        """Process a single question with AI"""
        try:
            question_id = question['question_id']
            
            # Mark as processing
            mark_question_as_ai_processing(question_id)
            
            # Get AI feedback
            ai_feedback = ai_review_service.analyze_question(question)
            
            # Save feedback
            add_ai_feedback_to_question(question_id, ai_feedback)
            
            self.processed_count += 1
            logger.info(f"AI review completed for question {question_id}")
            
        except Exception as e:
            logger.error(f"Error processing question {question.get('question_id', 'unknown')}: {str(e)}")
            self.error_count += 1
    
    def start_background_processing(self):
        """Start background processing thread"""
        if self.processing_thread and self.processing_thread.is_alive():
            logger.info("AI review thread already running")
            return
        
        def process_wrapper():
            try:
                self.process_pending_questions()
            except Exception as e:
                logger.error(f"Error in AI review thread: {str(e)}")
                self.is_processing = False
        
        self.processing_thread = threading.Thread(target=process_wrapper)
        self.processing_thread.daemon = True
        self.processing_thread.start()
        logger.info("AI review background processing started")

# Global processor instance
ai_processor = AIReviewProcessor()