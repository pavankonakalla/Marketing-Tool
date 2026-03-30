import json
import os
import re
from typing import Any, Dict, List

from openai import OpenAI


JOB_KEYWORDS = {
    "job",
    "hiring",
    "position",
    "opening",
    "vacancy",
    "jd",
    "developer",
    "engineer",
    "python",
    "resume",
    "cv",
    "opportunity",
}


def _get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is missing. Add it to environment variables.")
    return OpenAI(api_key=api_key)


def is_job_email(subject: str, body: str) -> bool:
    combined = f"{subject} {body}".lower()
    return any(keyword in combined for keyword in JOB_KEYWORDS)


def extract_structured_data(text: str, record_type: str = "job") -> Dict[str, Any]:
    """Use an LLM to convert unstructured text into a job schema."""
    client = _get_client()
    prompt = f"""
Extract structured data from this {record_type} description.
Return ONLY a JSON object with these keys:
'role', 'skills' (list), 'experience_years' (int), 'domain', 'location', 'visa_required' (bool).

Text: {text[:2500]}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


def fallback_structured_data(subject: str, body: str) -> Dict[str, Any]:
    """Fallback parser if LLM extraction fails."""
    text = f"{subject}\n{body}"
    years_match = re.search(r"(\d+)\+?\s*(?:years|yrs)", text, flags=re.IGNORECASE)
    skills = []
    for token in ["python", "sql", "aws", "azure", "java", "react", "node"]:
        if re.search(rf"\b{re.escape(token)}\b", text, flags=re.IGNORECASE):
            skills.append(token)
    return {
        "role": subject[:120],
        "skills": skills,
        "experience_years": int(years_match.group(1)) if years_match else 0,
        "domain": "unknown",
        "location": "unknown",
        "visa_required": False,
    }


def build_embedding_text(email: Dict[str, Any], structured: Dict[str, Any]) -> str:
    """Create one canonical string for vector embedding."""
    return (
        f"subject: {email.get('subject', '')}\n"
        f"sender: {email.get('sender', '')}\n"
        f"body: {email.get('body', '')}\n"
        f"role: {structured.get('role', '')}\n"
        f"skills: {', '.join(structured.get('skills', []))}\n"
        f"experience_years: {structured.get('experience_years', 0)}\n"
        f"domain: {structured.get('domain', '')}\n"
        f"location: {structured.get('location', '')}\n"
        f"visa_required: {structured.get('visa_required', False)}"
    )


def get_embedding(text: str, model: str = "text-embedding-3-small") -> List[float]:
    """Generate vector embedding using OpenAI embeddings API."""
    client = _get_client()
    response = client.embeddings.create(model=model, input=text[:8000])
    return response.data[0].embedding