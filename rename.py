# remove_vietnamese_gui_complete.py
import os
import re
import json
import time
import platform
from unidecode import unidecode
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

# ---------------- Helpers ----------------

def sanitize_filename(name):
    """
    Bỏ dấu + thay ký tự không hợp lệ bằng dấu gạch dưới.
    Trả về tên đã sanitize (không đường dẫn).
    """
    name = unidecode(name)
    # Thay ký tự không hợp lệ trên Windows bằng '_'
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    # Loại nhiều khoảng trắng thừa
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def make_long_path(path):
    """
    Trả về đường dẫn kèm tiền tố \\?\ nếu trên Windows và đường dẫn >=260.
    Nếu không cần thì trả về path nguyên bản.
    """
    if os.name == 'nt':
        abs_path = os.path.abspath(path)
        # Nếu đã có \\?\ thì giữ nguyên
        if abs_path.startswith('\\\\?\\'):
            return abs_path
        # Windows API Long Path: thêm \\?\ nếu quá dài
        if len(abs_path) >= 260:
            return '\\\\?\\' + abs_path
        return abs_path
    else:
        return path

def safe_rename(old_path, new_path):
    """
    Đổi tên an toàn: nếu target tồn tại thì thêm " (1)", "(2)".
    Trả về đường dẫn thực tế sau khi đổi tên.
    Lưu ý: sử dụng make_long_path trước khi gọi os.rename để hỗ trợ đường dẫn dài trên Windows.
    """
    base, ext = os.path.splitext(new_path)
    final_path = new_path
    counter = 1

    # Nếu final_path trùng với old_path (chỉ khác case trên FS case-insensitive),
    # cần xử lý đặc biệt: đổi tạm thời tên trung gian.
    try:
        # Nếu final_path exists và là cùng 1 file as old_path (path equality ignore case),
        # Windows có thể coi là trùng; handle by using intermediate name
        # But simplest approach is to check os.path.abspath equality
        if os.path.abspath(old_path) == os.path.abspath(final_path):
            return final_path  # không cần đổi
    except Exception:
        pass

    while os.path.exists(final_path):
        # Nếu tồn tại nhưng là chính file đang muốn đổi (vì case-only rename), break
        try:
            if os.path.samefile(old_path, final_path):
                return final_path
        except Exception:
            # os.path.samefile có thể lỗi trên một vài hệ thống; ignore
            pass

        final_path = f"{base} ({counter}){ext}"
        counter += 1

    # Thực hiện đổi tên với hỗ trợ long path
    oldp = make_long_path(old_path)
    newp = make_long_path(final_path)
    os.rename(oldp, newp)
    return final_path

def count_items(root_folder):
    """Đếm tổng số mục (file + thư mục) để tính progress."""
    count = 0
    for dirpath, dirnames, filenames in os.walk(root_folder):
        count += len(filenames) + len(dirnames)
    return max(count, 1)

# ---------------- Main processing ----------------

def process_items(root_folder, log_widget, progress_var, root,
                  do_rename=False, create_backup=False):
    """
    Thực hiện quét (topdown=False để đổi tên thư mục sau các file con).
    Nếu do_rename=False -> chỉ Preview (không đổi).
    Nếu create_backup=True -> lưu mapping old->new vào list để xuất ra file JSON sau khi hoàn tất.
    """
    total = count_items(root_folder)
    done = 0
    backup_list = []

    # Duyệt từ dưới lên để đổi tên thư mục sau khi đổi tên file/dir con
    for dirpath, dirnames, filenames in os.walk(root_folder, topdown=False):
        # Xử lý files
        for filename in filenames:
            try:
                new_filename = sanitize_filename(filename)
                old_path = os.path.join(dirpath, filename)
                new_path = os.path.join(dirpath, new_filename)

                # Nếu tên không đổi -> bỏ qua
                if filename != new_filename:
                    if do_rename:
                        try:
                            final = safe_rename(old_path, new_path)
                            log_widget.insert(tk.END, f"OK: {old_path} -> {final}\n")
                            if create_backup:
                                backup_list.append({"old": old_path, "new": final})
                        except Exception as e:
                            log_widget.insert(tk.END, f"❌ Lỗi: {old_path} -> {new_path} | {e}\n")
                    else:
                        log_widget.insert(tk.END, f"Preview: {old_path} -> {new_path}\n")

                # update progress
            except Exception as e:
                log_widget.insert(tk.END, f"❌ Lỗi xử lý file: {dirpath}\\{filename} | {e}\n")

            done += 1
            progress_var.set(int(done / total * 100))
            root.update_idletasks()

        # Xử lý thư mục
        for dirname in dirnames:
            try:
                new_dirname = sanitize_filename(dirname)
                old_path = os.path.join(dirpath, dirname)
                new_path = os.path.join(dirpath, new_dirname)

                if dirname != new_dirname:
                    if do_rename:
                        try:
                            final = safe_rename(old_path, new_path)
                            log_widget.insert(tk.END, f"OK: {old_path} -> {final}\n")
                            if create_backup:
                                backup_list.append({"old": old_path, "new": final})
                        except Exception as e:
                            log_widget.insert(tk.END, f"❌ Lỗi: {old_path} -> {new_path} | {e}\n")
                    else:
                        log_widget.insert(tk.END, f"Preview: {old_path} -> {new_path}\n")
            except Exception as e:
                log_widget.insert(tk.END, f"❌ Lỗi xử lý thư mục: {dirpath}\\{dirname} | {e}\n")

            done += 1
            progress_var.set(int(done / total * 100))
            root.update_idletasks()

    return backup_list

