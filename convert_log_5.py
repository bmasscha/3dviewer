
try:
    with open("c:/code/antigravity/3dviewer/tests/test_output_5.txt", "r", encoding="utf-16") as f:
        content = f.read()
except:
    try:
        with open("c:/code/antigravity/3dviewer/tests/test_output_5.txt", "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        content = f"Failed to read: {e}"

with open("c:/code/antigravity/3dviewer/tests/test_output_utf8.txt", "w", encoding="utf-8") as f:
    f.write(content)
