import requests
from PIL import Image
import os
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed # Import mới

def download_image(image_url):
    """
    Tải xuống một hình ảnh duy nhất.
    Trả về đối tượng PIL Image nếu thành công, None nếu thất bại.
    """
    try:
        response = requests.get(image_url, stream=True, timeout=10) # Thêm timeout
        response.raise_for_status()

        if 'image' not in response.headers.get('Content-Type', ''):
            print(f"URL {image_url} không trả về hình ảnh hợp lệ.")
            return None

        img = Image.open(BytesIO(response.content))
        # print(f"Đã tải xuống: {image_url}") # Có thể tắt nếu quá nhiều thông báo
        return img
    except requests.exceptions.RequestException as e:
        print(f"Lỗi tải xuống {image_url}: {e}")
        return None
    except Exception as e:
        print(f"Lỗi xử lý hình ảnh {image_url}: {e}")
        return None

def download_chapter_images_threaded(base_url_img, max_workers=8, start_image_index=0):
    """
    Tải xuống tất cả các hình ảnh của một chương truyện sử dụng đa luồng.

    Args:
        base_url_img (str): URL cơ sở của hình ảnh, ví dụ: "https://file.nhasachmienphi.com/jpg/nhasachmienphi-fairy-tail-hoi-phap_su-noi-tieng-326548-{}.jpg"
        max_workers (int): Số lượng luồng tối đa để tải ảnh trong một chương.
        start_image_index (int): Chỉ số bắt đầu của hình ảnh (thường là 0).

    Returns:
        list: Danh sách các đối tượng hình ảnh PIL đã tải xuống, đã sắp xếp.
    """
    chapter_images_map = {} # Dùng để lưu trữ ảnh theo index để sắp xếp
    futures = []

    # Giới hạn số lượng yêu cầu ban đầu để tìm ra số lượng ảnh thực tế
    # Sau đó mới tạo thêm các yêu cầu khác nếu cần
    initial_check_count = 500 # Giả định tối đa 500 ảnh cho mỗi chương. Có thể tăng/giảm.

    print(f"Đang tìm kiếm và tải ảnh cho chương...")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for i in range(start_image_index, start_image_index + initial_check_count):
            image_url = base_url_img.format(i)
            future = executor.submit(download_image, image_url)
            futures.append((i, future)) # Lưu trữ cả index và future

        # Chờ và xử lý kết quả
        found_last_image = False
        for index, future in sorted(futures, key=lambda x: x[0]):
            img = future.result()
            if img:
                chapter_images_map[index] = img
                found_last_image = True # Đã tìm thấy ít nhất 1 ảnh
            else:
                # Nếu không tải được ảnh (lỗi 404 hoặc không hợp lệ), coi như đã hết ảnh
                # Chỉ dừng nếu không có ảnh nào được tìm thấy ở các index cao hơn
                if found_last_image and index not in chapter_images_map:
                    # Kiểm tra xem có phải đây là ảnh cuối cùng không
                    # Logic này có thể cần tinh chỉnh nếu có những khoảng trống trong index ảnh
                    pass # Tiếp tục kiểm tra các ảnh tiếp theo trong initial_check_count
                else:
                    break # Nếu ảnh đầu tiên không có, hoặc có lỗ hổng lớn, dừng

    # Sắp xếp lại ảnh theo thứ tự index
    sorted_images = [chapter_images_map[i] for i in sorted(chapter_images_map.keys())]
    print(f"Đã tải được {len(sorted_images)} hình ảnh cho chương.")
    return sorted_images

def create_pdf_from_images(images, output_filename):
    """
    Tạo file PDF từ danh sách các đối tượng hình ảnh PIL.
    """
    if not images:
        print(f"Không có hình ảnh để tạo PDF cho {output_filename}.")
        return

    try:
        rgb_images = []
        for img in images:
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            rgb_images.append(img)

        rgb_images[0].save(output_filename, save_all=True, append_images=rgb_images[1:])
        print(f"Đã tạo file PDF: {output_filename}")
    except Exception as e:
        print(f"Lỗi khi tạo PDF {output_filename}: {e}")

