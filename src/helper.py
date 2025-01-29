import re
import string
import streamlit as st


def display_code_plots(text):
    # Handle multiple code block formats
    patterns = [
        r'```python\s*(.*?)```',  # Standard markdown
        r'```\s*(.*?)```',        # No language specified
        r'%%python\n(.*?)\n'      # Jupyter-style
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        if matches:
            return matches[0].strip()
    
    # Fallback: Try to find indented code blocks
    code_lines = []
    in_code = False
    for line in text.split('\n'):
        if line.strip().startswith(('import ', 'def ', 'class ', 'fig =')):
            in_code = True
        if in_code:
            code_lines.append(line)
    
    return '\n'.join(code_lines) if code_lines else None


def display_text_with_images(text):
    """
    Display text with associated images.
    Args:
        text (str): The text to be displayed.
    Returns:
        None
    """

    # Modify the regex to remove potential '[voir image]' and parentheses around the URL
    image_urls = re.findall(r"https?://[^\s]+image[^\s]*.jpg", text, flags=re.IGNORECASE)

    # Replace the markdown image syntax with just the URL for splitting
    text_for_splitting = re.sub(r"-? +?!?\[lien vers l'image\]\s*\(?(https?://[^\s]+image[^\s]*.jpg)\)?",
        r"\1 \n ", text, flags=re.IGNORECASE)

    # Split text at image URLs
    parts = re.split(r"https?://[^\s]+image[^\s]*.jpg", text_for_splitting)

    for i, part in enumerate(parts):
        # If there is punctuation character, parts[i] must have at least one alpha character.
        if any(char in string.punctuation for char in part) and not any(
            char.isalpha() for char in part
        ):
            continue
        # Display the text part
        st.markdown(part.replace("\n", "\n\n"))

        # Display the image if it exists
        if i < len(image_urls):
            st.image(image_urls[i])
