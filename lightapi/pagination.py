class Paginator:
    def __init__(self, limit=100, offset=0):
        self.limit = limit
        self.offset = offset

    def paginate(self, query):
        return query.limit(self.limit).offset(self.offset)