def download_manga_series_threaded(start_chapter_id, end_chapter_id, series_name="Fairy Tail_Manga", max_chapter_workers=2, max_image_workers_per_chapter=8):
    """
    Tải xuống toàn bộ series truyện tranh sử dụng đa luồng cho cả chương và ảnh.

    Args:
        start_chapter_id (int): ID của chương bắt đầu.
        end_chapter_id (int): ID của chương kết thúc.
        series_name (str): Tên của bộ truyện (để tạo thư mục).
        max_chapter_workers (int): Số lượng chương tối đa được tải song song.
        max_image_workers_per_chapter (int): Số lượng luồng tối đa để tải ảnh trong một chương.
    """
    output_dir = os.path.join(os.getcwd(), series_name)
    os.makedirs(output_dir, exist_ok=True)
    print(f"Các file PDF sẽ được lưu vào thư mục: {output_dir}")

    # Sử dụng ThreadPoolExecutor để xử lý các chương song song
    with ThreadPoolExecutor(max_workers=max_chapter_workers) as chapter_executor:
        chapter_futures = []
        for chapter_id in range(start_chapter_id, end_chapter_id + 1):
            chapter_filename = os.path.join(output_dir, f"{series_name}_Chapter_{chapter_id}.pdf")
            if os.path.exists(chapter_filename):
                print(f"File {chapter_filename} đã tồn tại, bỏ qua chương này.")
                continue

            chapter_futures.append(
                chapter_executor.submit(
                    process_single_chapter,
                    chapter_id,
                    series_name,
                    chapter_filename,
                    max_image_workers_per_chapter
                )
            )

        # Chờ tất cả các chương hoàn thành
        for future in as_completed(chapter_futures):
            try:
                future.result() # Lấy kết quả nếu cần, hoặc để kiểm tra lỗi
            except Exception as e:
                print(f"Lỗi khi xử lý một chương: {e}")

def process_single_chapter(chapter_id, series_name, chapter_filename, max_image_workers_per_chapter):
    """
    Hàm xử lý một chương duy nhất, dùng trong ThreadPoolExecutor.
    """
    print(f"\nĐang xử lý chương: {chapter_id}")
    base_url_img = f"https://file.nhasachmienphi.com/jpg/nhasachmienphi-fairy-tail-hoi-phap_su-noi-tieng-{chapter_id}-{{}}.jpg"

    images = download_chapter_images_threaded(base_url_img, max_workers=max_image_workers_per_chapter)
    if images:
        create_pdf_from_images(images, chapter_filename)
    else:
        print(f"Không tìm thấy hình ảnh cho chương {chapter_id}. Có thể chương này chưa có hoặc ID không đúng.")


# --- Cấu hình và chạy ---
if __name__ == "__main__":
    # Thay đổi các giá trị này theo nhu cầu của bạn
    start_id = 326548  # ID của chương đầu tiên bạn muốn tải
    end_id = 327092    # ID của chương cuối cùng bạn muốn tải (ví dụ: đến chương 326550)

    # Cấu hình số lượng luồng
    # Với 4 luồng CPU, bạn có thể thử max_chapter_workers = 2 hoặc 3 (để lại 1 luồng cho hệ thống)
    # max_image_workers_per_chapter nên từ 8-16, tùy thuộc vào độ ổn định của server.
    MAX_CHAPTER_WORKERS = 2 # Số chương được xử lý song song
    MAX_IMAGE_WORKERS_PER_CHAPTER = 10 # Số ảnh được tải song song trong một chương

    download_manga_series_threaded(
        start_id,
        end_id,
        series_name="Fairy_Tail_Hoi_Phap_Su",
        max_chapter_workers=MAX_CHAPTER_WORKERS,
        max_image_workers_per_chapter=MAX_IMAGE_WORKERS_PER_CHAPTER
    )
    print("\nQuá trình tải xuống và chuyển đổi đã hoàn tất!")
