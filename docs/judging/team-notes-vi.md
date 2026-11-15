# Ghi chú cho đội FireTrace

Đối tượng chính là người quản lý rừng/đất. Câu chuyện: chọn bằng chứng thật,
xem các thời kỳ cần đối chiếu, rồi mang bản tóm tắt và gói audit đi trao đổi
với chuyên gia địa phương. Chưa có nghiên cứu người dùng thực tế hay số liệu
chứng minh tác động đến quyết định quản lý.

Chọn **Explore NASA FIRMS case** để dùng dữ liệu NASA thật. Màn hình mở đầu và
các preset khác vẫn là dữ liệu giả lập, có nhãn riêng. Ca Tây Nguyên là hình
chữ nhật nghiên cứu `[107.8,12.5,108.5,13.1]`, không phải ranh giới hành chính,
vườn quốc gia hay vùng rừng đã kiểm chứng. Có 16.258 dòng: 4.143 MODIS và 12.115
VIIRS S-NPP, trích từ 37 tệp NASA. Không có API key trong gói này.

Hai hệ số chỉ học từ 2013–2020, sau đó đánh giá 2021–2024. Lịch sử tham chiếu
2001–2020 dùng những tháng có bằng chứng, không tự bù tháng trống bằng số 0.
Tháng 2 được chọn ban đầu do trung vị tham chiếu cao nhất, không phải vì đội
tìm tháng có bất thường đẹp nhất ở tập đánh giá.

Kết quả occupancy ngoài mẫu khá nhất quán giữa hai cảm biến, nhưng FRP còn yếu:
efficiency khoảng −5,058 trên 35 cặp. Phải trình bày kết quả âm này. Không gọi
R² là độ chính xác dự báo, không gọi HHE là số vụ cháy, không gọi FRP là năng
lượng/diện tích cháy, không suy ra nguyên nhân cháy từ mẫu nhiệt.

**UNVERIFIABLE là kết luận đúng với bằng chứng hiện có.** Có bản ghi hotspot
không chứng minh đã quan sát đầy đủ mọi thời kỳ. Cần dữ liệu độ phủ, sự cố thực
địa và lớp phủ đất trước khi đưa ra kết luận nguy cơ đã kiểm chứng.

Chuẩn bị demo: cài Python 3.11 và requirements; chạy `python run.py`; mở
localhost:8000. Dùng ba bước trên giao diện, thử raw/harmonized và phần đánh giá
Sensor Bridge, mở Audit để đọc brief, tải receipt/audit ZIP. Giải nén ZIP rồi
chạy `python -S -B verify.py receipt.json`. VALID chỉ xác nhận tính nhất quán,
không xác thực NASA hay chứng nhận kết quả khoa học.

Mốc 23:00 là hạn nội bộ của đội. Khung năm tiêu chí 2025 chỉ là tham chiếu có
ghi rõ năm; hướng dẫn chấm 2026 chưa truy cập được. Bảy slide là đề xuất nội bộ.
Chưa đổi quyền repo, chưa đăng/nộp bài và chưa deployment. Chủ repo cần xử lý
các bước đó riêng, đồng thời đối chiếu đúng yêu cầu dự thi hiện hành.
