"""
Cleanup: Remove old AW line-item contracts (AW-SO*-N format)
Keep only new AW-SO* contract-level nodes (without dash-number suffix).
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from neo4j import GraphDatabase

driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', '12345678'))
with driver.session() as s:
    # Count old vs new
    old = s.run(
        'MATCH (c:Contract) WHERE c.source = "AdventureWorks" AND c.contract_id =~ "AW-SO\\\\d+-\\\\d+" '
        'RETURN count(c) as cnt'
    ).single()['cnt']
    new = s.run(
        'MATCH (c:Contract) WHERE c.source = "AdventureWorks" AND NOT c.contract_id =~ "AW-SO\\\\d+-\\\\d+" '
        'RETURN count(c) as cnt'
    ).single()['cnt']
    print(f'Old line-item AW contracts (to remove): {old}')
    print(f'New contract-level AW contracts (to keep): {new}')

    # Delete old line-item contracts + their relationships
    result = s.run(
        'MATCH (c:Contract) WHERE c.source = "AdventureWorks" AND c.contract_id =~ "AW-SO\\\\d+-\\\\d+" '
        'DETACH DELETE c RETURN count(c) as deleted'
    )
    print(f'Deleted: {result.single()["deleted"]} old nodes')

    # Final counts
    print()
    counts = s.run('MATCH (n) RETURN labels(n)[0] as label, count(n) as cnt ORDER BY cnt DESC').data()
    print('=== Updated Node Counts ===')
    for row in counts:
        print(f'  {row["label"]:25s} {row["cnt"]}')

    aw = s.run('MATCH (c:Contract) WHERE c.source = "AdventureWorks" RETURN count(c) as cnt').single()['cnt']
    cuad = s.run('MATCH (c:Contract) WHERE c.source = "CUAD" RETURN count(c) as cnt').single()['cnt']
    print()
    print(f'AdventureWorks contracts: {aw}')
    print(f'CUAD contracts:           {cuad}')

driver.close()
print('Done.')
