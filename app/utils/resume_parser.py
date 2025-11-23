import os
import PyPDF2
import docx
import re
from typing import List, Dict

class ResumeParser:
    def __init__(self):
        self.technical_keywords = {
            'programming_languages': [
                'python', 'java', 'javascript', 'c++', 'c#', 'php', 'ruby', 'go', 'rust', 'swift', 'kotlin',
                'typescript', 'html', 'css', 'sql', 'r', 'matlab', 'scala', 'perl', 'bash', 'shell'
            ],
            'frameworks': [
                'react', 'angular', 'vue', 'django', 'flask', 'spring', 'express', 'laravel', 'ruby on rails',
                'asp.net', 'node.js', 'react native', 'flutter', 'tensorflow', 'pytorch', 'keras'
            ],
            'databases': [
                'mysql', 'postgresql', 'mongodb', 'redis', 'sqlite', 'oracle', 'cassandra', 'dynamodb',
                'firebase', 'elasticsearch'
            ],
            'tools': [
                'docker', 'kubernetes', 'jenkins', 'git', 'aws', 'azure', 'gcp', 'linux', 'unix',
                'jira', 'confluence', 'ansible', 'terraform', 'vagrant'
            ],
            'concepts': [
                'machine learning', 'artificial intelligence', 'data science', 'big data', 'cloud computing',
                'devops', 'agile', 'scrum', 'ci/cd', 'microservices', 'rest api', 'graphql', 'oauth'
            ]
        }
    
    def extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF file"""
        try:
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = ""
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                return text.strip()
        except Exception as e:
            print(f"Error reading PDF {file_path}: {e}")
            return ""
    
    def extract_text_from_docx(self, file_path: str) -> str:
        """Extract text from DOCX file"""
        try:
            doc = docx.Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text += paragraph.text + "\n"
            return text.strip()
        except Exception as e:
            print(f"Error reading DOCX {file_path}: {e}")
            return ""
    
    def extract_text(self, file_path: str) -> str:
        """Extract text from resume file based on extension"""
        if not os.path.exists(file_path):
            return ""
            
        if file_path.lower().endswith('.pdf'):
            return self.extract_text_from_pdf(file_path)
        elif file_path.lower().endswith(('.doc', '.docx')):
            return self.extract_text_from_docx(file_path)
        else:
            return ""
    
    def extract_keywords(self, text: str) -> List[str]:
        """Extract technical keywords from resume text"""
        if not text:
            return []
            
        text_lower = text.lower()
        found_keywords = []
        
        # Extract from predefined technical keywords
        for category, keywords in self.technical_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    found_keywords.append(keyword)
        
        # Extract potential skills using pattern matching
        skill_patterns = [
            r'\b(?:proficient in|experienced with|skills? in|knowledge of|expertise in)[\s\:]*([^\.\n]+)',
            r'\b(?:programming languages?|technologies?|tools?|frameworks?)[\s\:]*([^\.\n]+)',
        ]
        
        for pattern in skill_patterns:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            for match in matches:
                # Extract individual skills from the match
                skills = re.findall(r'\b[a-z+#]+\+*\b', match)
                found_keywords.extend(skills)
        
        # Remove duplicates and clean up
        unique_keywords = list(set([kw.strip() for kw in found_keywords if len(kw.strip()) > 2]))
        
        return unique_keywords[:20]  # Return top 20 keywords

# Global parser instance
resume_parser = ResumeParser()