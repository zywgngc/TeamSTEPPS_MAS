"""Strict explicit-option parsing, retaining balanced author quote wrappers."""
import re
from .runtime import normalize_label


def _v5_choice(text,options):
    direct=normalize_label(text,options)
    if direct is not None:return direct
    cleaned=re.sub(r'[*`]+','',str(text)).strip()
    markers=list(re.finditer(
        r'(?i)\b(?:the\s+)?(?:(?:final|correct|best)\s+)*(?:answer|option|choice)\s*'
        r'(?:[:=]|is\s*:?)\s*\[?\(?([A-E])(?=[\s)\].,;:]|$)',cleaned))
    if not markers:return None
    chosen=markers[-1]
    tail=cleaned[chosen.end():]
    # Explicit uncertainty between choices is not resolved by a scorer.
    alternative=(r'(?i)(?:\b(?:or|and|but|perhaps|maybe|alternatively|versus|vs|however)\b'
                 r'\s*(?:perhaps\s+|maybe\s+|option\s+|answer\s+|choice\s+)?|[/|])'
                 r'\s*\(?[A-E](?=[\s)\].,;:]|$)')
    if re.search(alternative,tail):return None
    if re.match(r'[\s)\].,:;]*(?:is\s+)?(?:incorrect|wrong|not\s+(?:correct|the\s+answer))\b',tail,re.I):
        return None
    return normalize_label(chosen.group(1),options)

def unwrap_quotes(text):
    cleaned = re.sub(r"[*`]+", "", str(text)).strip()
    for _ in range(4):
        quote = next((q for q in ("'''", '\"\"\"', "'", '\"') if cleaned.startswith(q)), None)
        if quote is None or len(cleaned) < 2 * len(quote) or not cleaned.endswith(quote):
            return cleaned
        cleaned = cleaned[len(quote):-len(quote)].strip()
    return cleaned

def final_choice(text, options):
    cleaned = unwrap_quotes(text)
    # The author format may occupy the last line after a prose explanation.
    declaration = (r"(?<!['\"])(?P<quote>'''|\"\"\"|'|\")"
        r"(?P<declaration>(?:the\s+)?(?:(?:final|correct|best)\s+)*"
        r"(?:answer|option|choice)\s*(?:[:=]|is\s*:?)\s*[^\r\n]*?)"
        r"(?P=quote)(?!['\"])")
    cleaned = re.sub(declaration, lambda match: match.group('declaration'), cleaned, flags=re.I)
    return _v5_choice(cleaned, options)
