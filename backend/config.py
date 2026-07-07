"""Application configuration."""
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Path to skill scripts (bundled copy first, then original local path)
_BUNDLED = os.path.join(os.path.dirname(__file__), 'skill_scripts')
_LOCAL = os.path.join(os.path.dirname(__file__), '..', '..', '.claude', 'skills', 'building-energy-analysis', 'scripts')
SKILL_SCRIPTS_DIR = os.getenv('SKILL_SCRIPTS_DIR', _BUNDLED if os.path.isdir(_BUNDLED) else os.path.abspath(_LOCAL))

# Path to SKILL.md (for system prompt)
_BUNDLED_MD = os.path.join(_BUNDLED, 'SKILL.md')
_LOCAL_MD = os.path.join(os.path.dirname(os.path.abspath(_LOCAL)), 'SKILL.md')
SKILL_MD_PATH = _BUNDLED_MD if os.path.isfile(_BUNDLED_MD) else _LOCAL_MD

# Upload constraints
MAX_UPLOAD_SIZE_MB = int(os.getenv('MAX_UPLOAD_SIZE_MB', '20'))
UPLOAD_DIR = os.getenv('UPLOAD_DIR', os.path.join(os.path.dirname(__file__), 'data', 'uploads'))
REPORT_DIR = os.getenv('REPORT_DIR', os.path.join(os.path.dirname(__file__), 'data', 'reports'))

# File retention (hours)
FILE_RETENTION_HOURS = int(os.getenv('FILE_RETENTION_HOURS', '24'))

# CORS
CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:5173').split(',')

# LLM Configuration
LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'anthropic')  # anthropic | deepseek
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
DEEPSEEK_BASE_URL = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')

# Ensure data directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)
