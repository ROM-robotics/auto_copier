import os
from datetime import datetime
from pathlib import Path
import re
import shutil
import unicodedata
import stat
import subprocess
import sys
import tempfile
import threading
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox


def resource_path(relative_path):
  if getattr(sys, "frozen", False):
    base = Path(sys._MEIPASS)
  else:
    base = Path(__file__).resolve().parent
  return base / relative_path


def hold_clipboard_and_exit():
  text = sys.stdin.read()
  holder = tk.Tk()
  holder.withdraw()
  holder.clipboard_clear()
  holder.clipboard_append(text)
  holder.update()
  holder.after(5 * 60 * 1000, holder.destroy)
  holder.mainloop()
  raise SystemExit(0)


def overall_percent(source_done, source_total, archive_size, copied, copy_done, zip_done=False):
  """Share of source bytes zipped plus archive bytes copied, from 0 to 100."""
  if copy_done:
    return 100.0
  source_done = max(0, source_done)
  source_total = max(0, source_total)
  archive_size = max(0, archive_size)
  copied = max(0, copied)
  if copied or zip_done:
    done = source_total + copied
    total = source_total + max(archive_size, copied)
  else:
    done = min(source_done, source_total) if source_total else source_done
    # The archive is still buffered, so its size can lag the bytes zip has
    # already read. Count at least those bytes until zip has finished.
    total = source_total + max(archive_size, done)
  if total <= 0:
    return 0.0
  return min(99.0, done / total * 100.0)


_TOOL_PERCENT = re.compile(rb"(\d{1,3})%")


def _latest_tool_percent(buf):
  matches = _TOOL_PERCENT.findall(buf)
  if not matches:
    return None
  value = int(matches[-1])
  if value > 100:
    return None
  return value


class PercentBar(tk.Canvas):

  def __init__(self, parent, width=440, height=26):
    super().__init__(
        parent,
        width=width,
        height=height,
        highlightthickness=1,
        highlightbackground="#90a4ae",
        bd=0,
    )
    self._width = width
    self._height = height
    self.value = 0
    self.set(0)

  def set(self, percent):
    self.value = max(0, min(100, int(percent)))
    self.delete("all")
    fill_w = int(self._width * self.value / 100)
    self.create_rectangle(0, 0, self._width, self._height, fill="#eceff1", outline="")
    if fill_w:
      self.create_rectangle(0, 0, fill_w, self._height, fill="#0d47a1", outline="")
    text = f"{self.value}%"
    cx = self._width / 2
    cy = self._height / 2
    font = ("Arial", 10, "bold")
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)):
      self.create_text(cx + dx, cy + dy, text=text, fill="white", font=font)
    self.create_text(cx, cy, text=text, fill="#0d47a1", font=font)


def apply_window_icon(root):
  icon_path = resource_path("assets/icon.png")
  if not icon_path.is_file():
    return
  try:
    icon = tk.PhotoImage(file=str(icon_path))
  except tk.TclError:
    return
  root.iconphoto(True, icon)
  root._icon_image = icon


class LargeCheck(tk.Frame):
  def __init__(self, parent, text, variable, size=28):
    super().__init__(parent)
    self.variable = variable
    self.size = size
    self.box = tk.Canvas(
        self,
        width=size,
        height=size,
        highlightthickness=0,
        cursor="hand2",
    )
    self.box.pack(side="left", padx=(0, 10))
    self.label = tk.Label(
        self,
        text=text,
        font=("Arial", 14),
        cursor="hand2",
        anchor="w",
    )
    self.label.pack(side="left")
    for widget in (self, self.box, self.label):
      widget.bind("<Button-1>", self._toggle)
    self.variable.trace_add("write", lambda *_: self._draw())
    self._draw()

  def _toggle(self, _event=None):
    self.variable.set(not self.variable.get())

  def _draw(self):
    size = self.size
    self.box.delete("all")
    self.box.create_rectangle(
        2, 2, size - 2, size - 2, outline="#0d47a1", width=2, fill="white"
    )
    if self.variable.get():
      self.box.create_line(
          7,
          size // 2,
          size // 2 - 1,
          size - 8,
          size - 7,
          7,
          fill="#0d47a1",
          width=3,
          capstyle="round",
          joinstyle="round",
      )


