class HITLQueue:
    def __init__(self, store):
        self.store = store

    def list_open(self):
        return self.store.list_escalations()

    def resolve(self, complaint_id: int):
        return self.store.resolve_escalation(complaint_id)
