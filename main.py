import requests
from bs4 import BeautifulSoup
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from fpdf import FPDF
import glob

# --- THIẾT LẬP CƠ BẢN ---
TRUYEN_SLUG = "quy-khoc-quy-xa"
URL_GOC = "https://vozer.io/"
CHUONG_BAT_DAU = 1
CHUONG_KET_THUC = 1031
THU_MUC_LUU = f"truyen_{TRUYEN_SLUG}_PDF"
SO_LUONG_TOI_DA = 10  # Số luồng tải cùng lúc (có thể tăng lên 10–20 nếu mạng khỏe)
# ------------------------

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9',
    'Accept-Language': 'vi-VN,vi;q=0.9',
    'Referer': f'{URL_GOC}{TRUYEN_SLUG}/',
}

FONT_PATH = None

# --- HÀM TÌM FONT UNICODE ---
def find_unicode_font():
    font_paths = [
        '/usr/share/fonts/truetype/**/Arial.ttf',
        '/usr/share/fonts/truetype/**/DejaVuSans.ttf',
        'C:/Windows/Fonts/arialuni.ttf',
        'C:/Windows/Fonts/arial.ttf',
        '/System/Library/Fonts/Supplemental/Arial.ttf'
    ]
    for path in font_paths:
        found = glob.glob(path, recursive=True)
        if found:
            return found[0]
    return None

# --- LỚP PDF ---
class PDF(FPDF):
    def __init__(self):
        super().__init__()
        if FONT_PATH:
            self.add_font("CustomFont", style="", fname=FONT_PATH)
            self.add_font("CustomFont", style="B", fname=FONT_PATH)  # thêm font bold
            self.set_font("CustomFont", size=11)
        else:
            self.set_font("Arial", size=11)
        self.set_auto_page_break(auto=True, margin=15)

    def header(self):
        self.set_font("Arial" if FONT_PATH is None else "CustomFont", size=9)
        self.cell(0, 10, TRUYEN_SLUG, 0, new_x="LMARGIN", new_y="NEXT", align='R')

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial" if FONT_PATH is None else "CustomFont", size=8)
        self.cell(0, 10, f"Trang {self.page_no()}", 0, new_x="LMARGIN", new_y="NEXT", align='C')

# --- HÀM TẢI 1 CHƯƠNG ---
def tai_chuong(so_chuong):
    url = f"{URL_GOC}{TRUYEN_SLUG}/chuong-{so_chuong}"
    s = requests.Session()
    s.headers.update(HEADERS)

    try:
        r = s.get(url, timeout=15)
        r.raise_for_status()
    except requests.RequestException:
        return so_chuong, None, None

    soup = BeautifulSoup(r.text, "html.parser")
    chapter_container = soup.find('div', id='chapter-001') or \
                        soup.find('div', id=f'chapter-{so_chuong}') or \
                        soup.find('div', class_='font-content')

    if not chapter_container:
        return so_chuong, None, None

    tieu_de_element = chapter_container.find('h1')
    tieu_de = tieu_de_element.text.strip() if tieu_de_element else f"Chương {so_chuong}"

    noi_dung_element = chapter_container.find('div', id='content')
    paragraphs = (noi_dung_element or chapter_container).find_all('p')
    noi_dung = "\n\n".join(p.text.strip() for p in paragraphs if p.text.strip())

    return so_chuong, tieu_de, noi_dung or "Nội dung không tải được."

# --- HÀM LƯU PDF ---
def luu_pdf(so_chuong, tieu_de, noi_dung, folder_path):
    ten_file_pdf = f"{TRUYEN_SLUG}_chuong_{so_chuong:04d}.pdf"
    duong_dan_file = os.path.join(folder_path, ten_file_pdf)
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial" if FONT_PATH is None else "CustomFont", style="B", size=14)
    pdf.multi_cell(0, 10, f"Chương {so_chuong}: {tieu_de}")
    pdf.ln(5)
    pdf.set_font("Arial" if FONT_PATH is None else "CustomFont", size=11)
    pdf.multi_cell(0, 7, noi_dung)
    pdf.output(duong_dan_file)

# --- MAIN ---
if __name__ == "__main__":
    print("🔍 Đang tìm font Unicode...")
    FONT_PATH = find_unicode_font()
    if FONT_PATH:
        print(f"✅ Font Unicode: {FONT_PATH}")
    else:
        print("⚠️ Không tìm thấy font Unicode. Có thể lỗi tiếng Việt.")

    if not os.path.exists(THU_MUC_LUU):
        os.makedirs(THU_MUC_LUU)

    tong_so = CHUONG_KET_THUC - CHUONG_BAT_DAU + 1
    thanh_cong = 0

    print(f"🚀 Bắt đầu tải {tong_so} chương bằng {SO_LUONG_TOI_DA} luồng...\n")

    start_time = time.time()
    with ThreadPoolExecutor(max_workers=SO_LUONG_TOI_DA) as executor:
        futures = [executor.submit(tai_chuong, i) for i in range(CHUONG_BAT_DAU, CHUONG_KET_THUC + 1)]

        for future in as_completed(futures):
            so_chuong, tieu_de, noi_dung = future.result()
            if noi_dung and "không tải" not in noi_dung:
                luu_pdf(so_chuong, tieu_de, noi_dung, THU_MUC_LUU)
                thanh_cong += 1
                print(f"✅ Chương {so_chuong} ({thanh_cong}/{tong_so})")
            else:
                print(f"❌ Lỗi chương {so_chuong}")

    print(f"\n--- HOÀN TẤT ---")
    print(f"📚 Tổng số chương thành công: {thanh_cong}/{tong_so}")
    print(f"🕒 Thời gian: {time.time() - start_time:.2f} giây")
    print(f"📂 File PDF đã lưu tại: {os.path.abspath(THU_MUC_LUU)}")
