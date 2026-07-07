"""Service layer wrapping the skill's generate_report.py functions."""
import sys
import os
import json
import uuid

from config import SKILL_SCRIPTS_DIR
if SKILL_SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SKILL_SCRIPTS_DIR)

import generate_report

from config import REPORT_DIR


def generate_word_report(data: dict) -> str:
    """Generate a Word (.docx) report and return the file path."""
    output_filename = f"report_{uuid.uuid4().hex[:8]}.docx"
    output_path = os.path.join(REPORT_DIR, output_filename)

    generate_report.generate_report(data, output_path)

    return output_path, output_filename
