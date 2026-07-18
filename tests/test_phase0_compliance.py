import re
import os

def load_file_content(relative_path):
    # Determine the directory of the current test file and construct absolute path
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    file_path = os.path.join(base_dir, relative_path)
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def test_whatsapp_templates_compliance():
    content = load_file_content("ops/whatsapp_templates.md")
    
    # 1. Verify existence of the 8 required templates
    required_templates = [
        "T_MISSED_CALL_BRIDGE",
        "T_BOOKING_CONFIRMATION",
        "T_REMINDER_24H",
        "T_REMINDER_2H",
        "T_PAYMENT_LINK",
        "T_STAFF_ALERT",
        "T_WEEKLY_SUMMARY",
        "T_CSAT_REQUEST"
    ]
    
    for template in required_templates:
        assert template in content, f"Template {template} is missing from the templates pack!"

    # 2. Verify all 4 languages exist for each template block
    required_languages = ["English (en)", "Hindi (hi)", "Hinglish (hi-Latn)", "Odia (or)"]
    
    # Split the file by template sections
    sections = re.split(r"##\s+\d+\.\s+T_", content)[1:]
    assert len(sections) == 8, f"Expected 8 template sections, found {len(sections)}."
    
    for idx, section in enumerate(sections):
        template_name = required_templates[idx]
        for lang in required_languages:
            assert lang in section, f"Language '{lang}' is missing in template {template_name}!"

    # 3. Check for disrespectful register (no informal pronouns tu/tum/tuma/tu in Hindi, Hinglish, or Odia)
    # Disallowed words: तू, तुम, तेरा, तुम्हारा, तुझे, तुम्हें (Hindi)
    # tu, tum, tera, tumhara, tuje, tumhein, tumne, tere, teri (Hinglish)
    # ତୁ (tu), ତୁମ (tuma), ତୋର (tora), ତତେ (tate) (Odia)
    disallowed_words = {
        # Hindi
        "तू", "तुम", "तेरा", "तुम्हारा", "तुझे", "तुम्हें",
        # Hinglish
        "tu", "tum", "tera", "tumhara", "tuje", "tumhein", "tumne", "tere", "teri",
        # Odia
        "ତୁ", "ତୁମ", "ତୋର", "ତତେ"
    }
    
    # Search within non-English parts of the sections
    for idx, section in enumerate(sections):
        template_name = required_templates[idx]
        # Remove the English block to avoid false positives (like "button", "status", etc.)
        non_english_content = re.sub(r"###\s+English\s+\(en\).*?(?=###|$)", "", section, flags=re.DOTALL)
        
        # Tokenize using Indic and alphanumeric ranges
        tokens = re.findall(r"[\u0900-\u097f\u0b00-\u0b7f\w']+", non_english_content, re.UNICODE)
        
        for token in tokens:
            token_lower = token.lower()
            assert token_lower not in disallowed_words, (
                f"Disallowed informal pronoun/register match '{token}' found in template {template_name}! "
                f"Please ensure respectful register (आप / ଆପଣ) is used exclusively."
            )

def test_dpdp_notice_compliance():
    content = load_file_content("ops/dpdp_notice.md")
    
    # 1. Verify existence of the WhatsApp notice in all 4 languages
    assert "English (en)" in content
    assert "Hindi (hi)" in content
    assert "Hinglish (hi-Latn)" in content
    assert "Odia (or)" in content

    # 2. Verify existence of the Recorded Voice Consent Script in all 4 languages
    assert "Recorded Voice Consent Script" in content
    
    # 3. Verify privacy notice template exists
    assert "PRIVACY NOTICE & PATIENT RIGHTS" in content
    assert "Right to Access" in content
    assert "Right to Correction & Erasure" in content
    assert "Grievance Redressal" in content


def test_whatsapp_templates_placeholders_match():
    content = load_file_content("ops/whatsapp_templates.md")
    
    required_templates = [
        "T_MISSED_CALL_BRIDGE",
        "T_BOOKING_CONFIRMATION",
        "T_REMINDER_24H",
        "T_REMINDER_2H",
        "T_PAYMENT_LINK",
        "T_STAFF_ALERT",
        "T_WEEKLY_SUMMARY",
        "T_CSAT_REQUEST"
    ]
    
    sections = re.split(r"##\s+\d+\.\s+T_", content)[1:]
    assert len(sections) == 8
    
    for idx, section in enumerate(sections):
        template_name = required_templates[idx]
        
        # Split section into languages
        lang_blocks = re.split(r"###\s+(English \(en\)|Hindi \(hi\)|Hinglish \(hi-Latn\)|Odia \(or\))\s*\n", section)
        
        lang_vars = {}
        for l_idx in range(1, len(lang_blocks), 2):
            lang_name = lang_blocks[l_idx]
            lang_text = lang_blocks[l_idx+1]
            
            # Find all double-curly-braces variables
            vars_found = set(map(int, re.findall(r"\{\{(\d+)\}\}", lang_text)))
            lang_vars[lang_name] = vars_found
            
        langs = list(lang_vars.keys())
        assert len(langs) == 4, f"Template {template_name} does not have exactly 4 language blocks: found {langs}"
        base_lang = langs[0]
        base_vars = lang_vars[base_lang]
        
        # Ensure sequentiality starting at 1: {1, 2, ..., N}
        if base_vars:
            max_var = max(base_vars)
            expected_set = set(range(1, max_var + 1))
            assert base_vars == expected_set, (
                f"Placeholders in template {template_name} ({base_lang}) are not sequential starting from 1: "
                f"found {base_vars}, expected {expected_set}."
            )
            
        for lang in langs[1:]:
            assert lang_vars[lang] == base_vars, (
                f"Placeholder variables mismatch in template {template_name} for language {lang}! "
                f"Expected {base_vars}, found {lang_vars[lang]}."
            )

