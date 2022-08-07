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

        self.frame = tk.Frame(self, width=800, height=600)
        self.frame.pack()
        self.frame.place(anchor="center", relx=0.5, rely=0.4)

        self.img = tk.Label(self.frame)
        self.img.pack()

        self.label = tk.Label(self.frame, text="hello :)")
        self.label.pack()

        # word, file path
        self.files = [
            (path.stem, path)
            for path in Path(__file__).resolve().parent.parent.glob("words/*.*")
        ]

        word, path = random.choice(self.files)

        img = ImageTk.PhotoImage(Image.open(path))
        self.img.configure(image=img)
        self.img.image = img
        self.label.configure(text=word)


if __name__ == "__main__":
    Flashcard().mainloop()
