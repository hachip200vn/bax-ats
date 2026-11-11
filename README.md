# BAX ATS + Career Site – chạy localhost

Cần Python 3.8 trở lên. Không cần cài thêm gói nào.

1. Giải nén thư mục `bax-local`, mở terminal trong thư mục đó.
2. Chạy: `python3 server.py` (Windows: `python server.py`).
3. Mở ATS nội bộ: http://localhost:3001 (mở trước, lần đầu sẽ tự tạo dữ liệu mẫu).
4. Mở Career Site: http://localhost:3000

Thử luồng: ở ATS vào tab Đăng tuyển, bật kênh Career Site và bấm đăng, đăng một tin ở tab Tin tức tuyển dụng. Ở Career Site bấm Ứng tuyển để nộp hồ sơ. Trong vài giây hồ sơ hiện ở cột "Nộp hồ sơ" của ATS.

Dữ liệu lưu trong `bax.db`. Xoá file này (khi đã tắt server) để về dữ liệu mẫu ban đầu. Đổi cổng bằng biến môi trường `CAREER_PORT`, `ATS_PORT`.

## Đã làm thật và đang giả lập

Làm thật:
- Hai ứng dụng web riêng, hai cổng, dùng chung một database SQLite.
- Cổng 3000 chỉ có `/public/*`. API nội bộ `/api/*` chỉ có ở cổng 3001.
- Nộp hồ sơ, cộng đồng nhân tài, yêu cầu xoá dữ liệu: server kiểm tra đồng ý xử lý dữ liệu, email hợp lệ, chống nộp trùng cùng vị trí, giới hạn 30 yêu cầu mỗi phút mỗi IP, tự chấm điểm AI.
- Tin đăng và tin tức chỉ hiện ra Career Site khi ATS đã bật kênh Career Site.
- Ghi nhật ký vào bảng `audit` (xem tại http://localhost:3001/api/audit).

Giả lập (chưa nối hệ thống thật): gửi email/SMS (chỉ ghi vào nhật ký), đăng job board, Google/Outlook Calendar, link Zoom/Meet/Teams, DocuSign/VNPT eSign, đồng bộ HRIS, chấm điểm AI là so khớp từ khoá.

## Giới hạn của bản localhost
- Giao diện ATS giữ toàn bộ trạng thái dưới dạng một khối JSON trong SQLite, chưa tách thành các bảng như tài liệu đặc tả. Quy tắc nghiệp vụ nội bộ (phân quyền theo vai trò, quy tắc xem scorecard, duyệt nhiều cấp) vẫn kiểm tra ở giao diện ATS, chưa kiểm tra ở server. Việc chọn người dùng ở góc phải chỉ để thử vai trò, chưa phải đăng nhập.
- Chưa có tải CV dạng file, hồ sơ nộp bằng cách dán nội dung.
- Chỉ dùng để test một mình trên máy. Không đưa lên internet.
