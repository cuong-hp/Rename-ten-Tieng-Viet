# remove_vietnamese_gui_complete_v4.py
import os
import re
import json
import time
import platform
from unidecode import unidecode
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

# ---------------- Helpers ----------------

def sanitize_filename(name, replace_spaces=False):
    """
    Xử lý tên file: bỏ dấu, thay ký tự đặc biệt.
    replace_spaces=True: thay thế cả khoảng trắng thành '_'
    """
    name = unidecode(name) # Bỏ dấu tiếng Việt
    
    # Xử lý %20 thành dấu cách trước
    name = name.replace("%20", " ") 

    # Thay ký tự cấm trên Windows
    name = re.sub(r'[\\/:*?"<>|]', '_', name)

    # Xử lý khoảng trắng thừa
    name = re.sub(r'\s+', ' ', name).strip()

    # Nếu tùy chọn thay thế khoảng trống được bật
    if replace_spaces:
        name = name.replace(" ", "_")

    return name

def make_long_path(path):
    """Hỗ trợ đường dẫn dài trên Windows (Long Path)"""
    if os.name == 'nt':
        abs_path = os.path.abspath(path)
        if abs_path.startswith('\\\\?\\'):
            return abs_path
        if len(abs_path) >= 260:
            return '\\\\?\\' + abs_path
        return abs_path
    else:
        return path

def safe_rename(old_path, new_path):
    """Đổi tên an toàn, tự động thêm (1), (2) nếu trùng."""
    base, ext = os.path.splitext(new_path)
    final_path = new_path
    counter = 1

    try:
        # Kiểm tra nếu chỉ khác viết hoa/thường (trên Windows)
        if os.path.abspath(old_path) == os.path.abspath(final_path):
            return final_path
    except Exception:
        pass

    while os.path.exists(final_path):
        try:
            if os.path.samefile(old_path, final_path):
                return final_path
        except Exception:
            pass
        final_path = f"{base} ({counter}){ext}"
        counter += 1

    oldp = make_long_path(old_path)
    newp = make_long_path(final_path)
    os.rename(oldp, newp)
    return final_path

def count_items(root_folder):
    """Đếm item để chạy progress bar"""
    count = 0
    for dirpath, dirnames, filenames in os.walk(root_folder):
        count += len(filenames) + len(dirnames)
    return max(count, 1)

# ---------------- Restore Logic (Mới) ----------------

def restore_from_json(json_path, log_widget, progress_var, root):
    """
    Khôi phục tên file từ file backup JSON.
    Quy tắc: Đọc ngược danh sách (LIFO) để khôi phục folder cha trước.
    """
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        messagebox.showerror("Lỗi", f"Không đọc được file JSON: {e}")
        return

    if not isinstance(data, list):
        messagebox.showerror("Lỗi", "File JSON không đúng định dạng danh sách.")
        return

    total = len(data)
    done = 0
    
    log_widget.insert(tk.END, f"♻️ Bắt đầu khôi phục từ: {json_path}\n...\n")
    
    # QUAN TRỌNG: Duyệt ngược danh sách (reversed)
    # Vì lúc tạo backup: File con -> Folder cha
    # Lúc khôi phục: Phải khôi phục Folder cha về tên cũ trước -> mới tìm thấy File con bên trong
    for entry in reversed(data):
        old_original = entry.get('old') # Đường dẫn gốc ban đầu
        current_path = entry.get('new') # Đường dẫn hiện tại (đã đổi)
        
        if not old_original or not current_path:
            continue

        try:
            # Kiểm tra xem file hiện tại có tồn tại không
            if os.path.exists(current_path):
                # Thực hiện đổi tên ngược lại
                # Dùng safe_rename để tránh trường hợp file cũ đã được tạo lại bởi user
                final = safe_rename(current_path, old_original)
                log_widget.insert(tk.END, f"Đã khôi phục: {os.path.basename(current_path)} -> {os.path.basename(final)}\n")
            else:
                log_widget.insert(tk.END, f"⚠️ Không tìm thấy: {current_path} (Bỏ qua)\n")
        except Exception as e:
            log_widget.insert(tk.END, f"❌ Lỗi khôi phục: {current_path} -> {old_original} | {e}\n")

        done += 1
        progress_var.set(int(done / total * 100))
        root.update_idletasks()

    log_widget.insert(tk.END, "\n✅ Hoàn tất khôi phục!\n")
    messagebox.showinfo("Xong", "Đã hoàn tất quá trình khôi phục.")

# ---------------- Rename Logic ----------------

def process_items(root_folder, log_widget, progress_var, root,
                  do_rename=False, create_backup=False, replace_spaces=False):
    total = count_items(root_folder)
    done = 0
    backup_list = []
    change_count = 0

    for dirpath, dirnames, filenames in os.walk(root_folder, topdown=False):
        # 1. Xử lý Files
        for filename in filenames:
            try:
                new_filename = sanitize_filename(filename, replace_spaces=replace_spaces)
                old_path = os.path.join(dirpath, filename)
                new_path = os.path.join(dirpath, new_filename)

                if filename != new_filename:
                    change_count += 1
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
                log_widget.insert(tk.END, f"❌ Lỗi file: {filename} | {e}\n")

            done += 1
            progress_var.set(int(done / total * 100))
            root.update_idletasks()

        # 2. Xử lý Thư mục
        for dirname in dirnames:
            try:
                new_dirname = sanitize_filename(dirname, replace_spaces=replace_spaces)
                old_path = os.path.join(dirpath, dirname)
                new_path = os.path.join(dirpath, new_dirname)

                if dirname != new_dirname:
                    change_count += 1
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
                log_widget.insert(tk.END, f"❌ Lỗi folder: {dirname} | {e}\n")

            done += 1
            progress_var.set(int(done / total * 100))
            root.update_idletasks()

    return backup_list, change_count

