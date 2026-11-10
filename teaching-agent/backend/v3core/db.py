"""SQLite 连接与事务（红队 P1-11）。

以前的样子：4 个模块级连接、`check_same_thread=False` 跨线程共享、每段写各自
`commit()`、失败时 `except Exception: pass`。后果有三：

1. **事务串味**：A 线程 `execute` 与 `commit` 之间，B 线程可能插进来执行，
   它的未提交写会被 A 的 commit 一并提交；回滚更是会连坐。
2. **半写**：`/api/judge` 里「记作答 → 记错题 → 排复习」是三次独立提交，
   进程在任何一处挂掉，就留下「答了题但没进错题本」的脏状态。
3. **静默失败**：`except: pass` 把 `database is locked` 全吞了，线上只表现为
   「数据莫名不动」，没有任何日志。

现在：

- **每线程一条连接**（`threading.local`），不再跨线程共享游标；
- **同进程同文件只有一个 `Connection` 代理**，写锁共享，避免两个连接互抢；
- `transaction(conn)` 用 `BEGIN IMMEDIATE` 显式开事务，期间内层 `commit()`
  变成 no-op，由最外层统一提交 / 回滚；
- 连接统一 `WAL + busy_timeout` 与 `sqlite3.Row`。

用法：

    conn = db.connection(path, schema=SCHEMA)      # 进程内单例代理
    with db.transaction(conn):                     # 一个原子单元
        record_attempt(conn, ...)                  # 内部 commit 会被吞掉
        record_mistake(conn, ...)
    # 退出时统一 commit；抛异常则整体 rollback
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

BUSY_TIMEOUT_MS = 5000


class Connection:
    """保持 `conn.execute(...)` 调用点不变的线程安全代理。

    每个线程首次访问时创建自己的真实连接（`sqlite3` 连接不是线程安全的，
    `check_same_thread=False` 只是关掉了检查，并不会让它变安全）。
    """

    def __init__(self, path: str | Path, schema: str = "") -> None:
        self.path = str(Path(path))
        self._schema = schema
        self._local = threading.local()
        # 写锁按「库文件」加：同进程里对同一文件的所有写事务串行，
        # 读（WAL）不受影响。
        self.write_lock = threading.RLock()

    # -- 真实连接 ---------------------------------------------------------
    @property
    def raw(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path, timeout=BUSY_TIMEOUT_MS / 1000)
            conn.row_factory = sqlite3.Row
            conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
            conn.execute("PRAGMA journal_mode=WAL")
            if self._schema:
                conn.executescript(self._schema)
                conn.commit()
            self._local.conn = conn
            self._local.depth = 0
        return conn

    # -- 事务深度 ---------------------------------------------------------
    @property
    def depth(self) -> int:
        return int(getattr(self._local, "depth", 0))

    @depth.setter
    def depth(self, value: int) -> None:
        self._local.depth = value

    @property
    def in_transaction(self) -> bool:
        return self.depth > 0

    # -- sqlite3 接口 ------------------------------------------------------
    def execute(self, sql: str, parameters: Any = ()) -> sqlite3.Cursor:
        return self.raw.execute(sql, parameters)

    def executemany(self, sql: str, seq: Any) -> sqlite3.Cursor:
        return self.raw.executemany(sql, seq)

    def executescript(self, script: str) -> sqlite3.Cursor:
        return self.raw.executescript(script)

    def commit(self) -> None:
        # 事务里由最外层统一提交；内层调 commit 不生效
        if self.depth:
            return
        self.raw.commit()

    def rollback(self) -> None:
        if self.depth:
            return
        self.raw.rollback()

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    def __getattr__(self, name: str) -> Any:
        # row_factory / total_changes 之类直接转发
        return getattr(self.raw, name)


_REGISTRY: dict[str, Connection] = {}
_REGISTRY_LOCK = threading.Lock()


def connection(path: str | Path, schema: str = "") -> Connection:
    """进程内按绝对路径去重的连接代理（同文件共享写锁）。"""
    key = str(Path(path).resolve())
    with _REGISTRY_LOCK:
        existing = _REGISTRY.get(key)
        if existing is None:
            existing = Connection(key, schema)
            _REGISTRY[key] = existing
        elif schema and not existing._schema:  # noqa: SLF001 — 后注册的 schema 补上
            existing._schema = schema
        return existing


@contextmanager
def transaction(conn: Connection) -> Iterator[Connection]:
    """把一段写操作包成一个原子单元。

    嵌套调用是安全的：只有最外层真正 BEGIN / COMMIT，内层只是加深计数。
    加的是「本库写锁」而不是全局锁，不同库之间仍然可以并行。
    """
    raw = conn.raw  # 触发本线程连接创建
    with conn.write_lock:
        if conn.depth:
            conn.depth += 1
            try:
                yield conn
            finally:
                conn.depth -= 1
            return

        raw.execute("BEGIN IMMEDIATE")
        conn.depth = 1
        try:
            yield conn
        except BaseException:
            conn.depth = 0
            raw.rollback()
            raise
        else:
            conn.depth = 0
            raw.commit()


def describe() -> dict[str, Any]:
    """给体检用：进程内连接代理、各库是否有线程未提交事务。"""
    return {
        "databases": {
            path: {"schema_chars": len(item._schema)}  # noqa: SLF001
            for path, item in _REGISTRY.items()
        }
    }
