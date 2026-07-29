# Day 04 Lab v2 Report — Research Agent

## Team

- **Members:**  Vũ Quang Nhật
- **Provider/model:** Groq (`llama-3.1-8b-instant`, `openai/gpt-oss-20b`), Gemini (`gemini-2.0-flash`), Openroute

---

# PHẦN A — Giới thiệu agent

## A1. Agent này làm được gì

Research Agent thông minh tích hợp khả năng tra cứu đa nguồn: tin tức web, bài đăng Twitter/X, bài báo khoa học arXiv, dự báo thời tiết trực tiếp, và quy định chính sách nội bộ công ty. Agent có khả năng tự động hỏi lại khi thiếu thông tin, xin xác nhận trước khi thực hiện hành động ghi nhạy cảm (Telegram), và hỗ trợ giao diện Web UI hiển thị quá trình suy luận (Live Tool Trace) trực quan.

**Link dùng thử (truy cập trong showdown):**

- **Local Web UI:** `http://localhost:8501`
- **Cloudflare Public Tunnel:** `cloudflared tunnel --url http://localhost:8501`

## A2. Tool agent có

| Tên tool         | Làm được gì                                                                                                                | Tool mới nhóm thêm?                 |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| `clarify`       | Hỏi lại người dùng khi thiếu thông tin (`text`) hoặc xin xác nhận trước hành động nhạy cảm (`yes_no`)      | Không (Core)                          |
| `timeline`      | Lấy bài đăng Twitter gần đây từ một tài khoản cụ thể (screenname)                                                  | Không (Core)                          |
| `social_search` | Tìm kiếm bài đăng Twitter theo từ khóa/chủ đề                                                                         | Không (Core)                          |
| `lookup`        | Tra cứu thông tin/tin tức thời sự trên web (Tavily search)                                                                | Không (Core)                          |
| `fetch`         | Đọc nội dung toàn văn từ một địa chỉ URL web cụ thể                                                                 | Không (Core)                          |
| `format`        | Trình bày dữ liệu digest theo khuôn định dạng đẹp                                                                     | Không (Core)                          |
| `weather`       | **Tra cứu dự báo thời tiết trực tiếp (nhiệt độ, tốc độ gió) tại địa điểm cụ thể qua Open-Meteo API** | **Có (Custom Tool nhóm làm)** |
| `policy`        | Tra cứu quy định/chính sách nội bộ công ty theo khu vực (RAG Policy search)                                            | Không (Extension)                     |
| `papers`        | Tìm kiếm bài báo khoa học trên arXiv theo từ khóa                                                                       | Không (Extension)                     |
| `paper_text`    | Tải PDF và trích xuất nội dung toàn văn từ arXiv ID                                                                     | Không (Extension)                     |
| `send`          | Gửi tin nhắn/bản tin lên kênh Telegram (Hành động có side-effect)                                                      | Không (Bonus)                         |

## A3. Câu hỏi mẫu để thử

1. **Thử Tool thời tiết mới:** `"Thời tiết ở Hà Nội hôm nay thế nào?"` $\rightarrow$ Agent gọi tool `weather(location="Hanoi")`.
2. **Thử Clarification khi thiếu thông tin:** `"Tóm tắt 5 tweet mới nhất giúp mình"` $\rightarrow$ Agent phát hiện thiếu handle, gọi `clarify` (`text`) để hỏi ai.
3. **Thử Confirmation Boundary nhạy cảm:** `"Đăng bản tin AI hôm nay lên Telegram giúp mình"` $\rightarrow$ Agent dừng lại, gọi `clarify` (`yes_no`) xin xác nhận đồng ý trước khi gửi.
4. **Thử Compound Parallel Tool Calls:** `"Tìm paper mới về AI agents và kiểm tra policy công ty về cách trích dẫn arXiv."` $\rightarrow$ Agent gọi 2 tool song song `papers` + `policy`.

## A4. Kịch bản demo đã rehearse

| Scenario                           | Tool trace cần thấy                                                            | Câu chuyện cải thiện version                                                          | Fallback run/transcript             |
| ---------------------------------- | -------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- | ----------------------------------- |
| 1. Hỏi thời tiết địa phương | `weather(location="Hanoi")`                                                    | Thêm custom tool`weather` kết nối API miễn phí Open-Meteo                          | `runs/v4_B_base_groq_*.json`      |
| 2. Thiếu handle người dùng     | `clarify(response_type="text")`                                                | Prompt v2 ép không đoán bừa handle nổi tiếng khi không có trong câu hỏi        | `runs/v3_B_base_groq_*.json`      |
| 3. Đăng bài Telegram nhạy cảm | `clarify(response_type="yes_no")`                                              | Prompt v3 tạo ranh giới xác nhận bắt buộc trước khi gửi tin nhắn                | `runs/v4_B_base_groq_*.json`      |
| 4. Tìm kiếm gộp 2 nguồn        | `lookup(...)` + `social_search(...)` hoặc `papers(...)` + `policy(...)` | Prompt v6 bổ sung các mẫu Few-Shot giúp LLM nhỏ gọi 2 tool song song trong 1 bước | `runs/v6_B_extension_groq_*.json` |