class AutoPasswordZipCopierApp:

  def __init__(self, root):
    self.root = root
    self.root.title("Auto Copier")
    self.root.resizable(False, False)

    self.desktop_path = str(Path.home() / "Desktop")
    self._closing_after_success = False
    self._job_id = 0
    self.browse_icon = self._load_browse_icon()
    self._install_large_directory_dialog()

    header = tk.Frame(root)
    header.pack(fill="x", padx=12, pady=(8, 0))
    tk.Button(
        header,
        text="?",
        command=self.show_help,
        font=("Arial", 11, "bold"),
        width=2,
        cursor="hand2",
    ).pack(side="right")

    # --- Widgets Layout ---
    # 1. Source Folder
    tk.Label(
        root, text="Source Folder:", font=("Arial", 10, "bold")
    ).pack(anchor="w", padx=20, pady=(8, 5))
    src_frame = tk.Frame(root)
    src_frame.pack(fill="x", padx=20)

    self._explorer_button(src_frame, self.select_source).pack(side="right")
    self.src_entry = tk.Entry(src_frame, font=("Arial", 10))
    self.src_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

    # 2. Destination Folder
    tk.Label(
        root, text="Destination Folder:", font=("Arial", 10, "bold")
    ).pack(anchor="w", padx=20, pady=(10, 5))
    dst_frame = tk.Frame(root)
    dst_frame.pack(fill="x", padx=20)

    self._explorer_button(dst_frame, self.select_destination).pack(side="right")
    self.dst_entry = tk.Entry(dst_frame, font=("Arial", 10))
    self.dst_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

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
        text="7z & Copy (Auto Password)",
        command=self.start_process_thread,
        bg="#0d47a1",
        fg="white",
        font=("Arial", 10, "bold"),
        width=25,
    )
    self.action_btn.pack(pady=(20, 8))

    self.use_default_password = tk.BooleanVar(value=True)
    LargeCheck(
        root,
        text="Default password",
        variable=self.use_default_password,
    ).pack(anchor="w", padx=20, pady=(0, 4))

    self.percent_bar = PercentBar(root)
    self.percent_bar.pack(pady=(5, 18))
    self.root.update_idletasks()
    self.root.geometry(f"560x{self.root.winfo_reqheight()}")

  def _load_browse_icon(self):
    icon_path = resource_path("assets/browse.png")
    if not icon_path.is_file():
      return None
    try:
      icon = tk.PhotoImage(file=str(icon_path))
    except tk.TclError:
      return None
    if icon.width() > 32:
      icon = icon.subsample(max(1, icon.width() // 32), max(1, icon.height() // 32))
    return icon

  def _explorer_button(self, parent, command):
    if self.browse_icon is None:
      return tk.Button(parent, text="...", command=command, font=("Arial", 9))
    return tk.Button(
        parent,
        image=self.browse_icon,
        command=command,
        relief="flat",
        bd=0,
        highlightthickness=0,
        cursor="hand2",
        padx=1,
        pady=1,
        activebackground="#e3f2fd",
    )

  def _install_large_directory_dialog(self):
    # Tk's directory dialog opens at its requested size. Double that size
    # when the dialog is shown, without shrinking it if the path is long.
    def enlarge(event):
      # The dialog is created by Tk's Tcl code, so the event widget is a path.
      path = event.widget if isinstance(event.widget, str) else str(event.widget)
      if self.root.tk.call("winfo", "class", path) != "TkChooseDir":
        return
      req_w = int(self.root.tk.call("winfo", "reqwidth", path))
      req_h = int(self.root.tk.call("winfo", "reqheight", path))
      screen_w = int(self.root.tk.call("winfo", "screenwidth", path))
      screen_h = int(self.root.tk.call("winfo", "screenheight", path))
      width = min(req_w * 2, screen_w - 80)
      height = min(req_h * 2, screen_h - 80)
      x = max(0, (screen_w - width) // 2)
      y = max(0, (screen_h - height) // 2)
      self.root.tk.call("wm", "geometry", path, f"{width}x{height}+{x}+{y}")

    self.root.bind_class("TkChooseDir", "<Map>", enlarge)

  def _choose_folder(self, title, entry):
    initial = entry.get().strip() or self.desktop_path
    if not os.path.isdir(initial):
      initial = self.desktop_path
    dir_path = filedialog.askdirectory(
        parent=self.root,
        title=title,
        initialdir=initial,
        mustexist=True,
    )
    if dir_path:
      entry.delete(0, tk.END)
      entry.insert(0, dir_path)

  def select_source(self):
    self._choose_folder("Select Source Folder", self.src_entry)

  def select_destination(self):
    self._choose_folder("Select Destination Folder", self.dst_entry)

  def _normalized_dir(self, value):
    return os.path.abspath(os.path.normpath(value.strip()))

  def _same_directory(self, src, dst):
    if src == dst:
      return True
    try:
      return os.path.isdir(src) and os.path.isdir(dst) and os.path.samefile(src, dst)
    except OSError:
      return False

  def _focus_destination(self):
    self.dst_entry.focus_set()
    self.dst_entry.selection_range(0, tk.END)
    self.dst_entry.icursor(tk.END)

  def start_process_thread(self):
    if not self.check_7z_installed():
      messagebox.showerror(
          "Error",
          "Ubuntu တွင် 7z tool မရှိပါ။ Terminal တွင် 'sudo apt install p7zip-full'"
          " ဖြင့် ထည့်သွင်းပါ။",
      )
      return

    src_text = self.src_entry.get().strip()
    dst_text = self.dst_entry.get().strip()
    if src_text and dst_text and self._same_directory(
        self._normalized_dir(src_text), self._normalized_dir(dst_text)
    ):
      messagebox.showerror(
          "Error",
          "Source နှင့် Destination path တူနေသည်။ Destination ကို ပြောင်းပါ။",
      )
      self._focus_destination()
      return

    custom_password = None
    if not self.use_default_password.get():
      custom_password = self._ask_custom_password()
      if custom_password is None:
        return

    self.action_btn.config(state="disabled")
    self._job_id += 1
    job_id = self._job_id
    self.percent_bar.set(0)

    threading.Thread(
        target=self.process_zip_and_copy,
        args=(job_id, custom_password),
        daemon=True,
    ).start()

  def check_7z_installed(self):
    return shutil.which("7z") is not None

  def _is_git_work_tree(self, src):
    if os.path.exists(os.path.join(src, ".git")) and shutil.which("git") is None:
      raise RuntimeError(
          "Source သည် git directory ဖြစ်သော်လည်း git command မရှိပါ။ "
          "'sudo apt install git' ဖြင့် ထည့်သွင်းပါ။"
      )
    if shutil.which("git") is None:
      return False
    proc = subprocess.run(
        ["git", "-C", src, "rev-parse", "--is-inside-work-tree"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return proc.returncode == 0 and proc.stdout.strip() == b"true"

  def _can_archive(self, full):
    if not os.path.lexists(full):
      return False
    # 7z still stats the target of a symlink, even with -snl.
    if os.path.islink(full) and not os.path.exists(full):
      return False
    return True

  def _broken_archive_paths(self, src):
    skipped = []
    base = os.path.basename(src)
    for dirpath, dirnames, filenames in os.walk(src, followlinks=False):
      rel_dir = os.path.relpath(dirpath, src)
      for name in list(dirnames):
        full = os.path.join(dirpath, name)
        if self._can_archive(full):
          continue
        rel = name if rel_dir == "." else f"{rel_dir}/{name}"
        skipped.append(f"{base}/{rel.replace(os.sep, '/')}")
        dirnames.remove(name)
      for name in filenames:
        full = os.path.join(dirpath, name)
        if self._can_archive(full):
          continue
        rel = name if rel_dir == "." else f"{rel_dir}/{name}"
        skipped.append(f"{base}/{rel.replace(os.sep, '/')}")
    return skipped

  def _root_gitignore_matches(self, src, paths):
    ignore_file = os.path.join(src, ".gitignore")
    if not os.path.isfile(ignore_file) or not paths:
      return set()
    git = shutil.which("git")
    if git is None:
      raise RuntimeError(
          "Source တွင် .gitignore ပါသော်လည်း git command မရှိပါ။ "
          "'sudo apt install git' ဖြင့် ထည့်သွင်းပါ။"
      )

    git_env = os.environ.copy()
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX"):
      git_env.pop(key, None)
    git_env["GIT_CONFIG_NOSYSTEM"] = "1"
    git_env["GIT_CONFIG_GLOBAL"] = os.devnull

    with tempfile.TemporaryDirectory(prefix="auto_copier_gitignore_") as temp_dir:
      subprocess.run(
          [git, "-C", temp_dir, "init", "--quiet"],
          stdout=subprocess.PIPE,
          stderr=subprocess.PIPE,
          check=True,
          env=git_env,
      )
      shutil.copyfile(ignore_file, os.path.join(temp_dir, ".gitignore"))
      input_paths = b"".join(os.fsencode(path) + b"\0" for path in paths)
      proc = subprocess.run(
          [
              git,
              "-C",
              temp_dir,
              "-c",
              "core.excludesFile=/dev/null",
              "check-ignore",
              "--no-index",
              "-z",
              "--stdin",
          ],
          input=input_paths,
          stdout=subprocess.PIPE,
          stderr=subprocess.PIPE,
          check=False,
          env=git_env,
      )
      if proc.returncode not in (0, 1):
        detail = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(detail or "git check-ignore failed")
      return {
          raw.decode("utf-8", "surrogateescape").rstrip("/")
          for raw in proc.stdout.split(b"\0")
          if raw
      }

  def _git_paths_to_zip(self, src):
    files = []
    commands = (
        ["git", "-C", src, "ls-files", "-z"],
        ["git", "-C", src, "ls-files", "-z", "--others"],
    )
    for cmd in commands:
      proc = subprocess.run(
          cmd,
          stdout=subprocess.PIPE,
          stderr=subprocess.PIPE,
          check=False,
      )
      if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(detail or "git ls-files failed")
      for raw in proc.stdout.split(b"\0"):
        if not raw:
          continue
        rel = raw.decode("utf-8", "surrogateescape")
        if rel.startswith("/") or rel.startswith("../") or "/../" in rel:
          continue
        if "\n" in rel:
          raise RuntimeError(f"Newline ပါသော path ကို archive မလုပ်နိုင်ပါ: {rel!r}")
        files.append(rel)
    unique = []
    seen = set()
    skipped = []
    for rel in files:
      if rel in seen:
        continue
      seen.add(rel)
      if not self._can_archive(os.path.join(src, rel)):
        skipped.append(rel)
        continue
      unique.append(rel)
    ignored = self._root_gitignore_matches(src, unique)
    included = []
    for rel in unique:
      if rel in ignored:
        skipped.append(rel)
      else:
        included.append(rel)
    return included, skipped

  def _gitignore_paths_in_tree(self, src):
    paths = []
    for dirpath, dirnames, filenames in os.walk(src, followlinks=False):
      rel_dir = os.path.relpath(dirpath, src)
      for name in dirnames:
        rel = name if rel_dir == "." else f"{rel_dir}/{name}"
        paths.append(rel.replace(os.sep, "/") + "/")
      for name in filenames:
        rel = name if rel_dir == "." else f"{rel_dir}/{name}"
        paths.append(rel.replace(os.sep, "/"))
    base = os.path.basename(src)
    return {
        f"{base}/{rel}"
        for rel in self._root_gitignore_matches(src, paths)
    }

  def _report_progress(self, percent, job_id):
    shown = max(0, min(100, int(round(percent))))

    def apply(value=shown, job_id=job_id):
      if job_id != self._job_id or value < self.percent_bar.value:
        return
      self.percent_bar.set(value)

    self.root.after(0, apply)

  def _zip_entries(self, src, include_paths):
    parent = os.path.dirname(src)
    base = os.path.basename(src)
    entries = {}
    if include_paths is None:
      entries[base + "/"] = 0
      for dirpath, _dirnames, filenames in os.walk(src, followlinks=False):
        rel_dir = os.path.relpath(dirpath, parent).replace(os.sep, "/")
        if rel_dir != base:
          entries[rel_dir + "/"] = 0
        for name in filenames:
          full = os.path.join(dirpath, name)
          rel = f"{rel_dir}/{name}"
          try:
            st = os.lstat(full)
          except OSError:
            continue
          if stat.S_ISREG(st.st_mode) or stat.S_ISLNK(st.st_mode):
            entries[rel] = st.st_size
      return entries
    for rel in include_paths:
      rel = rel.replace(os.sep, "/")
      full = os.path.join(src, rel)
      zip_rel = f"{base}/{rel}"
      try:
        st = os.lstat(full)
        size = st.st_size if stat.S_ISREG(st.st_mode) or stat.S_ISLNK(st.st_mode) else 0
      except OSError:
        size = 0
      entries[zip_rel] = size
    return entries

  def _run_archive(self, cmd, cwd, temp_archive, source_total, job_id, password):
    # -p with no value makes 7z read the password from stdin. Putting it in
    # argv would show the password in the process list.
    process = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )
    line = password.encode("utf-8") + b"\n"
    process.stdin.write(line + line)
    process.stdin.close()
    stderr_parts = []

    def drain_stderr():
      stderr_parts.append(process.stderr.read())

    stderr_thread = threading.Thread(target=drain_stderr, daemon=True)
    stderr_thread.start()
    last_reported = -1
    tool_percent = 0
    pending = b""
    while True:
      chunk = process.stdout.read(256)
      if not chunk:
        break
      pending = (pending + chunk)[-128:]
      parsed = _latest_tool_percent(pending)
      if parsed is not None:
        tool_percent = parsed
      archive_size = os.path.getsize(temp_archive) if os.path.isfile(temp_archive) else 0
      percent = overall_percent(
          source_total * tool_percent / 100.0, source_total, archive_size, 0, False
      )
      shown = int(round(percent))
      if shown != last_reported:
        last_reported = shown
        self._report_progress(percent, job_id)
    process.wait()
    stderr_thread.join()
    archive_size = os.path.getsize(temp_archive) if os.path.isfile(temp_archive) else 0
    if process.returncode == 0:
      self._report_progress(
          overall_percent(source_total, source_total, archive_size, 0, False, True),
          job_id,
      )
    err = b"".join(stderr_parts).decode("utf-8", errors="ignore").strip()
    if password:
      err = err.replace(password, "********")
    return process.returncode, err, source_total, archive_size

  def _headers_require_password(self, archive_path):
    probe = subprocess.run(
        ["7z", "l", "-y", "-p", "-bso1", "-bse1", archive_path],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if probe.returncode == 0:
      return False
    listing = probe.stdout.decode("utf-8", errors="replace")
    return "Enter password" in listing or "Errors:" in listing or "ERROR" in listing

  def _copy_with_progress(self, src, dst, source_total, job_id):
    archive_size = os.path.getsize(src)
    copied = 0
    with open(src, "rb") as source, open(dst, "wb") as target:
      while True:
        chunk = source.read(256 * 1024)
        if not chunk:
          break
        target.write(chunk)
        copied += len(chunk)
        self._report_progress(
            overall_percent(source_total, source_total, archive_size, copied, False),
            job_id,
        )
    try:
      shutil.copystat(src, dst)
    except OSError:
      pass
    self._report_progress(100, job_id)

  def show_help(self):
    if not self._confirm_help_phrase():
      return
    self._show_help_dialog()

  def _confirm_help_phrase(self):
    dialog = tk.Toplevel(self.root)
    dialog.title("?")
    dialog.resizable(False, False)
    dialog.transient(self.root)
    dialog.grab_set()
    apply_window_icon(dialog)
    accepted = {"ok": False}

    tk.Label(
        dialog,
        text="ချစ်လား?",
        font=("Arial", 14, "bold"),
    ).pack(anchor="w", padx=20, pady=(16, 8))
    entry = tk.Entry(dialog, font=("Arial", 12), width=28)
    entry.pack(fill="x", padx=20)
    error = tk.Label(dialog, text="", fg="#b71c1c", font=("Arial", 9))
    error.pack(anchor="w", padx=20, pady=(6, 0))

    def accept():
      answer = unicodedata.normalize("NFC", entry.get().strip())
      expected = {
          unicodedata.normalize("NFC", "\u1001\u103b\u1005\u103a\u1010\u1031\u102c"),
          unicodedata.normalize("NFC", "\u1001\u103b\u1005\u103a\u1010\u101a\u103a"),
      }
      if answer not in expected:
        error.config(text="မမှန်ပါ။")
        entry.focus_set()
        entry.selection_range(0, tk.END)
        return
      accepted["ok"] = True
      dialog.destroy()

    def cancel():
      dialog.destroy()

    buttons = tk.Frame(dialog)
    buttons.pack(pady=16)
    tk.Button(
        buttons, text="OK", command=accept, width=10,
        bg="#0d47a1", fg="white", font=("Arial", 10, "bold"),
    ).pack(side="left", padx=(0, 8))
    tk.Button(
        buttons, text="Cancel", command=cancel, width=10, font=("Arial", 10),
    ).pack(side="left")
    dialog.protocol("WM_DELETE_WINDOW", cancel)
    dialog.bind("<Return>", lambda _event: accept())
    dialog.bind("<Escape>", lambda _event: cancel())
    dialog.update_idletasks()
    x = self.root.winfo_rootx() + max(0, (self.root.winfo_width() - dialog.winfo_reqwidth()) // 2)
    y = self.root.winfo_rooty() + max(0, (self.root.winfo_height() - dialog.winfo_reqheight()) // 2)
    dialog.geometry(f"+{x}+{y}")
    entry.focus_set()
    self.root.wait_window(dialog)
    return accepted["ok"]

  def _show_help_dialog(self):
    dialog = tk.Toplevel(self.root)
    dialog.title("Help")
    dialog.resizable(False, False)
    dialog.transient(self.root)
    dialog.grab_set()
    apply_window_icon(dialog)

    text = tk.Text(
        dialog,
        width=52,
        height=18,
        wrap="word",
        font=("Arial", 10),
        relief="flat",
        padx=12,
        pady=10,
    )
    text.pack(fill="both", expand=True)
    text.insert("1.0", self._help_text())
    text.configure(state="disabled")
    tk.Button(
        dialog, text="ပိတ်မည်", command=dialog.destroy, width=12, font=("Arial", 10),
    ).pack(pady=(0, 12))
    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
    dialog.update_idletasks()
    x = self.root.winfo_rootx() + max(0, (self.root.winfo_width() - dialog.winfo_reqwidth()) // 2)
    y = self.root.winfo_rooty() + max(0, (self.root.winfo_height() - dialog.winfo_reqheight()) // 2)
    dialog.geometry(f"+{x}+{y}")

  def _help_text(self):
    return (
        "App အလုပ်လုပ်ပုံ\n"
        "1. Source Folder နှင့် Destination Folder ကို ရွေးပါ။\n"
        "2. Version / String ထည့်ပါ။ ဥပမာ v1.0.0။\n"
        "3. 7z & Copy ကို နှိပ်ပါ။\n"
        "4. Source folder ထဲရှိ .gitignore တစ်ခုတည်းတွင် ပါသော file နှင့် directory များကို မထည့်ပါ။\n"
        "5. ပျက်နေသော shortcut ကို ချန်ခဲ့ပါသည်။\n"
        "6. ဖိုင်အမည်စာရင်းပါ encrypt လုပ်ထားသော .7z ကို Destination ထဲသို့ ကူးပါသည်။ Password မထည့်ရင် Archive Manager က ဖိုင်စာရင်းကို မပြပါ။\n"
        "7. ပြီးသွားရင် password ကို ပြပါသည်။ Copy နှိပ်၍ ကူးနိုင်ပါသည်။ ၃ စက္ကန့်အကြာ app ပိတ်ပါသည်။\n"
        "\n"
        "Default password သတ်မှတ်ပုံ\n"
        "Default password ကို ရွေးထားရင် password သည် archive ဖိုင်အမည်ကို အက္ခရာပြောင်းပြန်လုပ်ထားခြင်းဖြစ်သည်။\n"
        "ဖိုင်အမည် = source folder အမည် + _ + version + _ + timestamp (YYYYMMDD_HHMMSS) + .7z\n"
        "ဥပမာ folder အမည် cherry_thin၊ version v1.0.0 ဖြစ်ပြီး timestamp 20261120_151200 ဖြစ်ရင် ဖိုင်အမည်သည် cherry_thin_v1.0.0_20261120_151200.7z ဖြစ်သည်။ Default password သည် ဖိုင်အမည်ကို အက္ခရာပြောင်းပြန်လုပ်ထားခြင်းဖြစ်သည်။\n"
        "Checkbox ကို ဖြုတ်ထားရင် space မပါသော password ကို ကိုယ်တိုင်ထည့်ရပါသည်။ Cancel နှိပ်ရင် အလုပ်မစပါ။"
    )

  def _ask_custom_password(self):
    while True:
      value = self._prompt_password()
      if value is None:
        return None
      if " " in value or "\n" in value or "\r" in value:
        messagebox.showerror("Error", "Password တွင် space မပါရပါ။")
        continue
      if not value:
        messagebox.showerror("Error", "Password ထည့်ပါ။")
        continue
      return value

  def _prompt_password(self):
    dialog = tk.Toplevel(self.root)
    dialog.title("Password")
    dialog.resizable(False, False)
    dialog.transient(self.root)
    dialog.grab_set()
    apply_window_icon(dialog)
    result = {"password": None}

    tk.Label(
        dialog,
        text="Space မပါသော password ထည့်ပါ။",
        font=("Arial", 10, "bold"),
    ).pack(anchor="w", padx=20, pady=(16, 8))
    entry = tk.Entry(dialog, font=("Arial", 12), width=34)
    entry.pack(fill="x", padx=20)

    def accept():
      result["password"] = entry.get()
      dialog.destroy()

    def cancel():
      result["password"] = None
      dialog.destroy()

    buttons = tk.Frame(dialog)
    buttons.pack(pady=16)
    tk.Button(
        buttons,
        text="OK",
        command=accept,
        bg="#0d47a1",
        fg="white",
        font=("Arial", 10, "bold"),
        width=10,
    ).pack(side="left", padx=(0, 8))
    tk.Button(
        buttons,
        text="Cancel",
        command=cancel,
        font=("Arial", 10),
        width=10,
    ).pack(side="left")

    dialog.protocol("WM_DELETE_WINDOW", cancel)
    dialog.bind("<Return>", lambda _event: accept())
    dialog.bind("<Escape>", lambda _event: cancel())
    dialog.update_idletasks()
    x = self.root.winfo_rootx() + max(0, (self.root.winfo_width() - dialog.winfo_reqwidth()) // 2)
    y = self.root.winfo_rooty() + max(0, (self.root.winfo_height() - dialog.winfo_reqheight()) // 2)
    dialog.geometry(f"+{x}+{y}")
    entry.focus_set()
    self.root.wait_window(dialog)
    return result["password"]

  def process_zip_and_copy(self, job_id, custom_password=None):
    try:
      src = os.path.abspath(os.path.normpath(self.src_entry.get().strip()))
      dst = os.path.abspath(os.path.normpath(self.dst_entry.get().strip()))
      version = self.ver_entry.get().strip()

      if not self.src_entry.get().strip() or not self.dst_entry.get().strip():
        raise ValueError("Source နှင့် Destination များကို ဖြည့်စွက်ပါ။")

      if not os.path.isdir(src):
        raise FileNotFoundError("ရွေးချယ်ထားသော Source Folder မရှိပါ။")

      os.makedirs(dst, exist_ok=True)

      folder_name = os.path.basename(src)
      timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
      archive_name = f"{folder_name}_{version}_{timestamp}.7z"
      archive_path = os.path.join(dst, archive_name)

      # Checked default uses the reversed archive name. An unchecked box
      # already collected a space-free password before this thread started.
      password = archive_name[::-1] if custom_password is None else custom_password

      if os.path.exists(archive_path):
        os.remove(archive_path)

      parent_dir = os.path.dirname(src)
      base_folder = folder_name
      include_paths = None
      skipped = []
      if self._is_git_work_tree(src):
        include_paths, skipped = self._git_paths_to_zip(src)
        if not include_paths:
          raise RuntimeError(
              ".gitignore အရ ထည့်သွင်းရန် file မကျန်တော့ပါ။"
          )
      else:
        skipped = self._broken_archive_paths(src)
        skipped.extend(self._gitignore_paths_in_tree(src))

      entries = self._zip_entries(src, include_paths)
      source_total = sum(entries.values())
      with tempfile.TemporaryDirectory(prefix="auto_copier_") as temp_dir:
        temp_archive = os.path.join(temp_dir, archive_name)
        # -mhe=on encrypts filenames. zip -P left the file list readable,
        # so Archive Manager opened it without asking for a password.
        if "\n" in password or "\r" in password or "\x00" in password:
          raise RuntimeError("Password တွင် space မပါရပါ။")
        cmd = [
            "7z", "a", "-t7z", "-y", "-mhe=on", "-snl", "-ssc",
            "-bsp1", "-bso0", "-bse2", "-p", temp_archive,
        ]
        if include_paths is None:
          cmd.append(base_folder)
          if skipped:
            exclude_path = os.path.join(temp_dir, "exclude.list")
            with open(exclude_path, "w", encoding="utf-8") as handle:
              handle.write("".join(f"{rel}\n" for rel in skipped))
            cmd.append(f"-x@{exclude_path}")
        else:
          list_path = os.path.join(temp_dir, "include.list")
          with open(list_path, "w", encoding="utf-8") as handle:
            for rel in include_paths:
              # A leading ./ makes 7z drop the directory and treat
              # every .gitignore as the same filename.
              handle.write(f"{base_folder}/{rel}\n")
          cmd.append(f"@{list_path}")
        returncode, err_msg, source_total, _archive_size = self._run_archive(
            cmd, parent_dir, temp_archive, source_total, job_id, password
        )
        if returncode != 0 or not os.path.isfile(temp_archive):
          detail = err_msg or f"7z exit {returncode}"
          raise RuntimeError(f"Archive failed: {detail}")
        if not self._headers_require_password(temp_archive):
          raise RuntimeError("Archive header is not password protected.")

        self._copy_with_progress(temp_archive, archive_path, source_total, job_id)

      if not os.path.isfile(archive_path) or os.path.getsize(archive_path) == 0:
        raise RuntimeError("Archive ဖိုင်ကို destination ထဲ မကူးနိုင်ပါ။")

      self._closing_after_success = True
      self.root.after(
          0,
          lambda password=password, archive_path=archive_path, skipped=len(skipped): (
              self.show_password_dialog(password, archive_path, skipped=skipped)
          ),
      )

    except Exception as e:
      error_message = f"အမှားအယွင်း ဖြစ်ပေါ်သည်:\n{e}"
      self.root.after(
          0,
          lambda message=error_message: messagebox.showerror("Error", message),
      )

    finally:
      if not self._closing_after_success:
        self.root.after(0, self.reset_ui)

  def _copy_password(self, password):
    self.root.clipboard_clear()
    self.root.clipboard_append(password)
    self.root.update()
    env = os.environ.copy()
    env["AUTO_COPIER_CLIPBOARD_HOLD"] = "1"
    if getattr(sys, "frozen", False):
      cmd = [sys.executable]
    else:
      cmd = [sys.executable, str(Path(__file__).resolve())]
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        start_new_session=True,
    )
    proc.stdin.write(password.encode())
    proc.stdin.close()

  def show_password_dialog(self, password, zip_path, close_after_ms=3000, skipped=0):
    dialog = tk.Toplevel(self.root)
    dialog.title("Password")
    dialog.resizable(False, False)
    dialog.transient(self.root)
    dialog.grab_set()
    apply_window_icon(dialog)

    tk.Label(
        dialog,
        text="Password protected 7z ဖိုင် အဆင်သင့်ဖြစ်ပါပြီ။",
        font=("Arial", 10, "bold"),
    ).pack(anchor="w", padx=20, pady=(16, 6))
    tk.Label(
        dialog,
        text=zip_path,
        font=("Arial", 9),
        fg="gray",
        wraplength=460,
        justify="left",
    ).pack(anchor="w", padx=20)
    if skipped:
      tk.Label(
          dialog,
          text=f"ပျက်နေသော shortcut {skipped} ခုကို ချန်ခဲ့သည်။",
          font=("Arial", 9),
          fg="#b71c1c",
          wraplength=460,
          justify="left",
      ).pack(anchor="w", padx=20, pady=(8, 0))

    tk.Label(
        dialog, text="Password:", font=("Arial", 10, "bold")
    ).pack(anchor="w", padx=20, pady=(12, 4))

    row = tk.Frame(dialog)
    row.pack(fill="x", padx=20)
    entry = tk.Entry(row, font=("Arial", 12), width=34)
    entry.insert(0, password)
    entry.configure(state="readonly")
    entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

    copy_btn = tk.Button(
        row,
        text="Copy",
        font=("Arial", 9, "bold"),
        bg="#0d47a1",
        fg="white",
        activebackground="#1565c0",
        activeforeground="white",
        width=8,
        command=lambda: self._on_copy_password(password, copy_btn),
    )
    copy_btn.pack(side="right")

    seconds = max(1, close_after_ms // 1000)
    countdown = tk.Label(
        dialog,
        text=f"{seconds} စက္ကန့်အကြာတွင် ပိတ်ပါမည်။",
        font=("Arial", 9, "italic"),
        fg="gray",
    )
    countdown.pack(anchor="w", padx=20, pady=(12, 16))

    def close_all():
      if getattr(dialog, "_closing", False):
        return
      dialog._closing = True
      try:
        dialog.destroy()
      except tk.TclError:
        pass
      try:
        self.root.destroy()
      except tk.TclError:
        pass

    def tick(seconds_left):
      try:
        if not dialog.winfo_exists():
          return
      except tk.TclError:
        return
      if seconds_left <= 0:
        close_all()
        return
      countdown.config(text=f"{seconds_left} စက္ကန့်အကြာတွင် ပိတ်ပါမည်။")
      dialog.after(1000, lambda: tick(seconds_left - 1))

    dialog.protocol("WM_DELETE_WINDOW", close_all)
    dialog.update_idletasks()
    x = self.root.winfo_rootx() + max(0, (self.root.winfo_width() - dialog.winfo_width()) // 2)
    y = self.root.winfo_rooty() + max(0, (self.root.winfo_height() - dialog.winfo_height()) // 2)
    dialog.geometry(f"+{x}+{y}")
    entry.focus_set()
    tick(seconds)
    dialog.after(close_after_ms, close_all)

  def _on_copy_password(self, password, button):
    self._copy_password(password)
    button.config(text="Copied")

  def reset_ui(self):
    self._job_id += 1
    self.percent_bar.set(0)
    self.action_btn.config(state="normal")


def _log_uncaught(exc_type, exc, tb):
  if issubclass(exc_type, KeyboardInterrupt):
    sys.__excepthook__(exc_type, exc, tb)
    return
  log_path = Path.home() / ".auto_copier_error.log"
  with log_path.open("a", encoding="utf-8") as log:
    log.write("".join(traceback.format_exception(exc_type, exc, tb)))
    log.write("\n")


if __name__ == "__main__":
  if os.environ.get("AUTO_COPIER_CLIPBOARD_HOLD") == "1":
    hold_clipboard_and_exit()
  sys.excepthook = _log_uncaught
  root = tk.Tk(className="autocopier")
  apply_window_icon(root)
  app = AutoPasswordZipCopierApp(root)
  root.mainloop()