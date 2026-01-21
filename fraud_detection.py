"""
This code is from "fraud_detection.py"
Fraud Detection Algorithms - Native Python Implementation
These algorithms replace Neo4j GDS functions for AuraDB Free Tier compatibility.
"""

import networkx as nx
from collections import defaultdict
from neo4j_utils import run_query


def build_networkx_graph():
    """
    Build a NetworkX graph from Neo4j data for algorithm processing.
    """
    G = nx.Graph()
    
    # Get all nodes
    nodes_query = """
    MATCH (n)
    RETURN n.id as id, labels(n)[0] as label, n.name as name, 
           n.flagged as flagged, n.ring_id as ring_id, n.is_fraudulent as is_fraud
    """
    nodes = run_query(nodes_query)
    
    for node in nodes:
        G.add_node(node['id'], 
                   label=node['label'],
                   name=node.get('name') or node['id'], # Fix for None names
                   flagged=node.get('flagged', False),
                   ring_id=node.get('ring_id'),
                   is_fraud=node.get('is_fraud', False))
    
    # Get all relationships
    rels_query = """
    MATCH (a)-[r]->(b)
    RETURN a.id as source, b.id as target, type(r) as rel_type
    """
    rels = run_query(rels_query)
    
    for rel in rels:
        if rel['source'] and rel['target']:
            G.add_edge(rel['source'], rel['target'], rel_type=rel['rel_type'])
    
    return G


def detect_communities(G: nx.Graph = None):
    """
    Detect communities using connected components (proxy for Louvain in free tier).
    """
    if G is None:
        G = build_networkx_graph()
    
    # Use connected components as base communities
    communities = list(nx.connected_components(G))
    
    # Filter to suspicious communities (more than 3 members)
    suspicious_communities = []
    for i, comm in enumerate(communities):
        if len(comm) >= 4:
            # Score based on flagged nodes
            flagged_count = sum(1 for n in comm if G.nodes[n].get('flagged', False))
            fraud_count = sum(1 for n in comm if G.nodes[n].get('is_fraud', False))
            
            # Get node types distribution
            labels = defaultdict(int)
            for n in comm:
                labels[G.nodes[n].get('label', 'Unknown')] += 1
            
            suspicious_communities.append({
                'community_id': i,
                'size': len(comm),
                'members': list(comm),
                'flagged_count': flagged_count,
                'fraud_count': fraud_count,
                'node_types': dict(labels),
                'risk_score': calculate_community_risk_score(comm, G)
            })
    
    # Sort by risk score
    suspicious_communities.sort(key=lambda x: x['risk_score'], reverse=True)
    
    return suspicious_communities


def calculate_community_risk_score(community: set, G: nx.Graph) -> float:
    """Calculate risk score for a community."""
    if len(community) < 2:
        return 0.0
    
    score = 0.0
    
    # Factor 1: Flagged entities (0-30 points)
    flagged = sum(1 for n in community if G.nodes[n].get('flagged', False))
    score += min(flagged * 10, 30)
    
    # Factor 2: Known fraud indicators (0-40 points)
    fraud = sum(1 for n in community if G.nodes[n].get('is_fraud', False))
    score += min(fraud * 5, 40)
    
    # Factor 3: Network density (0-20 points)
    subgraph = G.subgraph(community)
    if len(community) > 1:
        try:
            density = nx.density(subgraph)
            score += density * 20
        except:
            pass
    
    # Factor 4: Size bonus for medium communities
    if 5 <= len(community) <= 20:
        score += 10
    elif len(community) > 20:
        score += 5
    
    return round(score, 2)


def calculate_node_centrality(G: nx.Graph = None):
    """
    Calculate centrality metrics for all nodes.
    """
    if G is None:
        G = build_networkx_graph()
    
    # Degree centrality
    degree_cent = nx.degree_centrality(G)
    
    # Betweenness centrality (approximate for speed)
    try:
        betweenness = nx.betweenness_centrality(G, k=min(200, len(G)))
    except:
        betweenness = {n: 0 for n in G.nodes()}
    
    results = []
    for node_id in G.nodes():
        node_data = G.nodes[node_id]
        results.append({
            'id': node_id,
            'name': node_data.get('name') or node_id, # Fix for None
            'type': node_data.get('label', 'Unknown'),
            'degree_centrality': round(degree_cent.get(node_id, 0), 4),
            'betweenness_centrality': round(betweenness.get(node_id, 0), 4),
            'combined_score': round(
                degree_cent.get(node_id, 0) * 0.4 + 
                betweenness.get(node_id, 0) * 0.6, 4
            ),
            'flagged': node_data.get('flagged', False),
            'is_fraud': node_data.get('is_fraud', False)
        })
    
    results.sort(key=lambda x: x['combined_score'], reverse=True)
    return results


