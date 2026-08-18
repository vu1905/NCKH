import sys
sys.stdout.reconfigure(encoding='utf-8')
from neo4j import GraphDatabase

driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', '12345678'))
with driver.session() as s:
    token = '43659'
    cypher = """
    MATCH (c:Contract)
    WHERE c.sales_order_id = $token 
       OR c.sales_order_number CONTAINS $token 
       OR c.contract_no CONTAINS $token 
       OR c.contract_id CONTAINS $token
    OPTIONAL MATCH (c)-[:HAS_PARTY]->(p:Party)
    OPTIONAL MATCH (c)-[:INCLUDES_PRODUCT]->(pr:Product)
    OPTIONAL MATCH (c)-[:GOVERNED_BY]->(co:Country)
    RETURN c, collect(DISTINCT p.name) AS parties, collect(DISTINCT pr.name) AS products, co.name AS country
    """
    res = s.run(cypher, token=token).data()
    print(f'Results for {token}:', len(res))
    for r in res:
        c = r['c']
        print('  Contract ID:', c.get('contract_id'))
        print('  Title:', c.get('title'))
        print('  PDF:', c.get('pdf_filename'))
        print('  PDF Path:', c.get('pdf_path'))
        print('  Parties:', r['parties'])
        print('  Products count:', len(r['products']))
driver.close()
