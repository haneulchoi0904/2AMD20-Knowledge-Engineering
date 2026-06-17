from __future__ import annotations

import os
from typing import Any

from neo4j import GraphDatabase
from neo4j.exceptions import AuthError, Neo4jError, ServiceUnavailable

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv() -> bool:
        env_path = os.path.join(os.getcwd(), ".env")
        if not os.path.exists(env_path):
            print("[Neo4j] python-dotenv is not installed and .env was not found.")
            return False
        with open(env_path, encoding="utf-8") as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip().lstrip("\ufeff")
                os.environ.setdefault(key, value.strip().strip('"').strip("'"))
        return True


load_dotenv()


class Neo4jClient:
    def __init__(self) -> None:
        self.uri = os.getenv("NEO4J_URI")
        self.user = os.getenv("NEO4J_USER")
        self.password = os.getenv("NEO4J_PASSWORD")
        self.database = os.getenv("NEO4J_DATABASE") or None
        self.driver = None

        if not self.uri or not self.user or not self.password:
            raise ValueError(
                "Missing Neo4j credentials. Please set NEO4J_URI, "
                "NEO4J_USER, and NEO4J_PASSWORD in .env."
            )

        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def verify(self) -> bool:
        try:
            self.driver.verify_connectivity()
            return True
        except (ServiceUnavailable, AuthError, Neo4jError) as exc:
            print(f"[Neo4j] Connection failed: {exc}")
            return False

    def run_query(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        try:
            session_kwargs = {"database": self.database} if self.database else {}
            with self.driver.session(**session_kwargs) as session:
                result = session.run(query, parameters or {})
                return [dict(record) for record in result]
        except (ServiceUnavailable, AuthError, Neo4jError) as exc:
            print(f"[Neo4j] Query failed: {exc}")
            return []

    def close(self) -> None:
        if self.driver is not None:
            self.driver.close()