---

# PHẦN B — Chi tiết / Bằng chứng

## B1. Version evidence

| Version | Prompt/tool change                                               | Hypothesis                                                         | Metric name        | Before |   After | Run File                                                |
| ------- | ---------------------------------------------------------------- | ------------------------------------------------------------------ | ------------------ | -----: | ------: | ------------------------------------------------------- |
| v0      | Baseline prompt + tools                                          | Đánh giá độ chính xác ban đầu của mô hình              | case_accuracy      |   0.00 |  53.33% | `runs/v0_B_base_groq_20260729.json`                   |
| v1      | Thêm GroqProvider & Quy tắc routing cơ bản                   | Cải thiện routing cho tin tức và bài đăng Twitter           | case_accuracy      | 53.33% |  90.00% | `runs/v1_B_base_groq_20260729.json`                   |
| v2      | Chuẩn hóa mapping famous name -> handle                        | Tự động chuyển đổi Elon Musk -> elonmusk, Sam Altman -> sama | case_accuracy      | 90.00% |  90.00% | `runs/v2_B_base_groq_20260729.json`                   |
| v3      | Bổ sung Ranh giới xác nhận Telegram (R12)                    | Ép dùng`response_type="yes_no"` khi đăng bài Telegram       | case_accuracy      | 90.00% |  95.00% | `runs/v3_B_base_groq_20260729T110827341629.json`      |
| v4      | Bổ sung Tool gọi song song (R13) + Tool mới`weather`        | Gọi`lookup` + `social_search` cùng lúc cho câu hỏi kép   | case_accuracy      | 95.00% |  95.00% | `runs/v4_B_base_groq_20260729T115106897988.json`      |
| v5      | Chuẩn hóa định dạng arXiv ID (`1706.03762`) & policy area | Không tự ý thêm tiền tố URL khi đọc bài báo khoa học    | extension_accuracy | 30.00% |  60.00% | `runs/v5_B_extension_groq_20260729T120557593663.json` |
| v6      | Thêm ví dụ Few-Shot cho các câu hỏi gộp song song         | Giúp LLM nhỏ phát lệnh gọi 2 tool song song chuẩn 100%       | extension_accuracy | 60.00% | 100.00% | `runs/v6_B_extension_groq_20260729T122747489249.json` |

## B2. Failure analysis

| Case ID                      | Failure Type        | Actual Tool Calls                       | What Failed                                                                                 | Fix                                                                                               |
| ---------------------------- | ------------------- | --------------------------------------- | ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| R12_confirm_before_send      | `wrong_boundary`  | `clarify(response_type="text")`       | AI xem "bản tin này" là thiếu thông tin nên dùng text thay vì xin xác nhận yes/no | Thêm Mục 3 vào`system_prompt.md`: Mọi yêu cầu đăng Telegram BẮT BUỘC dùng `yes_no` |
| R13_parallel_web_and_tweets  | `wrong_tool`      | `[lookup]`                            | AI chỉ gọi`lookup` mà bỏ qua `social_search` khi người dùng hỏi cả 2 nguồn    | Thêm Mục 5 vào`system_prompt.md` ép phát lệnh gọi song song 2 tool                       |
| E05_arxiv_paper_text         | `wrong_arg_value` | `paper_text(arxiv_url="https://...")` | AI tự thêm tiền tố URL khi người dùng chỉ đưa ID`1706.03762`                    | Thêm quy tắc trong Section 4 giữ nguyên chuỗi ID gốc không thêm URL prefix                |
| E06_briefing_live_plus_style | `wrong_tool`      | `[lookup]`                            | AI chỉ gọi tin tức web mà quên kiểm tra policy trích dẫn công ty                   | Thêm các ví dụ Few-Shot song song trong Section 5 của`system_prompt.md`                    |

## B3. Team eval cases

10 Eval Cases đã tạo trong file `data/eval_group.json`:

| Case ID                              | What It Tests                                                      | Expected Tool/Behavior                            | Result |
| ------------------------------------ | ------------------------------------------------------------------ | ------------------------------------------------- | ------ |
| `G01_weather_routing`              | Hỏi thời tiết Hà Nội hôm nay                                 | `weather(location="Hanoi")`                     | PASS   |
| `G02_weather_missing_location`     | Hỏi thời tiết nhưng không nêu thành phố                    | `clarify(response_type="text")`                 | PASS   |
| `G03_policy_search_routing`        | Quy định xuất bản tài liệu công ty                          | `policy(policy_area="external_publishing")`     | PASS   |
| `G04_papers_arxiv_routing`         | Tìm 3 bài báo LLM Agent trên arXiv                             | `papers(query="LLM Agent", max_results=3)`      | PASS   |
| `G05_out_of_scope_cooking`         | Hỏi công thức nấu phở bò Hà Nội                            | `no_tool: true` (Từ chối vì ngoài phạm vi) | PASS   |
| `G06_multiturn_weather_clarify`    | Multi-turn: Lượt 1 hỏi thời tiết, lượt 2 bảo ở Đà Nẵng | `weather(location="Danang")`                    | PASS   |
| `G07_multiturn_paper_text`         | Multi-turn: Lượt 1 tìm paper, lượt 2 đọc bài ID 1706.03762 | `paper_text(arxiv_url="1706.03762")`            | PASS   |
| `G08_multiturn_weather_correction` | Multi-turn: Lượt 1 hỏi Tokyo, lượt 2 đổi sang Osaka         | `weather(location="Osaka")`                     | PASS   |
| `G09_multiturn_policy_clarify`     | Multi-turn: Lượt 1 hỏi bảo mật, lượt 2 chọn data privacy   | `policy(policy_area="data_privacy")`            | PASS   |
| `G10_multiturn_telegram_confirm`   | Multi-turn: Lượt 1 soạn tin, lượt 2 bảo đăng Telegram      | `clarify(response_type="yes_no")`               | PASS   |

## B4. Live chat evidence

| Scenario/Turn | Version | Tool Calls + Args                                   | Transcript/Run                            | Outcome                                           |
| ------------- | ------- | --------------------------------------------------- | ----------------------------------------- | ------------------------------------------------- |
| Live Chat 1   | v6      | `weather(location="Hanoi", days=1)`               | `transcripts/v6_groq_*.transcript.json` | Lấy thời tiết Hà Nội 29.1°C thành công    |
| Live Chat 2   | v6      | `clarify(question="...", response_type="text")`   | `transcripts/v6_groq_*.transcript.json` | Hỏi lại địa điểm khi thiếu                 |
| Live Chat 3   | v6      | `clarify(question="...", response_type="yes_no")` | `transcripts/v6_groq_*.transcript.json` | Xin xác nhận an toàn trước khi gửi Telegram |

## B5. Tool capability evidence

| Category                                       | Evidence File                                      | What Worked                                                                 | Risk / Guardrail                                                      |
| ---------------------------------------------- | -------------------------------------------------- | --------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| Must-have: tool mới đầu tiên (`weather`) | `tools/weather/tool.py`                          | Lấy dự báo thời tiết real-time từ Open-Meteo Geocoding + Forecast API | Bắt lỗi khi không tìm thấy vị trí hoặc thiếu location        |
| Optional built-in (`policy`, `papers`)     | `tools/policy/tool.py`, `tools/papers/tool.py` | Tra cứu tài liệu chính sách nội bộ & tìm bài báo khoa học arXiv  | Giới hạn`top_k` và lọc theo `policy_area` phù hợp           |
| Side-effect tool (`send` Telegram)           | `tools/send/tool.py`                             | Gửi tin nhắn lên Telegram khi có cờ`confirmed=True`                  | Bắt buộc xin xác nhận người dùng (`yes_no`) trước khi gọi |

## B6. Reflection

- **Sửa trong `system_prompt.md`:** Thích hợp nhất cho các quy tắc xử lý ranh giới an toàn (Confirmation Boundary `yes_no`), từ chối các câu hỏi ngoài phạm vi (Out-of-scope), và hướng dẫn phát lệnh gọi song song (Parallel Tool Calls) bằng các ví dụ Few-Shot.
- **Sửa trong `tools.yaml`:** Thích hợp nhất cho việc định nghĩa rõ kiểu dữ liệu (`enum`, `default`), các mô tả Tool nói rõ khi nào NÊN dùng và khi nào KHÔNG NÊN dùng.
- **Lỗi cần Manual Review:** Lỗi routing có thể PASS về mặt cú pháp nhưng nội dung tham số cần kiểm tra thủ công (như việc AI truyền chuỗi ID hay truyền URL đầy đủ vào `paper_text`).
- **Cải tiến tiếp theo:** Tích hợp thêm bộ nhớ đệm (Caching) cho các truy vấn thời tiết và tin tức để giảm số lượng API request và tối ưu tốc độ phản hồi.
