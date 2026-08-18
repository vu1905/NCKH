import sys
sys.stdout.reconfigure(encoding='utf-8')
from neo4j import GraphDatabase

driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', '12345678'))
with driver.session() as s:
    print('=== Sample AW Contract Detail in Neo4j ===')
    res = s.run('''
    MATCH (c:Contract {sales_order_number: 'SO43659'})
    OPTIONAL MATCH (c)-[:HAS_PARTY]->(p:Party)
    OPTIONAL MATCH (c)-[:IN_TERRITORY]->(t:Territory)
    OPTIONAL MATCH (c)-[:GOVERNED_BY]->(co:Country)
    OPTIONAL MATCH (c)-[:INCLUDES_PRODUCT]->(pr:Product)
    OPTIONAL MATCH (c)-[:HAS_CLAUSE]->(cl:Clause)
    RETURN c.contract_id as id, c.title as title, c.pdf_filename as pdf, c.total_due as total,
           collect(DISTINCT p.name) as parties,
           t.name as territory,
           co.name as country,
           count(DISTINCT pr) as product_count,
           count(DISTINCT cl) as clause_count
    ''').single()
    for k, v in res.items():
        print(f'  {k}: {v}')

    print('\n=== All Relationship Counts ===')
    r_rel = s.run('MATCH ()-[r]->() RETURN type(r) as rel, count(r) as cnt ORDER BY cnt DESC')
    for r in r_rel:
        print(f"  {r['rel']:25s}: {r['cnt']}")
driver.close()
