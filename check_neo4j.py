import sys
sys.stdout.reconfigure(encoding='utf-8')
from neo4j import GraphDatabase
driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', '12345678'))
with driver.session() as s:
    r = s.run('MATCH (c:Contract) RETURN DISTINCT c.source as src, count(c) as cnt').data()
    print('Contract sources:')
    for row in r:
        print(' ', row['src'], '->', row['cnt'])

    r2 = s.run('MATCH (c:Contract) WHERE c.source = "AdventureWorks" RETURN c.contract_id, c.title, c.source LIMIT 5').data()
    print()
    print('Sample AW contracts:')
    for row in r2:
        print(' ', row)

    r3 = s.run('MATCH (c:Contract) WHERE c.source = "AdventureWorks" MATCH (c)-[:HAS_PARTY]->(p:Party) RETURN c.contract_id, collect(p.name) as parties LIMIT 3').data()
    print()
    print('AW contracts with parties:')
    for row in r3:
        print(' ', row)

    r4 = s.run('MATCH (c:Contract) WHERE c.source = "AdventureWorks" MATCH (c)-[:HAS_CLAUSE]->(cl:Clause) RETURN c.contract_id, count(cl) as clause_cnt LIMIT 3').data()
    print()
    print('AW contract clause counts:')
    for row in r4:
        print(' ', row)
driver.close()
print('Done.')
