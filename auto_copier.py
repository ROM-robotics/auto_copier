import os
from pathlib import Path
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


class AutoPasswordZipCopierApp:

  def __init__(self, root):
    self.root = root
    self.root.title("Auto Reverse-Name Password Zip & Copy App")
    self.root.geometry("500x400")
    self.root.resizable(False, False)

    self.desktop_path = str(Path.home() / "Desktop")

    # --- Widgets Layout ---
    # 1. Source Folder
    tk.Label(
        root, text="Source Folder (Desktop):", font=("Arial", 10, "bold")
    ).pack(anchor="w", padx=20, pady=(15, 5))
    src_frame = tk.Frame(root)
    src_frame.pack(fill="x", padx=20)

    self.src_entry = tk.Entry(src_frame, width=40, font=("Arial", 10))
    self.src_entry.pack(side="left", padx=(0, 10))
    self.src_entry.insert(0, self.desktop_path)
    tk.Button(
        src_frame,
        text="Browse",
        command=self.select_source,
        font=("Arial", 9),
    ).pack(side="left")

    # 2. Destination Folder
    tk.Label(
        root, text="Destination Folder:", font=("Arial", 10, "bold")
    ).pack(anchor="w", padx=20, pady=(10, 5))
    dst_frame = tk.Frame(root)
    dst_frame.pack(fill="x", padx=20)

    self.dst_entry = tk.Entry(dst_frame, width=40, font=("Arial", 10))
    self.dst_entry.pack(side="left", padx=(0, 10))
    tk.Button(
        dst_frame,
        text="Browse",
        command=self.select_destination,
        font=("Arial", 9),
    ).pack(side="left")

    # 3. Version / String input
    tk.Label(
        root, text="Version / String (e.g., v1.0.0):", font=("Arial", 10, "bold")
    ).pack(anchor="w", padx=20, pady=(10, 5))
    self.ver_entry = tk.Entry(root, width=25, font=("Arial", 10))
    self.ver_entry.pack(anchor="w", padx=20)
    self.ver_entry.insert(0, "v1.0.0")

    # 4. Action Button & Progress Bar
    self.action_btn = tk.Button(
        root,
        text="Zip & Copy (Auto Password)",
        command=self.start_process_thread,
        bg="#0d47a1",
        fg="white",
        font=("Arial", 10, "bold"),
        width=25,
    )
    self.action_btn.pack(pady=20)

    self.progress = ttk.Progressbar(
        root, orient="horizontal", length=440, mode="indeterminate"
    )
    self.progress.pack(pady=5)

    self.status_label = tk.Label(
        root, text="Ready", font=("Arial", 9, "italic"), fg="gray"
    )
    self.status_label.pack(anchor="w", padx=20, pady=(0, 10))

  def select_source(self):
    dir_path = filedialog.askdirectory(initialdir=self.desktop_path)
    if dir_path:
      self.src_entry.delete(0, tk.END)
      self.src_entry.insert(0, dir_path)

  def select_destination(self):
    dir_path = filedialog.askdirectory(initialdir=self.desktop_path)
    if dir_path:
      self.dst_entry.delete(0, tk.END)
      self.dst_entry.insert(0, dir_path)

  def start_process_thread(self):
    if not self.check_zip_installed():
      messagebox.showerror(
          "Error",
          "Ubuntu တွင် zip tool မရှိပါ။ Terminal တွင် 'sudo apt install zip'"
          " ဖြင့် ထည့်သွင်းပါ။",
      )
      return

    self.action_btn.config(state="disabled")
    self.progress.start(10)
    self.status_label.config(
        text="Creating zip with auto-generated password...", fg="blue"
    )

    threading.Thread(target=self.process_zip_and_copy, daemon=True).start()

  def check_zip_installed(self):
    return shutil.which("zip") is not None

  def process_zip_and_copy(self):
    try:
      src = self.src_entry.get().strip()
      dst = self.dst_entry.get().strip()
      version = self.ver_entry.get().strip()

      if not src or not dst:
        raise ValueError("Source နှင့် Destination များကို ဖြည့်စွက်ပါ။")

      if not os.path.exists(src):
        raise FileNotFoundError("ရွေးချယ်ထားသော Source Folder မရှိပါ။")

      os.makedirs(dst, exist_ok=True)

      folder_name = os.path.basename(os.path.normpath(src))
      zip_file_name = f"{folder_name}_{version}.zip"
      zip_full_path = os.path.join(dst, zip_file_name)

      # Automatically generate password by reversing the zip file name string
      password = zip_file_name[::-1]

      if os.path.exists(zip_full_path):
        os.remove(zip_full_path)

      parent_dir = os.path.dirname(src)
      base_folder = os.path.basename(src)

      cmd = ["zip", "-e", "-r", zip_full_path, base_folder]

      process = subprocess.Popen(
          cmd,
          cwd=parent_dir,
          stdin=subprocess.PIPE,
          stdout=subprocess.PIPE,
          stderr=subprocess.PIPE,
      )

      pwd_input = f"{password}\n{password}\n".encode("utf-8")
      stdout, stderr = process.communicate(input=pwd_input)

      if process.returncode != 0:
        err_msg = stderr.decode("utf-8", errors="ignore")
        raise RuntimeError(f"Zip failed: {err_msg}")

      self.root.after(
          0,
          lambda: messagebox.showinfo(
              "Success",
              f"ဇစ်ဖိုင်နာမည် ပြောင်းပြန် (Password) ဖြင့် လုံခြုံစွာ ဇစ်ထုတ်ပြီး Copy ကူးပြီးပါပြီ:\n"
              f"{zip_full_path}\n\n"
              f"အသုံးပြုခဲ့သော Password: {password}",
          ),
      )

    except Exception as e:
      self.root.after(
          0,
          lambda: messagebox.showerror(
              "Error", f"အမှားအယွင်း ဖြစ်ပေါ်သည်:\n{str(e)}"
          ),
      )

    finally:
      self.root.after(0, self.reset_ui)

  def reset_ui(self):
    self.progress.stop()
    self.action_btn.config(state="normal")
    self.status_label.config(text="Ready", fg="gray")


if __name__ == "__main__":
  root = tk.Tk()
  app = AutoPasswordZipCopierApp(root)
  root.mainloop()