def detect_collusion_patterns():
    """
    Detect specific collusion patterns using Cypher queries.
    """
    patterns_found = []
    
    # Pattern 1: Repair Shop Clustering
    shop_pattern = run_query("""
        MATCH (c1:Claimant)-[:FILED]->(cl1:Claim)-[:REPAIRED_AT]->(shop:RepairShop)
              <-[:REPAIRED_AT]-(cl2:Claim)<-[:FILED]-(c2:Claimant)
        WHERE c1.id < c2.id
        WITH shop, collect(DISTINCT c1) + collect(DISTINCT c2) as claimants
        WHERE size(claimants) > 3
        RETURN shop.name as entity, shop.id as entity_id, 
               'Repair Shop Clustering' as pattern_type,
               size(claimants) as connected_claimants,
               shop.flagged as is_flagged
        ORDER BY connected_claimants DESC
    """)
    
    for p in shop_pattern:
        patterns_found.append({
            'pattern_type': 'Repair Shop Clustering',
            'entity': p['entity'],
            'entity_id': p['entity_id'],
            'connected_count': p['connected_claimants'],
            'flagged': p.get('is_flagged', False),
            'description': f"{p['connected_claimants']} unrelated claimants using same repair shop",
            'risk_level': 'HIGH' if p['connected_claimants'] > 5 else 'MEDIUM'
        })
    
    # Pattern 2: Medical Mill
    medical_pattern = run_query("""
        MATCH (c:Claimant)-[:FILED]->(cl:Claim)-[:TREATED_AT]->(mp:MedicalProvider)
        WITH mp, collect(DISTINCT c) as claimants
        WHERE size(claimants) > 4
        RETURN mp.name as entity, mp.id as entity_id,
               'Medical Mill' as pattern_type,
               size(claimants) as connected_claimants,
               mp.flagged as is_flagged
        ORDER BY connected_claimants DESC
    """)
    
    for p in medical_pattern:
        patterns_found.append({
            'pattern_type': 'Medical Mill',
            'entity': p['entity'],
            'entity_id': p['entity_id'],
            'connected_count': p['connected_claimants'],
            'flagged': p.get('is_flagged', False),
            'description': f"{p['connected_claimants']} claimants treated by same provider",
            'risk_level': 'HIGH'
        })

    # Pattern 3: Attorney Steering
    attorney_pattern = run_query("""
        MATCH (a:Attorney)-[:REPRESENTS]->(cl:Claim)<-[:FILED]-(c:Claimant)
        OPTIONAL MATCH (cl)-[:REPAIRED_AT]->(shop:RepairShop)
        WITH a, collect(DISTINCT c) as claimants, collect(DISTINCT shop) as shops
        WHERE size(claimants) > 4
        RETURN a.name as entity, a.id as entity_id,
               'Attorney Steering' as pattern_type,
               size(claimants) as connected_claimants,
               size(shops) as unique_shops,
               a.flagged as is_flagged
        ORDER BY connected_claimants DESC
    """)
    
    for p in attorney_pattern:
        shop_ratio = p['unique_shops'] / max(p['connected_claimants'], 1)
        patterns_found.append({
            'pattern_type': 'Attorney Steering',
            'entity': p['entity'],
            'entity_id': p['entity_id'],
            'connected_count': p['connected_claimants'],
            'flagged': p.get('is_flagged', False),
            'description': f"Represents {p['connected_claimants']} claimants from {p['unique_shops']} shops",
            'risk_level': 'HIGH' if shop_ratio < 0.3 else 'MEDIUM'
        })

    return patterns_found


