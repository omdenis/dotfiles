import tkinter as tk
import urllib.parse
import webbrowser


def get_clipboard_text() -> str:
    root = tk.Tk()
    root.withdraw()  
    try:
        text = root.clipboard_get()
    except tk.TclError:
        text = ""
    finally:
        root.destroy()
    return text


def main():
    text = get_clipboard_text().strip()
    if not text:
        print("Буфер пуст или в нём нет текста.")
        return

    text_for_translate = text + "\n\n"

    encoded_text = urllib.parse.quote(text_for_translate)

    url = f"https://translate.google.ru/?sl=en&tl=ru&text={encoded_text}&op=translate"
    webbrowser.open(url)
    print(f"Открываю перевод для: {text!r}")


if __name__ == "__main__":
    main()

