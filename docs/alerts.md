# Cảnh báo và hướng xử lý Day 13

Các ngưỡng dưới đây là cấu hình thí điểm từ baseline local ngày 30/09/2026: P95 159 ms trên 10 request. Người trực nhận cảnh báo qua Slack `#k4-l3b-alerts`; kênh cần được kết nối khi triển khai thật. Nguồn đo là `data/logs.jsonl`, thời gian trong log là UTC.

## Alert 1

- **Tên:** `HighLatencyP95`. **Mức:** warning. **Thời gian duy trì:** 5 phút.
- **Điều kiện:** P95 của `response_sent.latency_ms` lớn hơn 1.000 ms. Triệu chứng là người dùng phải chờ câu trả lời lâu hơn; ngưỡng này liên quan trực tiếp SLO `fast_successful_requests`.
- **Người phụ trách:** Nguyễn Văn Duy, MSSV 2A202602729.
- **Kiểm tra Metrics → Logs → Traces:** (1) Mở panel Latency, ghi P95/P99 và phút bắt đầu tăng so với baseline. (2) Lọc `response_sent` trong khoảng đó, chọn request có `latency_ms > 1000` và ghi `correlation_id`. (3) Mở trace cùng ID, so sánh duration của `retrieval` và `generation` để xác định bước chậm.
- **Khắc phục:** Chỉ tắt practice scenario, giảm tải hoặc rollback prompt nếu trace chỉ đúng nguyên nhân đó; chạy lại cùng workload rồi xác nhận P95 giảm. Không kết luận chỉ từ thời gian client vì request đồng thời có thể xếp hàng.

## Alert 2

- **Tên:** `HighRequestErrorRate`. **Mức:** critical. **Thời gian duy trì:** 3 phút.
- **Điều kiện:** `request_failed / request_received > 2%`. Triệu chứng là người dùng không nhận được câu trả lời; những request lỗi tiêu hao error budget của SLO.
- **Người phụ trách:** Nguyễn Văn Duy, MSSV 2A202602729.
- **Kiểm tra Metrics → Logs → Traces:** (1) Xác nhận panel Errors và thời điểm error rate tăng. (2) Lọc `request_failed`, nhóm theo `error_type`, lấy một `correlation_id` đại diện. (3) Mở trace tương ứng, xác định span nào lỗi và đối chiếu metadata với log.
- **Khắc phục:** Khôi phục dependency hoặc cấu hình gây lỗi theo trace; nếu lỗi do practice `tool_fail`, tắt scenario. Sau đó chạy load test và xác nhận error rate trở lại mức baseline.

## Alert 3

- **Tên:** `LowRetrievalSuccess`. **Mức:** warning. **Thời gian duy trì:** 5 phút.
- **Điều kiện:** tỷ lệ `tool_success == true` trên các event có `tool_success` xuống dưới 90%. Triệu chứng là người dùng nhận câu trả lời thiếu căn cứ hoặc thất bại ở bước tìm tài liệu.
- **Người phụ trách:** Nguyễn Văn Duy, MSSV 2A202602729.
- **Kiểm tra Metrics → Logs → Traces:** (1) Xem panel Errors, so sánh retrieval success với baseline 100%. (2) Lọc event `tool_success=false`, lấy `correlation_id` và `error_type`. (3) Mở trace cùng ID, kiểm tra span `retrieval`, duration và trạng thái lỗi.
- **Khắc phục:** Khôi phục kho tài liệu/dịch vụ truy xuất hoặc tắt practice scenario khi demo. Chạy lại workload, xác nhận retrieval success hồi phục và kiểm tra câu trả lời có căn cứ.