def calculate_claim_risk_score(claim_id: str):
    """
    Calculate contextual fraud risk score for a specific claim.
    """
    context = run_query("""
        MATCH (c:Claimant)-[:FILED]->(claim:Claim {id: $claim_id})
        OPTIONAL MATCH (claim)-[:REPAIRED_AT]->(shop:RepairShop)
        OPTIONAL MATCH (claim)-[:TREATED_AT]->(mp:MedicalProvider)
        OPTIONAL MATCH (claim)<-[:REPRESENTS]-(att:Attorney)
        OPTIONAL MATCH (claim)<-[:WITNESSED]-(wit:Witness)
        OPTIONAL MATCH (c)-[:HAS_PHONE]->(phone:Phone)
        
        // Count neighbors' other connections (The "Network Context")
        OPTIONAL MATCH (shop)<-[:REPAIRED_AT]-(other_claim:Claim)
        WHERE other_claim.id <> claim.id
        WITH c, claim, shop, mp, att, wit, phone, count(DISTINCT other_claim) as shop_claim_count
        
        RETURN c.name as claimant_name, c.id as claimant_id,
               claim.amount as amount, claim.injury_type as injury,
               claim.is_fraudulent as is_fraud, claim.ring_id as ring_id,
               shop.name as shop_name, shop.flagged as shop_flagged,
               mp.name as provider_name, mp.flagged as provider_flagged,
               att.name as attorney_name, att.flagged as attorney_flagged,
               wit.name as witness_name, wit.flagged as witness_flagged,
               phone.number as phone_number, phone.flagged as phone_flagged,
               shop_claim_count
    """, {'claim_id': claim_id})
    
    if not context:
        return None
    
    ctx = context[0]
    risk_factors = []
    risk_score = 0
    
    # Scoring Logic
    if ctx.get('shop_flagged'):
        risk_factors.append("Repair shop is flagged")
        risk_score += 25
    if ctx.get('provider_flagged'):
        risk_factors.append("Medical provider is flagged")
        risk_score += 25
    if ctx.get('attorney_flagged'):
        risk_factors.append("Attorney is flagged")
        risk_score += 20
    if ctx.get('phone_flagged'):
        risk_factors.append("Phone number associated with multiple identities")
        risk_score += 30
    
    # Isolation Check (Mitigating Factor)
    mitigating_factors = []
    if risk_score < 10 and not ctx.get('is_fraud'):
        mitigating_factors.append("Isolated from known fraud rings")
        mitigating_factors.append("Service providers have normal claim volumes")
    
    return {
        'claim_id': claim_id,
        'claimant_name': ctx['claimant_name'],
        'risk_score': risk_score,
        'risk_level': 'HIGH' if risk_score >= 60 else 'MEDIUM' if risk_score >= 30 else 'LOW',
        'risk_factors': risk_factors,
        'mitigating_factors': mitigating_factors,
        'is_known_fraud': ctx.get('is_fraud', False)
    }

def get_network_for_visualization(center_id: str = None, hops: int = 2, limit: int = 150):
    """
    Get network data formatted for streamlit-agraph visualization.
    """
    if center_id:
        # Ego network
        query = f"""
        MATCH path = (center {{id: $center_id}})-[*1..{hops}]-(connected)
        WITH nodes(path) as ns, relationships(path) as rs
        UNWIND ns as n
        WITH DISTINCT n, rs
        UNWIND rs as r
        RETURN DISTINCT 
            n.id as node_id, labels(n)[0] as node_type, n.name as node_name,
            n.flagged as flagged, n.is_fraudulent as is_fraud, n.amount as amount, n.ring_id as ring_id,
            startNode(r).id as source, endNode(r).id as target, type(r) as rel_type
        LIMIT $limit
        """
        results = run_query(query, {'center_id': center_id, 'limit': limit})
    else:
        # Generic sample (rarely used now)
        query = """
        MATCH (n)-[r]->(m)
        RETURN DISTINCT
            n.id as source, m.id as target, type(r) as rel_type,
            n.id as node_id, labels(n)[0] as node_type, n.name as node_name,
            n.flagged as flagged, n.is_fraudulent as is_fraud
        LIMIT $limit
        """
        results = run_query(query, {'limit': limit})
    
    nodes = {}
    edges = []
    
    for r in results:
        # Add Node
        if r['node_id'] not in nodes:
            nodes[r['node_id']] = {
                'id': r['node_id'],
                'type': r.get('node_type', 'Unknown'),
                'name': r.get('node_name') or r['node_id'],
                'flagged': r.get('flagged', False),
                'is_fraud': r.get('is_fraud', False),
                'amount': r.get('amount'),
                'ring_id': r.get('ring_id')
            }
        
        # Add Edge
        if r.get('source') and r.get('target'):
            edges.append({
                'source': r['source'],
                'target': r['target'],
                'rel_type': r.get('rel_type', 'RELATED')
            })
            
    return {'nodes': list(nodes.values()), 'edges': edges}