def wrap_text(text: str, max_width: int = 70) -> str:
    words: list[str] = text.split()
    lines: list[str] = []
    current_line: str = ""

    for word in words:
        if not current_line:
            current_line = word
        elif len(current_line) + 1 + len(word) <= max_width:
            current_line += " " + word
        else:
            lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return "\n".join(lines)

text: str = """Дан текст. Напишите программу, которая отформатирует этот текст так, чтобы в строке текста было не более 70 символов, а потом шел перенос строки. Слова при этом не должны разбиваться."""
result: str = wrap_text(text, 70)
print(result)
