import random
from pathlib import Path
import time

import tkinter as tk
from PIL import ImageTk, Image



class Flashcard(tk.Tk):
    def __init__(self):
        tk.Tk.__init__(self)

        self.geometry("800x600")
        self.title("toki pona")
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Return>", self.mark_entry)

        self.frame = tk.Frame(self, width=800, height=600)
        self.frame.pack()
        self.frame.place(anchor="center", relx=0.5, rely=0.4)

        self.img = tk.Label(self.frame)
        self.img.pack()

        self.label = tk.Label(self.frame)
        self.label.pack()

        self.word_entry = tk.Entry(self.frame)
        self.word_entry.pack()

        self.spoiler = tk.Button(
            self.frame,
            text="please tell me!",
            command=self.spoiler_please,
        )
        self.spoiler.pack()

        self.spoiler_label = tk.Label(self.frame)
        self.spoiler_label.pack()

        # word, file path
        self.files = [
            (path.stem, path)
            for path in Path(__file__).resolve().parent.parent.glob("words/*.*")
        ]

        self.random_word()

    def random_word(self):
        self.word_entry.delete(0, tk.END)
        self.spoiler_label.configure(text="")

        self.current_word, self.current_path = random.choice(self.files)

        img = ImageTk.PhotoImage(Image.open(self.current_path))
        self.img.configure(image=img)
        self.img.image = img
        self.label.configure(text="")

    def mark_entry(self, event):
        user_entry = self.word_entry.get()
        if user_entry == self.current_word:
            self.random_word()
            self.label.configure(text=f"yes, it was {user_entry}")
        else:
            self.label.configure(text=f"no, it's not {user_entry}")

    def spoiler_please(self):
        self.spoiler_label.configure(text=f"pst, it's {self.current_word}")


if __name__ == "__main__":
    Flashcard().mainloop()
