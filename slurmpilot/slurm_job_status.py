class SlurmJobStatus:
    completed: str = "COMPLETED"
    pending: str = "PENDING"
    failed: str = "FAILED"
    running: str = "RUNNING"
    cancelled: str = "CANCELLED"
    timeout: str = "TIMEOUT"
    out_of_memory: str = "OUT_OF_MEMORY"

    def statuses(self):
        return [self.completed, self.pending, self.failed, self.running, self.cancelled]
