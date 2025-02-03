import streamlit as st
import re
import xml.etree.ElementTree as ET
import pandas as pd

VALID_LANGUAGE_CODES = {
    "ar-001", "id-ID", "ms-MY", "bn-IN", "ca-ES", "cs-CZ", "da-DK", "nl-NL", "eu-ES", "fil-PH", "fi-FI",
    "fr-FR", "fr-CA", "gl-ES", "de-DE", "el-GR", "gu-IN", "he-IL", "hi-IN", "hu-HU", "it-IT", "ja-JP",
    "kn-IN", "ko-KR", "ml-IN", "cmn-CN", "cmn-Hant", "mr-IN", "ne-NP", "nb-NO", "pl-PL", "pt-BR", "pt-PT",
    "pa-IN", "ro-RO", "ru-RU", "sr-RS", "es-ES", "es-419", "sv-SE", "ta-IN", "te-IN", "th-TH", "tr-TR",
    "uk-UA", "ur-PK", "vi-VN"
}

def extract_itt_data(file_content):
    content = file_content.decode("utf-8")
    pattern = re.findall(r'<p begin="(\d{2}:\d{2}:\d{2}:\d{2})" end="(\d{2}:\d{2}:\d{2}:\d{2})">(.*?)</p>', content)
    lang_match = re.search(r'xml:lang=["\']([a-zA-Z0-9-]+)["\']', content)
    lang_code = lang_match.group(1) if lang_match else "Unknown"
    return pattern, lang_code, content

def timecode_to_frames(tc):
    h, m, s, f = map(int, tc.split(":"))
    return (h * 3600 + m * 60 + s) * 30 + f

def check_timecode_overlap(itt_data):
    prev_end = None
    for start, end, _ in itt_data:
        start_frames = timecode_to_frames(start)
        end_frames = timecode_to_frames(end)
        if prev_end is not None and start_frames < prev_end:
            return True
        prev_end = end_frames
    return False

def compare_files(english_data, translated_data):
    line_count_match = len(english_data) == len(translated_data)
    timecode_issues = []
    
    for i, (eng_start, eng_end, eng_text) in enumerate(english_data):
        if i >= len(translated_data):
            break
        spa_start, spa_end, spa_text = translated_data[i]
        if abs(timecode_to_frames(eng_start) - timecode_to_frames(spa_start)) > 3 or \
           abs(timecode_to_frames(eng_end) - timecode_to_frames(spa_end)) > 3:
            timecode_issues.append((eng_text, spa_text))
    
    extra_lines = translated_data[len(english_data):] if len(translated_data) > len(english_data) else []
    missing_lines = english_data[len(translated_data):] if len(english_data) > len(translated_data) else []
    
    return line_count_match, timecode_issues, extra_lines, missing_lines

def generate_corrected_itt(english_data):
    corrected_output = "<?xml version='1.0' encoding='utf-8'?>\n<tt>\n<body>\n"
    for eng_start, eng_end, _ in english_data:
        corrected_output += f'    <p begin="{eng_start}" end="{eng_end}">TRANSLATED TEXT HERE</p>\n'
    corrected_output += "</body>\n</tt>"
    return corrected_output

st.title("ITT Localization Validator")

english_file = st.file_uploader("Upload English GUIDE .itt file", type=["itt"], key="english")
translated_files = st.file_uploader("Upload Translated .itt files", type=["itt"], accept_multiple_files=True, key="translated")

if english_file and translated_files:
    english_data, english_lang, english_content = extract_itt_data(english_file.read())
    summary = []
    translated_contents = {}

    for translated_file in translated_files:
        file_content = translated_file.read()  # Read the file once and store content
        translated_data, translated_lang, translated_content = extract_itt_data(file_content)
        translated_contents[translated_file.name] = translated_content  # Store content for later display

        line_count_match, timecode_issues, extra_lines, missing_lines = compare_files(english_data, translated_data)
        overlap_issue = check_timecode_overlap(translated_data)
        errors_found = not line_count_match or timecode_issues or overlap_issue
        result_emoji = "✅" if not errors_found else "❌"
        summary.append([translated_file.name, translated_lang, result_emoji])
    
    st.subheader("Summary Table")
    df_summary = pd.DataFrame(summary, columns=["File Name", "Language Code", "Result"])
    st.table(df_summary)
    
    for translated_file in translated_files:
        translated_content = translated_contents[translated_file.name]  # Retrieve stored content
        translated_data, translated_lang, _ = extract_itt_data(translated_content.encode('utf-8'))

        with st.expander(f"Results for {translated_file.name}"):
            if translated_lang == "en":
                st.error(f"🚨 Detected language code: {translated_lang} (Invalid - should not be English)")
            else:
                st.success(f"✅ Detected language code: {translated_lang}")
            
            line_count_match, timecode_issues, extra_lines, missing_lines = compare_files(english_data, translated_data)
            overlap_issue = check_timecode_overlap(translated_data)
            
            if line_count_match:
                st.success("✅ Line count matches!")
            else:
                st.warning("⚠️ Line count does NOT match!")
                if extra_lines:
                    st.error(f"🚨 Extra lines detected: {len(extra_lines)}")
                if missing_lines:
                    st.error(f"🚨 Missing lines detected: {len(missing_lines)}")
            
            if timecode_issues:
                st.error("⏳ Timecode mismatches found (over 3 frames):")
                for eng_text, spa_text in timecode_issues:
                    st.text(f"English: {eng_text}\nTranslated: {spa_text}")
            
            if overlap_issue:
                st.error("🚨 Overlapping timecodes detected!")
            
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("English File")
                st.code(english_content, language='xml')
            with col2:
                st.subheader(f"Translated File: {translated_file.name}")
                st.code(translated_content, language='xml')
            
            if errors_found:
                corrected_itt = generate_corrected_itt(english_data)
                st.download_button(f"Download Corrected ITT for {translated_file.name}", corrected_itt, f"corrected_{translated_file.name}", "text/xml")
