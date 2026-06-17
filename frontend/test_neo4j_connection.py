from services.neo4j_client import Neo4jClient
from services.cypher_queries import NODE_COUNT_QUERY


def main() -> None:
    client = Neo4jClient()

    if not client.verify():
        print("Neo4j connection failed.")
        client.close()
        return

    print("Neo4j connection established.")
    rows = client.run_query(NODE_COUNT_QUERY)

    if not rows:
        print("Connection works, but the validation query returned no rows.")
    else:
        print("Node counts:")
        for row in rows:
            print(row["node_type"], row["count"])

    client.close()


if __name__ == "__main__":
    main()
