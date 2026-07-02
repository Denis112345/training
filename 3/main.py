def get_by_path(data: dict, path: str):
    keys: list[str] = path.split(".")
    result = data

    for key in keys:
        result = result[key]

    return result


data = {
    "a": {
        "b": {
            "c": "+++"
        }
    }
}

value = get_by_path(data, "a.b.c")
print(value)
