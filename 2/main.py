from itertools import combinations

ticket: tuple[int, ...] = (3, 2, 1, 0, 2, 4)

def check_lucky_ticket(ticket: tuple[int, ...]) -> bool:
    total: int = sum(ticket)

    if total % 2 != 0:
        return False

    half: int = total // 2

    for combo in combinations(range(6), 3):
        if sum(ticket[i] for i in combo) == half:
            return True

    return False

print(check_lucky_ticket(ticket))
