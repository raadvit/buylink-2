import threading


class ImplementQueue:
    def __init__(self, max_workers: int = 1):
        self._max_workers = max(1, max_workers)
        self._semaphore = threading.Semaphore(self._max_workers)
        self._lock = threading.Lock()
        self._queue: list[str] = []
        self._active_issues: set[int] = set()

    def submit(self, session_id: str, issue_number: int, launch_fn, update_status_fn, store) -> int:
        with self._lock:
            if issue_number in self._active_issues:
                raise ValueError(f"Issue {issue_number} je již ve frontě nebo se implementuje.")
            self._active_issues.add(issue_number)
            self._queue.append(session_id)
            position = len(self._queue)
        store.update_session(session_id, status="queued", queue_position=position)
        t = threading.Thread(
            target=self._worker,
            args=(session_id, issue_number, launch_fn, update_status_fn, store),
            daemon=True,
        )
        t.start()
        return position

    def get_position(self, session_id: str) -> int:
        with self._lock:
            try:
                return self._queue.index(session_id) + 1
            except ValueError:
                return 0

    def _worker(self, session_id: str, issue_number: int, launch_fn, update_status_fn, store) -> None:
        self._semaphore.acquire()
        try:
            with self._lock:
                try:
                    self._queue.remove(session_id)
                except ValueError:
                    pass
            try:
                update_status_fn()
            except RuntimeError as e:
                store.update_session(session_id, status="error", error=str(e))
                return
            launch_fn(session_id, issue_number, store)
        finally:
            with self._lock:
                self._active_issues.discard(issue_number)
            self._semaphore.release()


class AnalysisQueue:
    def __init__(self, max_workers: int = 1):
        self._max_workers = max(1, max_workers)
        self._semaphore = threading.Semaphore(self._max_workers)
        self._lock = threading.Lock()
        self._queue: list[str] = []

    def submit(self, session_id: str, issue_number: int, launch_fn, store) -> int:
        with self._lock:
            self._queue.append(session_id)
            position = len(self._queue)
        store.update_session(session_id, status="queued", queue_position=position)
        t = threading.Thread(target=self._worker, args=(session_id, issue_number, launch_fn, store), daemon=True)
        t.start()
        return position

    def get_position(self, session_id: str) -> int:
        with self._lock:
            try:
                return self._queue.index(session_id) + 1
            except ValueError:
                return 0

    def _worker(self, session_id: str, issue_number: int, launch_fn, store) -> None:
        self._semaphore.acquire()
        try:
            with self._lock:
                try:
                    self._queue.remove(session_id)
                except ValueError:
                    pass
            store.update_session(session_id, status="analyzing", queue_position=0)
            launch_fn(session_id, issue_number, store)
        finally:
            self._semaphore.release()
