---
name: weather
track: custom
kind: live_api
provider: Open-Meteo
requires_env: []
inputs: [location, days]
outputs: [location, items]
side_effect: false
---
# weather

Tra cứu thông tin dự báo thời tiết tại một thành phố hoặc địa điểm cụ thể.