# ---------------- GUI Actions ----------------

current_folder = ""

def preview_action():
    global current_folder
    folder = filedialog.askdirectory()
    if not folder:
        return
    current_folder = folder

    log_box.delete(1.0, tk.END)
    log_box.insert(tk.END, f"👀 Xem trước tại: {current_folder}\n\n")

    progress_var.set(0)
    progress_bar.update()

    create_backup = backup_var.get() == 1
    do_replace_spaces = replace_space_var.get() == 1

    backup_list, changes = process_items(current_folder, log_box, progress_var, root,
                                       do_rename=False,
                                       create_backup=create_backup,
                                       replace_spaces=do_replace_spaces)

    progress_var.set(100)
    progress_bar.update()

    if changes > 0:
        log_box.insert(tk.END, f"\n🔎 Xong xem trước! Phát hiện {changes} mục cần đổi tên.\n")
        if messagebox.askyesno("Xác nhận đổi tên", f"Tìm thấy {changes} mục cần đổi tên.\n\nBạn có muốn thực hiện đổi tên ngay bây giờ không?"):
            log_box.insert(tk.END, f"\n👉 Đang thực hiện đổi tên tại: {current_folder}\n\n")
            
            # Thực hiện đổi tên thật
            backup_list, _ = process_items(current_folder, log_box, progress_var, root,
                                           do_rename=True,
                                           create_backup=create_backup,
                                           replace_spaces=do_replace_spaces)
            
            progress_var.set(100)
            progress_bar.update()

            log_box.insert(tk.END, "\n✅ Hoàn tất đổi tên!\n")
            messagebox.showinfo("Xong", "Đã hoàn tất quá trình đổi tên.")

            # Lưu Backup
            if create_backup and backup_list:
                try:
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    backup_fn = os.path.join(current_folder, f"rename_backup_{timestamp}.json")
                    with open(backup_fn, "w", encoding="utf-8") as f:
                        json.dump(backup_list, f, ensure_ascii=False, indent=2)
                    log_box.insert(tk.END, f"\n💾 Đã lưu file Backup: {backup_fn}\n")
                except Exception as e:
                    log_box.insert(tk.END, f"\n❌ Lỗi lưu backup: {e}\n")
        else:
            log_box.insert(tk.END, "\n✋ Đã hủy lệnh đổi tên. Bạn có thể xem lại danh sách trên.\n")
    else:
        log_box.insert(tk.END, "\n✨ Không có mục nào cần đổi tên (tất cả đã sạch dấu hoặc đúng định dạng).\n")
        messagebox.showinfo("Thông báo", "Không tìm thấy file hoặc thư mục nào cần đổi tên.")

def select_backup_and_restore():
    """Hàm cho nút Khôi phục"""
    json_path = filedialog.askopenfilename(
        title="Chọn file Backup JSON",
        filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
    )
    if not json_path:
        return
    
    log_box.delete(1.0, tk.END)
    progress_var.set(0)
    restore_from_json(json_path, log_box, progress_var, root)
    progress_var.set(100)

# ---------------- GUI Layout ----------------
root = tk.Tk()
root.title("Công cụ Đổi tên & Khôi phục (Full)")
root.geometry("950x700")

top_frame = tk.Frame(root)
top_frame.pack(pady=10)

# Hàng 1: Nút bấm
btn_start = tk.Button(top_frame, text="Xem trước", command=preview_action, font=("Arial", 11, "bold"), bg="#aaffaa")
btn_start.grid(row=0, column=0, padx=5)

# Nút Khôi phục mới
btn_restore = tk.Button(top_frame, text="Khôi phục", command=select_backup_and_restore, font=("Arial", 11), bg="#ffcccc")
btn_restore.grid(row=0, column=2, padx=5)

# Hàng 2: Tùy chọn
options_frame = tk.Frame(root)
options_frame.pack(pady=5)

backup_var = tk.IntVar(value=1)
chk_backup = tk.Checkbutton(options_frame, text="Tạo file backup (JSON)", variable=backup_var)
chk_backup.grid(row=0, column=0, padx=10)

replace_space_var = tk.IntVar(value=0)
chk_replace_space = tk.Checkbutton(options_frame, text="Xóa khoảng trống thành '_'", variable=replace_space_var, fg="red")
chk_replace_space.grid(row=0, column=1, padx=10)

# Tiến trình & Log
progress_var = tk.IntVar()
progress_bar = ttk.Progressbar(root, orient="horizontal", length=900, mode="determinate", variable=progress_var)
progress_bar.pack(pady=5)

log_box = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=115, height=35, font=("Consolas", 10))
log_box.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

root.mainloop()
