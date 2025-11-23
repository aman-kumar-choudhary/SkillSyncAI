import os
import google.generativeai as genai
from typing import Dict, List, Optional
from dotenv import load_dotenv
import logging
import json
import re

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class AIReviewService:
    def __init__(self):
        self.api_key = os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not found in environment variables. AI review will be disabled.")
            self.enabled = False
            return
        
        try:
            # Test the API key with a simple call
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.5-flash')  # Use gemini-pro instead of flash
            
            # Test the configuration with a simple prompt
            test_response = self.model.generate_content("Say 'OK' if working")
            self.enabled = True
            logger.info("AI Review Service initialized successfully with Gemini")
            
        except Exception as e:
            logger.error(f"Failed to initialize AI Review Service: {str(e)}")
            logger.error("Please check your GEMINI_API_KEY and ensure it's valid")
            self.enabled = False
    
    def analyze_question(self, question_data: Dict) -> Dict:
        """
        Analyze a question and provide AI feedback
        """
        if not self.enabled:
            return {
                "suggestions": ["AI review is currently disabled. Please check your GEMINI_API_KEY configuration."],
                "confidence_score": 0,
                "status": "ai_disabled",
                "feedback": "AI review is currently disabled",
                "overall_quality": "unknown"
            }
        
        try:
            prompt = self._build_prompt(question_data)
            response = self.model.generate_content(prompt)
            
            return self._parse_response(response.text, question_data)
            
        except Exception as e:
            logger.error(f"Error analyzing question: {str(e)}")
            return {
                "suggestions": [f"AI analysis failed: {str(e)}"],
                "confidence_score": 0,
                "status": "error",
                "feedback": "Failed to analyze question",
                "overall_quality": "unknown"
            }
    
    def _build_prompt(self, question_data: Dict) -> str:
        """Build the prompt for Gemini AI with clear, interactive feedback instructions"""
        question_text = question_data.get('text', '')
        options = question_data.get('options', [])
        correct_answer = question_data.get('correct_answer', '')
        
        prompt = f"""
        Analyze this multiple-choice question and provide clear, actionable, and professional feedback.

        QUESTION: {question_text}

        OPTIONS:
        {chr(10).join([f"{i+1}. {opt}" for i, opt in enumerate(options)])}

        CORRECT ANSWER: {correct_answer}

        Provide feedback in this EXACT JSON format only - no additional text, no markdown, no explanations:

        {{
            "overall_quality": "excellent|good|fair|poor",
            "confidence_score": 0.85,
            "suggestions": [
                "Clear, actionable suggestion phrased as guidance",
                "Another specific improvement recommendation"
            ],
            "specific_issues": [
                "Brief description of any identified issues"
            ],
            "recommended_changes": [
                "Specific change recommendation"
            ],
            "improved_question": "Optional improved version if needed, otherwise keep original",
            "improved_options": ["Option 1", "Option 2", "Option 3", "Option 4"]
        }}

        CRITICAL INSTRUCTIONS:
        - Provide suggestions that are clear, professional, and easy to understand
        - Use natural, conversational language that feels helpful
        - Focus on actionable improvements that enhance question quality
        - DO NOT use emojis, symbols, or markdown formatting
        - Keep suggestions concise but meaningful (2-3 suggestions maximum)
        - Phrase feedback as constructive guidance rather than criticism
        - If the question is well-written, provide positive reinforcement with minor optimization tips
        - Return ONLY the JSON object, nothing else before or after

        Focus your analysis on:
        1. Clarity and precision of the question stem
        2. Relevance and quality of answer options
        3. Unambiguous correctness of the designated answer
        4. Overall educational effectiveness
        """
        
        return prompt
    
    def _parse_response(self, response_text: str, question_data: Dict) -> Dict:
        """Parse the AI response with better error handling and emoji filtering"""
        try:
            # Clean the response text - remove any markdown, code blocks, etc.
            cleaned_text = response_text.strip()
            cleaned_text = re.sub(r'```json\s*|\s*```', '', cleaned_text)  # Remove code blocks
            cleaned_text = re.sub(r'^[^{]*', '', cleaned_text)  # Remove anything before first {
            cleaned_text = re.sub(r'[^}]*$', '', cleaned_text)  # Remove anything after last }
            
            # Remove any emojis or symbols
            emoji_pattern = re.compile(
                "["
                "\U0001F600-\U0001F64F"  # emoticons
                "\U0001F300-\U0001F5FF"  # symbols & pictographs
                "\U0001F680-\U0001F6FF"  # transport & map symbols
                "\U0001F1E0-\U0001F1FF"  # flags (iOS)
                "\U00002700-\U000027BF"  # dingbats
                "\U0001F900-\U0001F9FF"  # supplemental symbols and pictographs
                "]+", flags=re.UNICODE
            )
            cleaned_text = emoji_pattern.sub('', cleaned_text)
            
            # Try to parse JSON
            ai_feedback = json.loads(cleaned_text)
            
            # Process suggestions to ensure they're clean and readable
            suggestions = ai_feedback.get("suggestions", [])
            cleaned_suggestions = []
            
            for suggestion in suggestions[:3]:  # Limit to 3 suggestions
                # Clean each suggestion
                clean_suggestion = emoji_pattern.sub('', suggestion)
                clean_suggestion = re.sub(r'[•\-*]\s*', '', clean_suggestion)  # Remove bullet points
                clean_suggestion = clean_suggestion.strip()
                if clean_suggestion and len(clean_suggestion) > 5:  # Meaningful length
                    cleaned_suggestions.append(clean_suggestion)
            
            # Ensure we have at least one suggestion if there were issues
            if not cleaned_suggestions and ai_feedback.get("overall_quality", "good") in ["fair", "poor"]:
                cleaned_suggestions = ["Consider reviewing the question for clarity and option relevance"]
            
            return {
                "suggestions": cleaned_suggestions,
                "specific_issues": ai_feedback.get("specific_issues", [])[:2],
                "recommended_changes": ai_feedback.get("recommended_changes", [])[:2],
                "confidence_score": min(max(ai_feedback.get("confidence_score", 0.5), 0), 1),
                "overall_quality": ai_feedback.get("overall_quality", "unknown"),
                "improved_question": ai_feedback.get("improved_question", question_data.get('text', '')),
                "improved_options": ai_feedback.get("improved_options", question_data.get('options', [])),
                "status": "analyzed"
            }
            
        except Exception as e:
            logger.error(f"Error parsing AI response: {str(e)}. Response was: {response_text[:500]}")
            # Return minimal feedback on error
            return {
                "suggestions": ["AI analysis completed but response format was unexpected. Please review the question manually."],
                "confidence_score": 0.3,
                "status": "analyzed",
                "feedback": "Analysis completed with formatting issues",
                "overall_quality": "unknown",
                "improved_question": question_data.get('text', ''),
                "improved_options": question_data.get('options', [])
            }

# Singleton instance
ai_review_service = AIReviewService()