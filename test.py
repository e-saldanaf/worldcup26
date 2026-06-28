import os
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

url = URL.create(
    "cockroachdb+psycopg2",
    username="esaldanaf",
    password="NQsiSoZC-arv0yeP1Nty-Q",
    host="esaldanaf-26570.j77.aws-eu-west-1.cockroachlabs.cloud",
    port=26257,
    database="worldcup",
    query={"sslmode": "require"},
)

print("connecting to host:", url.host)
engine = create_engine(url)
with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
    conn.execute(text("CREATE DATABASE IF NOT EXISTS worldcup"))
    print([r[0] for r in conn.execute(text("SHOW DATABASES"))])