# ---------------- GUI ----------------

def select_folder_and_run(mode):
    folder = filedialog.askdirectory()
    if not folder:
        return

    # reset log
    log_box.delete(1.0, tk.END)
    if mode == "preview":
        log_box.insert(tk.END, f"👀 Xem trước các mục sẽ đổi trong thư mục:\n{folder}\n\n")
    else:
        log_box.insert(tk.END, f"👉 Đang đổi tên trong thư mục:\n{folder}\n\n")

    progress_var.set(0)
    progress_bar.update()

    # Nếu người dùng chọn tạo backup, hỏi file name và lưu mapping sau khi đổi xong
    create_backup = backup_var.get() == 1

    backup_list = process_items(folder, log_box, progress_var, root,
                                do_rename=(mode == "rename"),
                                create_backup=create_backup)

    progress_var.set(100)
    progress_bar.update()

    if mode == "preview":
        log_box.insert(tk.END, "\n🔎 Đây chỉ là bản xem trước, chưa đổi tên!\n")
        messagebox.showinfo("Xem trước", "Đã hiển thị danh sách đổi tên (chưa đổi).")
    else:
        log_box.insert(tk.END, "\n✅ Hoàn tất đổi tên!\n")
        messagebox.showinfo("Xong", "Đã hoàn tất đổi tên.")

    # Nếu cần backup, ghi file JSON mapping (cả thời gian để phân biệt)
    if create_backup and backup_list:
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_fn = os.path.join(folder, f"rename_backup_{timestamp}.json")
            # Ghi JSON với ensure_ascii=False để giữ UTF-8 đọc dễ
            with open(backup_fn, "w", encoding="utf-8") as f:
                json.dump(backup_list, f, ensure_ascii=False, indent=2)
            log_box.insert(tk.END, f"\n💾 Backup mapping saved: {backup_fn}\n")
        except Exception as e:
            log_box.insert(tk.END, f"\n❌ Không lưu được backup: {e}\n")

# Khởi tạo GUI
root = tk.Tk()
root.title("Xóa dấu tiếng Việt - Rename không dấu (Hoàn thiện)")
root.geometry("900x700")

top_frame = tk.Frame(root)
top_frame.pack(pady=10)

btn_preview = tk.Button(top_frame, text="👀 Xem trước", command=lambda: select_folder_and_run("preview"), font=("Arial", 12))
btn_preview.grid(row=0, column=0, padx=8)

btn_rename = tk.Button(top_frame, text="✅ Thực hiện đổi tên", command=lambda: select_folder_and_run("rename"), font=("Arial", 12))
btn_rename.grid(row=0, column=1, padx=8)

backup_var = tk.IntVar(value=1)
chk_backup = tk.Checkbutton(top_frame, text="Tạo file backup mapping (JSON)", variable=backup_var)
chk_backup.grid(row=0, column=2, padx=12)

note_label = tk.Label(root, text="Ghi chú: nếu có file/thu mục sau khi đổi trùng tên sẽ tự thêm ' (1)', ' (2)'... để tránh mất dữ liệu.", fg="blue")
note_label.pack(pady=6)

progress_var = tk.IntVar()
progress_bar = ttk.Progressbar(root, orient="horizontal", length=860, mode="determinate", variable=progress_var)
progress_bar.pack(pady=5)

log_box = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=110, height=35, font=("Consolas", 10))
log_box.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

root.mainloop()
