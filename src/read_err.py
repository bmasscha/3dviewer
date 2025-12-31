try:
    with open("err.txt", "rb") as f:
        data = f.read()
    with open("err_dump.txt", "w", encoding="utf-8", errors="ignore") as f:
        f.write(f"Size: {len(data)}\n")
        f.write(data.decode("utf-16le", errors="ignore")) # Powershell default
except Exception as e:
    with open("err_dump.txt", "w") as f:
        f.write(f"Error: {e}")
