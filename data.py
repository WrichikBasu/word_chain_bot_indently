from collections import deque


class LimitedLengthList(deque):
    def __init__(self, list_length, *args, **kwargs):
        self.list_length = list_length
        super().__init__(*args, **kwargs)

    def append(self, item: any):
        super().append(item)
        while len(self) > self.list_length:
            self.popleft()


class History(dict[int, LimitedLengthList[str]]):
    def __init__(self, history_length: int = 5, *args, **kwargs):
        self.__history_length = history_length
        super().__init__(*args, **kwargs)

    def __missing__(self, key):
        self[key] = LimitedLengthList(self.__history_length)
        return self[key]
