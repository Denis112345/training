import json

in_data: str = '{"one": ["http", "yandex.ru"], "two": ["https", "google.com"]}'

out_data: dict = json.loads(in_data)

print(out_data)
