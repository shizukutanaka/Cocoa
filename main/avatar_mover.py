import tkinter as tk
from tkinter import ttk
import math

class AvatarMoverApp:
    def __init__(self, root):
        self.root = root
        self.root.title("アバター移動モード選択")
        self.mode = tk.StringVar(value="2D")
        self.create_widgets()
        self.avatar_pos = [250, 250, 0]  # x, y, z
        self.canvas_avatar = None
        self.update_canvas()

    def create_widgets(self):
        mode_frame = ttk.LabelFrame(self.root, text="移動モード")
        mode_frame.pack(padx=10, pady=5, fill='x')
        ttk.Radiobutton(mode_frame, text="平面上 (2D)", variable=self.mode, value="2D", command=self.update_canvas).pack(side='left', padx=5)
        ttk.Radiobutton(mode_frame, text="3D空間 (3D)", variable=self.mode, value="3D", command=self.update_canvas).pack(side='left', padx=5)

        self.canvas = tk.Canvas(self.root, width=500, height=500, bg="#f0f0f0")
        self.canvas.pack(padx=10, pady=10)

        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="←", command=lambda: self.move_avatar(-20, 0, 0)).grid(row=0, column=0)
        ttk.Button(btn_frame, text="→", command=lambda: self.move_avatar(20, 0, 0)).grid(row=0, column=2)
        ttk.Button(btn_frame, text="↑", command=lambda: self.move_avatar(0, -20, 0)).grid(row=0, column=1)
        ttk.Button(btn_frame, text="↓", command=lambda: self.move_avatar(0, 20, 0)).grid(row=0, column=1, pady=(30, 0))
        ttk.Button(btn_frame, text="上昇(Z+)", command=lambda: self.move_avatar(0, 0, 20)).grid(row=1, column=0)
        ttk.Button(btn_frame, text="下降(Z-)", command=lambda: self.move_avatar(0, 0, -20)).grid(row=1, column=2)

    def move_avatar(self, dx, dy, dz):
        if self.mode.get() == "2D":
            self.avatar_pos[0] += dx
            self.avatar_pos[1] += dy
        else:
            self.avatar_pos[0] += dx
            self.avatar_pos[1] += dy
            self.avatar_pos[2] += dz
        self.update_canvas()

    def update_canvas(self):
        self.canvas.delete("all")
        if self.mode.get() == "2D":
            x, y = self.avatar_pos[0], self.avatar_pos[1]
            self.canvas.create_oval(x-20, y-20, x+20, y+20, fill="skyblue", outline="navy", width=2)
            self.canvas.create_text(x, y, text="Avatar", font=("Arial", 12, "bold"))
            self.canvas.create_text(250, 30, text=f"2D座標: x={x}, y={y}", font=("Arial", 10))
        else:
            # 3D表現は簡易的な投影で描画
            x, y, z = self.avatar_pos
            # z軸は奥行きとしてy座標に影響（簡易投影）
            px = x
            py = y - z * 0.5
            size = 20 + z * 0.05
            self.canvas.create_oval(px-size, py-size, px+size, py+size, fill="lightgreen", outline="darkgreen", width=2)
            self.canvas.create_text(px, py, text="Avatar", font=("Arial", 12, "bold"))
            self.canvas.create_text(250, 30, text=f"3D座標: x={x}, y={y}, z={z}", font=("Arial", 10))

if __name__ == "__main__":
    root = tk.Tk()
    app = AvatarMoverApp(root)
    root.mainloop()
