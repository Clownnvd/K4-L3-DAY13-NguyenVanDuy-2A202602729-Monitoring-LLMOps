# Báo cáo cá nhân - K4-L3B Day 13 Monitoring & LLMOps

## 1. Thông tin học viên

- **Họ và tên:** Nguyễn Văn Duy
- **MSSV:** 2A202602729
- **Lớp:** K4-L3B
- **Repository:** [K4-L3-DAY13-NguyenVanDuy-2A202602729-Monitoring-LLMOps](https://github.com/Clownnvd/K4-L3-DAY13-NguyenVanDuy-2A202602729-Monitoring-LLMOps)
- **Commit SHA cuối:** SHA của nhánh `main` được cung cấp cùng URL khi nộp VLearn. Không thể ghi SHA của chính commit chứa dòng này vì sửa dòng sẽ đổi SHA.
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1` của starter K4-L3B.
- **Project Langfuse cá nhân:** `day13-k4-l3b-2A202602729` trên region EU, gói Hobby.

## 2. Evidence index

Ba kết quả lệnh trên cây mã nguồn cuối: [pytest.txt](evidence/pytest.txt), [log-validator.txt](evidence/log-validator.txt), [dashboard-validator.txt](evidence/dashboard-validator.txt).

| Ảnh runtime | Điều được kiểm chứng |
|---|---|
| [01 - Log sự cố](evidence/01-incident-log.png) | Hai event lấy trực tiếp từ `data/logs.jsonl`, cùng `req-b9bb996f`, response 2.653 ms. |
| [02 - Danh sách trace](evidence/02-trace-list.png) | Project cá nhân, 10 root trace của batch baseline, cột Input/Output trống. |
| [03 - Trace sự cố](evidence/03-incident-trace.png) | Trace `6f851543fd5061583a79fcda6e6713d0` cùng `req-b9bb996f`, cây retrieval/generation, thời gian, token và cost. |
| [04 - Prompt version](evidence/04-prompt-versioning.png) | Trace `production` v2 cạnh danh sách version sau rollback: v1 giữ `production` + `baseline`, v2 giữ `candidate`. |
| [05 - Dashboard sự cố](evidence/05-dashboard-incident.png) | Sáu panel có dữ liệu thật, 60 phút, ngưỡng và P95 tăng trong challenge. |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline CP0 | Kết quả cuối | Cách hiểu |
|---|---:|---:|---|
| Log validator | 30/100 | **100/100** | Log mới có correlation ID, metadata và không có PII mẫu nguyên văn. |
| Dashboard validator | 6/6 | **6/6** | Contract YAML đủ sáu panel; ảnh 05 chứng minh màn runtime có dữ liệu. |
| Pytest | 22 pass | **28 pass** | Có thêm test ID, PII, exception, generation và phép tổng hợp dashboard. |
| Root trace Langfuse | 0 | **18** | Batch đầu có 10 trace; các trace tiếp theo kiểm chứng version và challenge. |
| PII leak theo validator | 0 trên mẫu baseline | **0** | Test cuối bổ sung trường hợp CCCD, thẻ và context lồng nhau. |
| P95 / TTFT P95 | 153 / 51 ms | 2.777 / 51 ms trên toàn cửa sổ 60 phút | P95 cuối cao do cố ý bật challenge và có một lần tải prompt chậm; baseline khỏe sau CP1 có P95 159 ms. |
| Retrieval success | 100% | **100%** | Challenge lần này là truy xuất chậm, không phải truy xuất lỗi. |

Trong ảnh dashboard cuối có 34 request, 0 lỗi, cost ước tính 0,071835 USD, 1.175 token đầu vào, 4.554 token đầu ra và điểm chất lượng tham chiếu trung bình 85,9%. Fake LLM không phát sinh hóa đơn mô hình; cost là ước tính từ công thức trong source.

## 4. Logging và bảo vệ dữ liệu

- `app/middleware.py` xóa context của request trước; giữ header `x-request-id` nếu đúng `req-` + 8 ký tự hex, nếu sai thì sinh ID mới. ID và thời gian xử lý được trả qua response header.
- `app/main.py` bind `correlation_id`, `user_id_hash`, `session_id`, `feature`, `model`, `env` trước `request_received`. User ID được băm SHA-256 và chỉ lấy 12 ký tự đầu.
- `app/logging_config.py` chạy `scrub_event` đệ quy **trước** khi render ra console và ghi JSONL. Nó che email, số điện thoại Việt Nam, CCCD và số thẻ ngay cả khi nằm trong payload lồng nhau hoặc metadata dạng chuỗi. `tests/test_pii.py` và `tests/test_chat_observability.py` kiểm tra cả log runtime lẫn response header.
- `data/logs.jsonl` không được commit. Log baseline CP0 đã chuyển ra ngoài repository trước khi đo CP1. Ảnh 01 hiển thị hai event của cùng request; file `log-validator.txt` xác nhận 100/100 và 0 PII leak trên bộ kiểm thử.

## 5. Tracing và phiên bản prompt

`@observe` tạo cây `day13-agent-request → lab-agent-run → retrieval, generation`. Ba observation không capture raw input/output. Trace dùng user ID và session ID đã băm; metadata có `correlation_id`, tên/nhãn/version của prompt và `query_preview` đã scrub. Generation ghi model, token đầu vào/đầu ra và cost ước tính. Có 18 root trace trong project cá nhân; ảnh 02 chụp 10 trace của batch đầu.

| Bước | Nhãn và version thực dùng | Trace ID |
|---|---|---|
| Baseline | `baseline` → `day13-chat` v1 | `111aa7a091227a8352ca8e17a6974569` |
| Candidate | `candidate` → v2 | `bdd365d240c65b9ec04f6447a947da06` |
| Promote | `production` → v2 | `7f87025fc8f59c3864e248ac5ab45621` |
| Rollback | `production` → v1 | `5570f19a96d0f8e9c167aba82a32cfe1` |

Prompt v1 và v2 cùng giữ ba biến `{{feature}}`, `{{docs}}`, `{{message}}`; v2 thêm chỉ dẫn trả lời ngắn gọn. App lấy prompt bằng label, nên đổi label rồi restart là đổi version đang phục vụ. Một lần fetch prompt bị lỗi SSL và dùng `local-fallback`; trace đó không được tính là bằng chứng version. Sau khi restart, trace promote và rollback đều có `prompt_source=langfuse`.

## 6. Dashboard, SLO và cảnh báo

`dashboard/server.py` đọc `data/logs.jsonl` trong cửa sổ 60 phút, làm mới mỗi 30 giây và phục vụ màn full-width tại `http://127.0.0.1:8765`. Sáu panel là latency P50/P95/P99 và TTFT, traffic, error rate cùng retrieval success, cost, token và quality proxy. Ngưỡng hiển thị khớp `config/dashboard.yaml`; panel quality chỉ là tín hiệu sàng lọc, chưa phải điểm đánh giá thủ công.

SLO thí điểm trong `config/slo.yaml`: **99,5% request trong 28 ngày phải có `response_sent` với `latency_ms ≤ 1.000`**. Baseline khỏe P95 159 ms; ngưỡng 1.000 ms đủ rộng cho dao động nhỏ và phát hiện rõ challenge 2,5 giây. Error budget là **0,5%**, tương đương tối đa **50 request không đạt trên 10.000 request**. Chưa suy rộng ngưỡng này thành cam kết production vì workload bài lab rất nhỏ.

Ba alert và runbook trong `config/alert_rules.yaml` cùng `docs/alerts.md`:

1. `HighLatencyP95`: P95 > 1.000 ms trong 5 phút.
2. `HighRequestErrorRate`: error rate > 2% trong 3 phút.
3. `LowRetrievalSuccess`: retrieval success < 90% trong 5 phút.

Mỗi runbook đi từ Metrics → Logs → Traces rồi mới chọn cách khắc phục. Cấu hình có owner, severity, duration và kênh Slack `#k4-l3b-alerts`; chưa nối bộ gửi thông báo Slack thật.

## 7. Điều tra challenge chính thức

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`, file từ starter K4-L3B, không sửa nội dung và không commit file này.
- **Khoảng thời gian:** batch có Langfuse bắt đầu khoảng **04:40:46 UTC ngày 30/09/2026** (11:40:46 giờ Việt Nam).
- **Metrics:** P95 khỏe trước sự cố 159 ms; phút 04:40 UTC có P95 **2.655 ms**. Panel TTFT vẫn khoảng 50 ms, error rate 0%, retrieval success 100%. Ảnh 05 chụp P95 **2.777 ms** của toàn cửa sổ 60 phút, có cả các lần thử prompt.
- **Logs:** `response_sent` của `req-b9bb996f` lúc **04:40:48.989463Z** có `latency_ms=2653`, `ttft_ms=50`, `tokens_in=35`, `tokens_out=98`, `cost_usd=0.001575`; request này xuất hiện cùng ID trong `request_received` (ảnh 01).
- **Trace:** ID `6f851543fd5061583a79fcda6e6713d0` có cùng `correlation_id`. `lab-agent-run` mất **2.653 ms**; child `retrieval` mất **2.501 ms**, `generation` **152 ms**, 133 token và cost ước tính 0,001575 USD (ảnh 03).
- **Root cause:** độ trễ nằm ở retrieval; challenge chính thức đã bật scenario `rag_slow`. Kết luận dựa trên P95 tăng, log của request cụ thể và span retrieval chiếm gần hết thời gian trace.
- **Fix action:** chạy `python scripts/inject_incident.py --scenario rag_slow --disable`; `/health` sau đó xác nhận mọi incident là `false`.
- **Preventive measure:** giữ alert P95, lọc request chậm theo `correlation_id`, kiểm tra retrieval span và so lại với baseline sau khi khôi phục. Không lấy thời gian client của `load_test.py --concurrency 5` làm latency API vì request có thể xếp hàng.

## 8. Quyết định, lỗi gặp và điều học được

- **Quyết định kỹ thuật:** dashboard dùng Python standard library + SVG, đọc cùng file JSONL mà validator kiểm tra. Cách này không cài Streamlit vào môi trường FastAPI/Langfuse và tránh làm lệch phiên bản phụ thuộc của bài.
- **Blocker:** Git qua `github.com:443` không kết nối được trên máy, nên lấy đúng fork bằng archive và đối chiếu cập nhật starter qua GitHub API. Một request sau khi promote prompt bị SSL timeout và rơi về `local-fallback`; restart API rồi chạy lại để có trace `production` v2 thực, không dùng fallback làm evidence.
- **Luồng điều tra:** Metrics định vị triệu chứng và thời gian; Logs lấy một `correlation_id` cùng giá trị bất thường; Traces cho thấy child span nào chậm/lỗi; root cause chỉ được ghi khi ba lớp bằng chứng khớp nhau.
- **Vận hành LLM:** prompt version giúp biết yêu cầu nào dùng bản chỉ dẫn nào và rollback khi chất lượng/cost xấu đi. Token và cost cho biết tải sinh nội dung; SLO và error budget biến cảm giác “chậm” thành ngưỡng đo được. Với fake LLM, cost hiện là số mô phỏng.
- **Hạn chế:** chỉ có 34 request trong ảnh dashboard; chưa có tải thật dài ngày, chưa đo chất lượng bằng người chấm và chưa triển khai thông báo Slack. SLO cần hiệu chỉnh lại trước production.

## 9. Tự kiểm tra trước khi nộp

- [x] Source có correlation ID, PII scrub, child observations và dashboard thật.
- [x] Có đúng 3 output text, 5 ảnh runtime. Ảnh 01 và 03 cùng `req-b9bb996f`.
- [x] Project Langfuse cá nhân có 18 root trace, prompt v1/v2 và bằng chứng promote/rollback.
- [x] Pytest 28 pass, log validator 100/100, dashboard validator 6/6.
- [x] `.env`, `config/challenge.json`, `data/logs.jsonl`, `.venv/` đều bị Git ignore.
- [ ] Đối chiếu commit cuối trên GitHub và nộp URL + SHA qua VLearn.
